"""Vision extract: image bytes → ScanResult. Grok reads; it never computes."""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.grok.client import GrokClient
from app.models import Item, Lease, Offer, ScanKind, ScanResult

_USER = "Extract the fields printed on this image. Return JSON only."

_PROMPTS: dict[ScanKind, str] = {
    "label": (
        "You read appliance rating labels. Return a single JSON object with only these "
        "keys, copied exactly as printed: brand, model, serial, product_class, volume_cuft. "
        "volume_cuft is a number. Do not invent, estimate, convert or compute any value. "
        "If a field is not printed, omit it. No markdown, no commentary."
    ),
    "price_tag": (
        "You read store price tags. Return a single JSON object with only these keys, "
        "copied exactly as printed: brand, model, price. price is a number in dollars. "
        "Do not invent, estimate, convert or compute any value. If a field is not printed, "
        "omit it. No markdown, no commentary."
    ),
    "lease": (
        "You read rent-to-own lease paperwork. Return a single JSON object with only these "
        "keys, copied exactly as printed: weekly_payment, term_weeks, cash_price, fees, "
        "early_purchase_rule, early_purchase_pct, early_purchase_text, missed_payment_rule, "
        "source_id. early_purchase_rule is one of pct_of_remaining, cash_price_minus_pct_paid, "
        "none. early_purchase_pct is a fraction in [0, 1] when a percent is printed, else null "
        "when the rule is none. Numbers are numbers. Do not invent, estimate, convert or "
        "compute any value. If a field is not printed, omit it (use source_id \"user_lease\" "
        "only when no source id is printed). No markdown, no commentary."
    ),
    "listing": (
        "You read used-appliance listing screenshots. Return a single JSON object with only "
        "these keys, copied exactly as printed: brand, model, price, condition. price is a "
        "number in dollars. condition is one of new, used_as_is, refurbished. Do not invent, "
        "estimate, convert or compute any value. If a field is not printed, omit it. No "
        "markdown, no commentary."
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
    raw = client.chat_json(_PROMPTS[kind], _USER, image_jpeg)
    if not isinstance(raw, dict):
        return ScanResult(kind=kind, valid=False, errors=["response is not a JSON object"])
    if kind == "label":
        return _from_label(raw)
    if kind == "price_tag":
        return _from_price_tag(raw)
    if kind == "lease":
        return _from_lease(raw)
    return _from_listing(raw)


def _fmt(exc: ValidationError, prefix: str = "") -> list[str]:
    out: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"])
        path = f"{prefix}.{loc}" if prefix and loc else (prefix or loc or "value")
        out.append(f"{path}: {err['msg']}")
    return out


def _validate_fields(model_cls: type, data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    kept: dict[str, Any] = {}
    errors: list[str] = []
    for key, value in data.items():
        field = model_cls.model_fields.get(key)
        if field is None:
            continue
        try:
            kept[key] = TypeAdapter(field.annotation).validate_python(value)
        except ValidationError as exc:
            errors.extend(_fmt(exc, prefix=key))
    return kept, errors


def _missing(kept: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for key in keys:
        value = kept.get(key)
        if value is None or value == "":
            out.append(f"{key}: missing")
    return out


def _pick(raw: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: raw[key] for key in keys if key in raw}


def _item(
    raw: dict[str, Any],
    keys: tuple[str, ...],
    *,
    condition: str | None = None,
    attributes: dict[str, str | float] | None = None,
) -> tuple[Item, list[str]]:
    kept, errors = _validate_fields(Item, _pick(raw, keys))
    data = dict(_ITEM_SCAFFOLD)
    if condition is not None:
        data["condition"] = condition
    data.update(kept)
    if attributes is not None:
        data["attributes"] = attributes
    try:
        return Item.model_validate(data), errors
    except ValidationError as exc:
        return Item.model_construct(**data), errors + _fmt(exc, prefix="item")


def _offer(
    raw: dict[str, Any],
    *,
    seller_type: str,
    source: str,
    source_id: str,
) -> tuple[Offer | None, list[str]]:
    kept, errors = _validate_fields(Offer, _pick(raw, ("price",)))
    if "price" not in kept:
        return None, errors + _missing(kept, ("price",))
    data = {
        "item_id": "scan",
        "seller_type": seller_type,
        "source": source,
        "source_id": source_id,
        **kept,
    }
    try:
        return Offer.model_validate(data), errors
    except ValidationError as exc:
        return Offer.model_construct(**data), errors + _fmt(exc, prefix="offer")


def _lease(raw: dict[str, Any]) -> tuple[Lease | None, list[str], bool]:
    keys = (
        "weekly_payment",
        "term_weeks",
        "cash_price",
        "fees",
        "early_purchase_rule",
        "early_purchase_pct",
        "early_purchase_text",
        "missed_payment_rule",
        "source_id",
    )
    kept, errors = _validate_fields(Lease, _pick(raw, keys))
    if "source_id" not in kept:
        kept["source_id"] = "user_lease"
    errors = errors + _missing(kept, ("weekly_payment", "term_weeks", "cash_price"))
    try:
        return Lease.model_validate(kept), errors, not errors
    except ValidationError as exc:
        errors = errors + _fmt(exc, prefix="lease")
        if not any(k in kept for k in ("weekly_payment", "term_weeks", "cash_price", "early_purchase_text", "fees")):
            return None, errors, False
        return Lease.model_construct(**kept), errors, False


def _label_attrs(raw: dict[str, Any]) -> tuple[dict[str, str | float], list[str]]:
    attrs: dict[str, str | float] = {}
    errors: list[str] = []
    if "product_class" in raw:
        try:
            attrs["product_class"] = TypeAdapter(str).validate_python(raw["product_class"])
        except ValidationError as exc:
            errors.extend(_fmt(exc, prefix="product_class"))
    if "volume_cuft" in raw:
        try:
            attrs["volume_cuft"] = TypeAdapter(float).validate_python(raw["volume_cuft"])
        except ValidationError as exc:
            errors.extend(_fmt(exc, prefix="volume_cuft"))
    return attrs, errors


def _from_label(raw: dict[str, Any]) -> ScanResult:
    attrs, attr_errors = _label_attrs(raw)
    item_kept, field_type_errors = _validate_fields(Item, _pick(raw, ("brand", "model", "serial")))
    item, build_errors = _item(
        raw,
        ("brand", "model", "serial"),
        condition="used_as_is",
        attributes=attrs,
    )
    errors = attr_errors + field_type_errors + build_errors + _missing(item_kept, ("brand", "model"))
    # Drop duplicate messages while preserving order.
    errors = list(dict.fromkeys(errors))
    return ScanResult(kind="label", valid=not errors, errors=errors, item=item)


def _from_price_tag(raw: dict[str, Any]) -> ScanResult:
    item_kept, item_type_errors = _validate_fields(Item, _pick(raw, ("brand", "model")))
    item, item_build_errors = _item(raw, ("brand", "model"), condition="new")
    offer, offer_errors = _offer(raw, seller_type="retailer", source="price_tag", source_id="user")
    errors = list(
        dict.fromkeys(
            item_type_errors
            + item_build_errors
            + offer_errors
            + _missing(item_kept, ("brand", "model"))
        )
    )
    valid = not errors and offer is not None
    return ScanResult(kind="price_tag", valid=valid, errors=errors, item=item, offer=offer)


def _from_listing(raw: dict[str, Any]) -> ScanResult:
    item_kept, item_type_errors = _validate_fields(Item, _pick(raw, ("brand", "model", "condition")))
    condition = item_kept.get("condition") if "condition" in item_kept else None
    item, item_build_errors = _item(
        raw,
        ("brand", "model", "condition"),
        condition=condition if isinstance(condition, str) else "used_as_is",
    )
    offer, offer_errors = _offer(
        raw,
        seller_type="private",
        source="user_listing",
        source_id="user_listing",
    )
    errors = list(
        dict.fromkeys(
            item_type_errors
            + item_build_errors
            + offer_errors
            + _missing(item_kept, ("brand", "model", "condition"))
        )
    )
    valid = not errors and offer is not None
    return ScanResult(kind="listing", valid=valid, errors=errors, item=item, offer=offer)


def _from_lease(raw: dict[str, Any]) -> ScanResult:
    lease, errors, ok = _lease(raw)
    errors = list(dict.fromkeys(errors))
    return ScanResult(kind="lease", valid=ok and not errors, errors=errors, lease=lease)
