"""Vision extract: image bytes -> ScanResult. Grok copies what is printed; it never computes."""

from __future__ import annotations

import json
from typing import Any

import httpx
from PIL import UnidentifiedImageError
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
        "number, manufacture year, total volume in cubic feet, and the yearly electricity use in "
        "kWh printed on an EnergyGuide label (label_kwh_per_year). product_class is the DOE product "
        "class code only when the label prints one as a code (for example 3 or 5A); a description "
        "such as Refrigerator-Freezers with Top-Mounted Freezer is not a code, so use null." + _RULES
    ),
    "price_tag": "You read store price tags: brand, model number and the price in dollars." + _RULES,
    "lease": (
        "You read rent-to-own lease pages and paperwork: the leased refrigerator's brand and model "
        "number, weekly payment, term in weeks, cash price, "
        "fees, the early purchase option (its rule, the percent printed, and its exact wording in "
        "early_purchase_text) and the missed payment rule. fees is a separately charged fee printed "
        "as a dollar amount, such as an enrollment, processing or delivery fee; 0 when the page "
        "prints the fee as None or Free; never the cost of lease services, a payment or a total. "
        "payment_today is the amount printed as due today or at signing. total_of_payments is the "
        "total of all lease payments to ownership as printed (labelled for example Total of Payments "
        "or Total Cost of Ownership); null when no total is printed, never a sum you work out. "
        "early_purchase_rule is pct_of_remaining "
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
            "brand": _nullable("string"),
            "model": _nullable("string"),
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
            "payment_today": _nullable("number"),
            "total_of_payments": _nullable("number"),
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


def _failure(exc: Exception) -> str:
    if isinstance(exc, UnidentifiedImageError):
        return "The image could not be read. Use a JPEG or PNG photo."
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Grok returned an error (HTTP {exc.response.status_code}). Enter the details by hand."
    if isinstance(exc, httpx.RequestError):
        return "Could not reach Grok. Enter the details by hand."
    if isinstance(exc, (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError)):
        return "Grok's reply could not be read. Enter the details by hand."
    return "The scan failed. Enter the details by hand."


def scan(kind: ScanKind, image_jpeg: bytes, client: GrokClient) -> ScanResult:
    try:
        raw = client.chat_json(_PROMPTS[kind], _USER, image_jpeg, schema=_SCHEMAS[kind])
    except Exception as exc:  # any client, network, reply or image failure goes to the manual form
        return ScanResult(kind=kind, valid=False, errors=[_failure(exc)])
    if not isinstance(raw, dict):
        return ScanResult(kind=kind, valid=False, errors=["Grok's reply could not be read. Enter the details by hand."])
    printed = {
        k: v for k, v in raw.items() if v is not None and v != "" and isinstance(v, (str, int, float, bool))
    }
    errors, parts = _BUILDERS[kind](printed)
    errors = list(dict.fromkeys(errors))
    if errors:
        return ScanResult(kind=kind, valid=False, errors=errors, fields=printed)
    return ScanResult(kind=kind, valid=True, fields=printed, **parts)


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


Built = tuple[list[str], dict[str, Any]]


def _item(kept: dict[str, Any], **extra: Any) -> tuple[Item | None, list[str]]:
    try:
        return Item.model_validate({**_ITEM_SCAFFOLD, **extra, **kept}), []
    except ValidationError as exc:
        return None, _fmt(exc, prefix="item")


def _offer(raw: dict[str, Any], **fixed: Any) -> tuple[Offer | None, list[str]]:
    kept, errors = _check(Offer, raw, ("price",))
    if "price" not in kept:
        return None, errors + _missing(kept, ("price",))
    try:
        return Offer.model_validate({"item_id": "scan", **fixed, **kept}), errors
    except ValidationError as exc:
        return None, errors + _fmt(exc, prefix="offer")


_LABEL_ATTRS = {"product_class": str, "volume_cuft": float, "label_kwh_per_year": float}


def _from_label(raw: dict[str, Any]) -> Built:
    kept, errors = _check(Item, raw, ("brand", "model", "serial", "mfg_year"))
    attrs, attr_errors = _check(_LABEL_ATTRS, raw, _LABEL_ATTRS)
    extra: dict[str, Any] = {"attributes": attrs}
    if "mfg_year" in kept:
        extra["year_confidence"] = "high"
    item, item_errors = _item(kept, **extra)
    return errors + attr_errors + item_errors + _missing(kept, ("brand", "model")), {"item": item}


def _from_price_tag(raw: dict[str, Any]) -> Built:
    kept, errors = _check(Item, raw, ("brand", "model"))
    item, item_errors = _item(kept, condition="new")
    offer, offer_errors = _offer(raw, seller_type="retailer", source="price_tag", source_id="user")
    errors = errors + item_errors + offer_errors + _missing(kept, ("brand", "model"))
    return errors, {"item": item, "offer": offer}


def _from_listing(raw: dict[str, Any]) -> Built:
    kept, errors = _check(Item, raw, ("brand", "model", "condition", "mfg_year"))
    extra: dict[str, Any] = {}
    if "mfg_year" in kept:
        # A seller's stated year is not a printed rating, so it is not trusted as high.
        extra["year_confidence"] = "low"
    item, item_errors = _item(kept, **extra)
    offer, offer_errors = _offer(raw, seller_type="private", source="user_listing", source_id="user_listing")
    errors = errors + item_errors + offer_errors + _missing(kept, ("brand", "model", "condition"))
    return errors, {"item": item, "offer": offer}


_LEASE_KEYS = (
    "weekly_payment",
    "term_weeks",
    "cash_price",
    "fees",
    "early_purchase_rule",
    "early_purchase_text",
    "missed_payment_rule",
    "payment_today",
    "total_of_payments",
)


def _from_lease(raw: dict[str, Any]) -> Built:
    kept, errors = _check(Lease, raw, _LEASE_KEYS)
    if "early_purchase_percent" in raw:
        pct, pct_errors = _check({"early_purchase_percent": float}, raw, ("early_purchase_percent",))
        errors += pct_errors
        if "early_purchase_percent" in pct:
            kept["early_purchase_pct"] = pct["early_purchase_percent"] / 100
    kept["source_id"] = "user_lease"
    errors += _missing(kept, ("weekly_payment", "term_weeks", "cash_price"))
    lease: Lease | None = None
    try:
        lease = Lease.model_validate(kept)
    except ValidationError as exc:
        errors += _fmt(exc, prefix="lease")
    # The leased unit is the rent-to-own offer the quote pairs with the lease; its price is the cash price.
    item_kept, item_errors = _check(Item, raw, ("brand", "model"))
    item, build_errors = _item(item_kept, condition="new")
    offer_raw = {"price": kept["cash_price"]} if "cash_price" in kept else {}
    offer, offer_errors = _offer(offer_raw, seller_type="rent_to_own", source="user_listing", source_id="user_listing")
    offer_errors = [e for e in offer_errors if e != "price: missing"]
    errors += item_errors + build_errors + offer_errors + _missing(item_kept, ("brand", "model"))
    return errors, {"item": item, "offer": offer, "lease": lease}


_BUILDERS = {"label": _from_label, "price_tag": _from_price_tag, "lease": _from_lease, "listing": _from_listing}
