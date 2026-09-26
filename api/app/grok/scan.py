"""Vision extract: image bytes -> ScanResult. Grok copies what is printed; it never computes."""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.grok.client import GrokClient
from app.models import Item, Lease, Offer, ScanKind, ScanResult

_USER = "Extract the fields printed on this image."

_RULES = (
    " Copy every value exactly as printed. Use null for anything not printed. Never infer, "
    "estimate, convert, round or compute a number, and never fill a field from general knowledge."
)

_PROMPTS: dict[ScanKind, str] = {
    "label": (
        "You read refrigerator rating labels and EnergyGuide labels: brand, model number, serial "
        "number, manufacture year, product class or type, total volume in cubic feet, and the "
        "yearly electricity use in kWh printed on an EnergyGuide label (label_kwh_per_year)." + _RULES
    ),
    "price_tag": "You read store price tags: brand, model number and the price in dollars." + _RULES,
    "lease": (
        "You read rent-to-own lease pages and paperwork: weekly payment, term in weeks, cash price, "
        "fees, the early purchase option (its rule, the percent printed, and its exact wording in "
        "early_purchase_text) and the missed payment rule. early_purchase_rule is pct_of_remaining "
        "when the buyout is a percent of the remaining payments, cash_price_minus_pct_paid when it "
        "is the cash price minus a percent of what was paid, none when no early purchase option is "
        "printed. early_purchase_percent is the percent number as printed (50 for 50%)." + _RULES
    ),
    "listing": (
        "You read used-appliance listing screenshots: brand, model number, asking price in dollars, "
        "condition, and the manufacture year if the listing states one. condition is new, "
        "refurbished, or used_as_is for any other used item." + _RULES
    ),
}


def _nullable(json_type: str | list[str]) -> dict:
    types = json_type if isinstance(json_type, list) else [json_type]
    return {"type": [*types, "null"]}


def _schema(props: dict[str, dict]) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


_SCHEMAS: dict[ScanKind, dict] = {
    "label": _schema(
        {
            "brand": _nullable("string"),
            "model": _nullable("string"),
            "serial": _nullable("string"),
            "mfg_year": _nullable("integer"),
            "product_class": _nullable("string"),
            "volume_cuft": _nullable("number"),
            "label_kwh_per_year": _nullable("number"),
        }
    ),
    "price_tag": _schema(
        {"brand": _nullable("string"), "model": _nullable("string"), "price": _nullable("number")}
    ),
    "lease": _schema(
        {
            "weekly_payment": _nullable("number"),
            "term_weeks": _nullable("integer"),
            "cash_price": _nullable("number"),
            "fees": _nullable("number"),
            "early_purchase_rule": {
                "anyOf": [
                    {"enum": ["pct_of_remaining", "cash_price_minus_pct_paid", "none"]},
                    {"type": "null"},
                ]
            },
            "early_purchase_percent": _nullable("number"),
            "early_purchase_text": _nullable("string"),
            "missed_payment_rule": _nullable("string"),
        }
    ),
    "listing": _schema(
        {
            "brand": _nullable("string"),
            "model": _nullable("string"),
            "price": _nullable("number"),
            "condition": {"anyOf": [{"enum": ["new", "used_as_is", "refurbished"]}, {"type": "null"}]},
            "mfg_year": _nullable("integer"),
        }
    ),
}

_ITEM_SCAFFOLD: dict[str, Any] = {
    "id": "scan",
    "category": "refrigerator",
    "brand": "",
    "model": "",
    "condition": "used_as_is",
}


def scan(kind: ScanKind, image_jpeg: bytes, client: GrokClient) -> ScanResult:
    raw = client.chat_json(_PROMPTS[kind], _USER, image_jpeg, schema=_SCHEMAS[kind])
    if not isinstance(raw, dict):
        return ScanResult(kind=kind, valid=False, errors=["response is not a JSON object"])
    printed = {k: v for k, v in raw.items() if v is not None and v != ""}
    if kind == "label":
        return _from_label(printed)
    if kind == "price_tag":
        return _from_price_tag(printed)
    if kind == "lease":
        return _from_lease(printed)
    return _from_listing(printed)


def _fmt(exc: ValidationError, prefix: str = "") -> list[str]:
    out: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"])
        path = f"{prefix}.{loc}" if prefix and loc else (prefix or loc or "value")
        out.append(f"{path}: {err['msg']}")
    return out


