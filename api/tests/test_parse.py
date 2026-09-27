"""Request parsing (PLAN.md task 4.1) with a fake Grok client; never calls the network.

The replies below were recorded from grok-4.20-0309-non-reasoning on 2026-09-26 with this
module's prompt and schema.
"""

import json

import httpx
import pytest

from app.grok.parse import _SCHEMA, TIMEFRAME_DAYS, parse_request, parse_request_with_errors
from app.models import ShopFilters

RECORDED = {
    "about $300, small space, need it this week": {
        "budget_dollars": 300, "max_width_inches": None, "within_days": None,
        "timeframe": "this_week", "conditions": [],
    },
    "under $500, 30 inches wide, within 3 days, used or refurbished is fine": {
        "budget_dollars": 500, "max_width_inches": 30, "within_days": 3,
        "timeframe": None, "conditions": ["refurbished", "used_as_is"],
    },
    "a fridge for my apartment, nothing fancy": {
        "budget_dollars": None, "max_width_inches": None, "within_days": None,
        "timeframe": None, "conditions": [],
    },
}

EMPTY_REPLY = {"budget_dollars": None, "max_width_inches": None, "within_days": None, "timeframe": None, "conditions": []}


class FakeGrokClient:
    def __init__(self, reply: object) -> None:
        self.reply = reply
        self.calls: list[dict] = []

    def chat_json(self, system: str, user: str, image_jpeg: bytes | None = None, schema: dict | None = None) -> object:
        self.calls.append({"system": system, "user": user, "image": image_jpeg, "schema": schema})
        return self.reply


class RaisingClient:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def chat_json(self, *_args, **_kwargs) -> dict:
        raise self.exc


def _parse(text: str) -> tuple[ShopFilters, list[str]]:
    return parse_request_with_errors(text, FakeGrokClient(RECORDED[text]))


def test_budget_and_this_week_map_and_a_small_space_gets_no_invented_width() -> None:
    filters, errors = _parse("about $300, small space, need it this week")
    assert errors == []
    assert filters.budget_today == 300
    assert filters.need_within_days == 7
    # "small space" gives no inch figure, so the width is left for the user to fill in.
    assert filters.max_width_in is None
    assert filters.category == "refrigerator"


def test_typed_numbers_and_conditions_are_copied() -> None:
    filters, errors = _parse("under $500, 30 inches wide, within 3 days, used or refurbished is fine")
    assert errors == []
    assert (filters.budget_today, filters.max_width_in, filters.need_within_days) == (500, 30, 3)
    assert filters.conditions == ["refurbished", "used_as_is"]


def test_a_request_with_no_numbers_sets_no_numbers() -> None:
    filters, errors = _parse("a fridge for my apartment, nothing fancy")
    assert errors == []
    assert filters == ShopFilters(category="refrigerator")


@pytest.mark.parametrize(("timeframe", "days"), sorted(TIMEFRAME_DAYS.items()))
def test_each_timeframe_maps_to_its_calendar_days(timeframe: str, days: int) -> None:
    filters, errors = parse_request_with_errors("x", FakeGrokClient({**EMPTY_REPLY, "timeframe": timeframe}))
    assert errors == []
    assert filters.need_within_days == days


def test_typed_days_win_over_a_timeframe() -> None:
    reply = {**EMPTY_REPLY, "within_days": 3, "timeframe": "this_month"}
    filters, _ = parse_request_with_errors("x", FakeGrokClient(reply))
    assert filters.need_within_days == 3


def test_the_request_is_text_only_with_the_strict_schema() -> None:
    client = FakeGrokClient(EMPTY_REPLY)
    parse_request_with_errors("  about $300  ", client)
    [call] = client.calls
    assert call["user"] == "about $300"
    assert call["image"] is None
    assert call["schema"] is _SCHEMA
    assert _SCHEMA["additionalProperties"] is False
    assert set(_SCHEMA["required"]) == set(_SCHEMA["properties"])
    assert "Never infer, estimate, convert, round or compute a number" in call["system"]


def test_blank_text_does_not_call_grok() -> None:
    client = FakeGrokClient(EMPTY_REPLY)
    assert parse_request_with_errors("   ", client) == (ShopFilters(), [])
    assert client.calls == []


@pytest.mark.parametrize(
    ("patch", "field"),
    [
        ({"budget_dollars": float("nan")}, "budget_dollars"),
        ({"budget_dollars": float("inf")}, "budget_dollars"),
        ({"budget_dollars": True}, "budget_dollars"),
        ({"budget_dollars": "300"}, "budget_dollars"),
        ({"budget_dollars": -5}, "budget_today"),
        ({"max_width_inches": 0}, "max_width_in"),
        ({"within_days": 2.5}, "within_days"),
        ({"timeframe": "next_year"}, "timeframe"),
        ({"conditions": "used"}, "conditions"),
        ({"conditions": ["like new"]}, "conditions"),
    ],
)
def test_a_bad_reply_gives_empty_filters_and_the_errors(patch: dict, field: str) -> None:
    filters, errors = parse_request_with_errors("x", FakeGrokClient({**EMPTY_REPLY, **patch}))
    assert filters == ShopFilters()
    assert any(e.startswith(field) for e in errors), errors


@pytest.mark.parametrize("timeframe", [["this_week"], {"days": 7}, 7])
def test_a_timeframe_that_is_not_text_gives_empty_filters(timeframe: object) -> None:
    filters, errors = parse_request_with_errors("x", FakeGrokClient({**EMPTY_REPLY, "timeframe": timeframe}))
    assert filters == ShopFilters()
    assert errors == ["timeframe: not text"]


@pytest.mark.parametrize("conditions", [[{}], [["new"]], ["new", 1]])
def test_conditions_that_are_not_text_give_empty_filters(conditions: list) -> None:
    filters, errors = parse_request_with_errors("x", FakeGrokClient({**EMPTY_REPLY, "conditions": conditions}))
    assert filters == ShopFilters()
    assert errors == ["conditions: not a list of text"]


def test_a_reply_that_is_not_an_object_gives_empty_filters() -> None:
    filters, errors = parse_request_with_errors("x", FakeGrokClient(["not", "an", "object"]))
    assert filters == ShopFilters()
    assert errors == ["Grok's reply could not be read. Set the filters by hand."]


_REQUEST = httpx.Request("POST", "https://api.x.ai/v1/chat/completions")


@pytest.mark.parametrize(
    ("exc", "message"),
    [
        (httpx.ConnectError("boom", request=_REQUEST), "Could not reach Grok"),
        (httpx.HTTPStatusError("bad", request=_REQUEST, response=httpx.Response(401, request=_REQUEST)), "HTTP 401"),
        (json.JSONDecodeError("Expecting value", "", 0), "reply could not be read"),
        (RuntimeError("unexpected"), "Parsing failed"),
    ],
)
def test_client_failures_give_empty_filters_and_a_plain_message(exc: Exception, message: str) -> None:
    filters, errors = parse_request_with_errors("about $300", RaisingClient(exc))
    assert filters == ShopFilters()
    assert len(errors) == 1 and message in errors[0]


def test_parse_request_returns_the_filters_only() -> None:
    text = "about $300, small space, need it this week"
    assert parse_request(text, FakeGrokClient(RECORDED[text])) == _parse(text)[0]
    assert parse_request("x", RaisingClient(RuntimeError())) == ShopFilters()
