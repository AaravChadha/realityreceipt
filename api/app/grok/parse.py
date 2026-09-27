"""Request parsing: a shopper's words -> ShopFilters. Grok copies what the user typed; it never
computes, estimates or translates a number."""

from __future__ import annotations

import json
import math
from typing import Any

import httpx
from pydantic import ValidationError

from app.grok.client import GrokClient
from app.models import ShopFilters

_SYSTEM = (
    "You read a shopper's request for a refrigerator and fill in filters. "
    "budget_dollars is the amount the shopper typed as a dollar figure (300 for about $300); "
    "null when no amount is typed. "
    "max_width_inches is the space width the shopper typed in inches (30 for 30 inches or 30\"); "
    "null when no inch figure is typed, even if they describe the space as small or tight. "
    "within_days is a number of days the shopper typed (3 for within 3 days); null otherwise. "
    "timeframe is today, this_week or this_month when the shopper says they need it then "
    "(this_week for this week or within a week); null when no timeframe is given. "
    "conditions lists the conditions the shopper will accept: new, refurbished, or used_as_is for "
    "used; an empty list when they do not say. "
    "Copy numbers exactly as typed. Never infer, estimate, convert, round or compute a number."
)

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "budget_dollars": {"type": ["number", "null"]},
        "max_width_inches": {"type": ["number", "null"]},
        "within_days": {"type": ["integer", "null"]},
        "timeframe": {"anyOf": [{"enum": ["today", "this_week", "this_month"]}, {"type": "null"}]},
        "conditions": {"type": "array", "items": {"enum": ["new", "refurbished", "used_as_is"]}},
    },
    "required": ["budget_dollars", "max_width_inches", "within_days", "timeframe", "conditions"],
    "additionalProperties": False,
}

# A calendar rule applied in code, not an estimate: the latest delivery that still meets the timeframe.
TIMEFRAME_DAYS = {"today": 0, "this_week": 7, "this_month": 30}

_NUMBERS = {"budget_dollars": "budget_today", "max_width_inches": "max_width_in", "within_days": "need_within_days"}


def parse_request(text: str, client: GrokClient) -> ShopFilters:
    return parse_request_with_errors(text, client)[0]


def parse_request_with_errors(text: str, client: GrokClient) -> tuple[ShopFilters, list[str]]:
    """The filters for the UI to show for editing, or empty filters plus the errors on failure."""
    if not text.strip():
        return ShopFilters(), []
    try:
        raw = client.chat_json(_SYSTEM, text.strip(), schema=_SCHEMA)
    except Exception as exc:  # any client, network or reply failure leaves the filters to the user
        return ShopFilters(), [_failure(exc)]
    if not isinstance(raw, dict):
        return ShopFilters(), ["Grok's reply could not be read. Set the filters by hand."]

    errors: list[str] = []
    data: dict[str, Any] = {"category": "refrigerator"}
    for key, field in _NUMBERS.items():
        value = raw.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            errors.append(f"{key}: not a number")
        elif key == "within_days" and not float(value).is_integer():
            errors.append(f"{key}: not a whole number of days")
        else:
            data[field] = int(value) if key == "within_days" else value

    timeframe = raw.get("timeframe")
    if timeframe is not None and timeframe not in TIMEFRAME_DAYS:
        errors.append(f"timeframe: {timeframe!r} is not today, this_week or this_month")
    elif timeframe is not None and "need_within_days" not in data:
        data["need_within_days"] = TIMEFRAME_DAYS[timeframe]

    conditions = raw.get("conditions") or []
    if not isinstance(conditions, list):
        errors.append("conditions: not a list")
    else:
        data["conditions"] = list(dict.fromkeys(conditions))

    if errors:
        return ShopFilters(), errors
    try:
        return ShopFilters.model_validate(data), []
    except ValidationError as exc:
        return ShopFilters(), [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]


def _failure(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Grok returned an error (HTTP {exc.response.status_code}). Set the filters by hand."
    if isinstance(exc, httpx.RequestError):
        return "Could not reach Grok. Set the filters by hand."
    if isinstance(exc, (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError)):
        return "Grok's reply could not be read. Set the filters by hand."
    return "Parsing failed. Set the filters by hand."