def _check(annotation: Any, raw: dict[str, Any], keys: tuple[str, ...] | dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Validate each present key on its own, so one bad field does not discard the others."""
    kept: dict[str, Any] = {}
    errors: list[str] = []
    for key in keys:
        if key not in raw:
            continue
        target = annotation[key] if isinstance(annotation, dict) else annotation.model_fields[key].annotation
        try:
            kept[key] = TypeAdapter(target).validate_python(raw[key])
        except ValidationError as exc:
            errors.extend(_fmt(exc, prefix=key))
    return kept, errors


def _missing(kept: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    return [f"{key}: missing" for key in keys if key not in kept]


def _item(kept: dict[str, Any], **extra: Any) -> tuple[Item, list[str]]:
    data = {**_ITEM_SCAFFOLD, **extra, **kept}
    try:
        return Item.model_validate(data), []
    except ValidationError as exc:
        return Item.model_construct(**data), _fmt(exc, prefix="item")


def _offer(raw: dict[str, Any], **fixed: Any) -> tuple[Offer | None, list[str]]:
    kept, errors = _check(Offer, raw, ("price",))
    if "price" not in kept:
        return None, errors + _missing(kept, ("price",))
    data = {"item_id": "scan", **fixed, **kept}
    try:
        return Offer.model_validate(data), errors
    except ValidationError as exc:
        return Offer.model_construct(**data), errors + _fmt(exc, prefix="offer")


def _result(kind: ScanKind, errors: list[str], **parts: Any) -> ScanResult:
    errors = list(dict.fromkeys(errors))
    return ScanResult(kind=kind, valid=not errors, errors=errors, **parts)


_LABEL_ATTRS = {"product_class": str, "volume_cuft": float, "label_kwh_per_year": float}


def _from_label(raw: dict[str, Any]) -> ScanResult:
    kept, errors = _check(Item, raw, ("brand", "model", "serial", "mfg_year"))
    attrs, attr_errors = _check(_LABEL_ATTRS, raw, _LABEL_ATTRS)
    extra: dict[str, Any] = {"attributes": attrs}
    if "mfg_year" in kept:
        extra["year_confidence"] = "high"
    item, item_errors = _item(kept, **extra)
    return _result("label", errors + attr_errors + item_errors + _missing(kept, ("brand", "model")), item=item)


def _from_price_tag(raw: dict[str, Any]) -> ScanResult:
    kept, errors = _check(Item, raw, ("brand", "model"))
    item, item_errors = _item(kept, condition="new")
    offer, offer_errors = _offer(raw, seller_type="retailer", source="price_tag", source_id="user")
    errors = errors + item_errors + offer_errors + _missing(kept, ("brand", "model"))
    return _result("price_tag", errors, item=item, offer=offer)


def _from_listing(raw: dict[str, Any]) -> ScanResult:
    kept, errors = _check(Item, raw, ("brand", "model", "condition", "mfg_year"))
    extra: dict[str, Any] = {}
    if "mfg_year" in kept:
        # A seller's stated year is not a printed rating, so it is not trusted as high.
        extra["year_confidence"] = "low"
    item, item_errors = _item(kept, **extra)
    offer, offer_errors = _offer(raw, seller_type="private", source="user_listing", source_id="user_listing")
    errors = errors + item_errors + offer_errors + _missing(kept, ("brand", "model", "condition"))
    return _result("listing", errors, item=item, offer=offer)


_LEASE_KEYS = (
    "weekly_payment",
    "term_weeks",
    "cash_price",
    "fees",
    "early_purchase_rule",
    "early_purchase_text",
    "missed_payment_rule",
)


def _from_lease(raw: dict[str, Any]) -> ScanResult:
    kept, errors = _check(Lease, raw, _LEASE_KEYS)
    if "early_purchase_percent" in raw:
        pct, pct_errors = _check({"early_purchase_percent": float}, raw, ("early_purchase_percent",))
        errors += pct_errors
        if "early_purchase_percent" in pct:
            kept["early_purchase_pct"] = pct["early_purchase_percent"] / 100
    kept["source_id"] = "user_lease"
    errors += _missing(kept, ("weekly_payment", "term_weeks", "cash_price"))
    try:
        lease = Lease.model_validate(kept)
    except ValidationError as exc:
        errors += _fmt(exc, prefix="lease")
        lease = Lease.model_construct(**kept)
    return _result("lease", errors, lease=lease)
