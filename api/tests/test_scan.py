"""Grok scan: fake client + recorded fixtures, never the network (PLAN.md 3.7)."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image, UnidentifiedImageError

from app.grok import client as client_module
from app.grok.client import GrokClient, shrink_jpeg
from app.grok.scan import _SCHEMAS, scan
from app.models import ScanKind

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "scan"
JPEG = b"\xff\xd8\xff\xd9"  # stand-in bytes; the fake client never decodes them

KIND_FIXTURES: dict[ScanKind, str] = {
    "label": "label_valid.json",
    "price_tag": "price_tag_valid.json",
    "lease": "lease_valid.json",
    "listing": "listing_valid.json",
}


class FakeGrokClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def chat_json(self, system: str, user: str, image_jpeg: bytes | None = None, schema: dict | None = None) -> dict:
        self.calls.append({"system": system, "user": user, "image": image_jpeg, "schema": schema})
        return self.payload


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _png(width: int, height: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), (200, 180, 40)).save(out, format="PNG")
    return out.getvalue()


def test_label_valid_reads_year_and_label_kwh() -> None:
    client = FakeGrokClient(_load("label_valid.json"))
    result = scan("label", JPEG, client)
    assert result.valid is True
    assert result.errors == []
    assert result.item is not None
    assert (result.item.brand, result.item.model, result.item.serial) == ("GE", "GTS18GSNRSS", "FG123456A")
    assert result.item.mfg_year == 2016
    assert result.item.year_confidence == "none"  # only a serial decode sets it; a printed year is taken as is
    assert result.item.id == "scan-label"
    assert result.item.attributes == {"product_class": "3", "volume_cuft": 18.1, "label_kwh_per_year": 369.0}
    assert result.offer is None and result.lease is None
    assert client.calls[0]["image"] == JPEG
    assert client.calls[0]["schema"] == _SCHEMAS["label"]


def test_label_with_unprinted_fields_as_null_is_valid() -> None:
    payload = {**_load("label_valid.json"), "serial": None, "mfg_year": None, "label_kwh_per_year": None}
    result = scan("label", JPEG, FakeGrokClient(payload))
    assert result.valid is True
    assert result.item is not None
    assert result.item.serial is None
    assert result.item.mfg_year is None
    assert result.item.year_confidence == "none"
    assert "label_kwh_per_year" not in result.item.attributes


def test_price_tag_valid() -> None:
    result = scan("price_tag", JPEG, FakeGrokClient(_load("price_tag_valid.json")))
    assert result.valid is True
    assert result.item is not None
    assert (result.item.brand, result.item.model, result.item.condition) == ("Whirlpool", "WRT318FZDB", "new")
    assert result.offer is not None
    assert result.offer.price == 698.0
    assert result.offer.source == "price_tag"


def test_lease_valid_turns_the_printed_percent_into_a_fraction() -> None:
    result = scan("lease", JPEG, FakeGrokClient(_load("lease_valid.json")))
    assert result.valid is True
    assert result.lease is not None
    assert (result.lease.weekly_payment, result.lease.term_weeks, result.lease.cash_price) == (30.0, 52, 800.0)
    assert result.lease.early_purchase_rule == "pct_of_remaining"
    assert result.lease.early_purchase_pct == 0.5
    assert result.lease.early_purchase_text == "Pay 50% of the remaining balance to own"
    assert result.lease.source_id == "user_lease"


def test_lease_reads_the_leased_fridge_and_prices_its_offer_at_the_cash_price() -> None:
    result = scan("lease", JPEG, FakeGrokClient(_load("lease_valid.json")))
    assert result.item is not None
    assert (result.item.brand, result.item.model) == ("Frigidaire", "FRTE1936AV")
    assert result.offer is not None
    assert result.offer.item_id == result.item.id
    assert result.offer.seller_type == "rent_to_own"
    assert result.offer.price == 800.0


def test_lease_without_brand_and_model_is_invalid() -> None:
    payload = {**_load("lease_valid.json"), "brand": None, "model": None}
    result = scan("lease", JPEG, FakeGrokClient(payload))
    assert result.valid is False
    assert "brand: missing" in result.errors
    assert "model: missing" in result.errors
    assert result.item is None and result.offer is None and result.lease is None
    assert result.fields["cash_price"] == 800.0


def test_lease_missing_term_is_invalid_and_keeps_what_was_read_in_fields() -> None:
    payload = {**_load("lease_valid.json"), "term_weeks": None}
    result = scan("lease", JPEG, FakeGrokClient(payload))
    assert result.valid is False
    assert "term_weeks: missing" in result.errors
    assert result.item is None and result.offer is None and result.lease is None
    assert result.fields["weekly_payment"] == 30.0
    assert result.fields["cash_price"] == 800.0
    assert "term_weeks" not in result.fields
    sent = json.loads(result.model_dump_json())
    assert sent["fields"]["brand"] == "Frigidaire"
    assert sent["lease"] is None


def test_lease_keeps_todays_payment_and_the_printed_total() -> None:
    payload = {**_load("lease_valid.json"), "payment_today": 0.01, "total_of_payments": 1560.0}
    result = scan("lease", JPEG, FakeGrokClient(payload))
    assert result.valid is True
    assert result.lease is not None
    assert (result.lease.payment_today, result.lease.total_of_payments) == (0.01, 1560.0)


def test_a_valid_scan_also_reports_what_was_read_in_fields() -> None:
    result = scan("listing", JPEG, FakeGrokClient(_load("listing_valid.json")))
    assert result.valid is True
    assert result.fields == {k: v for k, v in _load("listing_valid.json").items() if v is not None}


def test_listing_valid() -> None:
    result = scan("listing", JPEG, FakeGrokClient(_load("listing_valid.json")))
    assert result.valid is True
    assert result.item is not None
    assert (result.item.brand, result.item.condition) == ("Frigidaire", "used_as_is")
    assert result.item.mfg_year is None
    assert result.offer is not None
    assert result.offer.price == 250.0
    assert result.offer.source == "user_listing"


def test_label_malformed_is_invalid_and_returns_no_item() -> None:
    result = scan("label", JPEG, FakeGrokClient(_load("label_malformed.json")))
    assert result.valid is False
    assert any(e.startswith("model:") for e in result.errors)
    assert any(e.startswith("volume_cuft:") for e in result.errors)
    assert result.item is None
    assert result.fields["brand"] == "GE"
    assert result.fields["serial"] == "FG123456A"
    assert result.fields["volume_cuft"] == "eighteen"


def test_each_kind_has_its_own_prompt_and_strict_schema() -> None:
    systems = set()
    for kind, name in KIND_FIXTURES.items():
        client = FakeGrokClient(_load(name))
        scan(kind, JPEG, client)
        call = client.calls[0]
        systems.add(call["system"])
        schema = call["schema"]
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
        assert set(_load(name)) == set(schema["properties"])
    assert len(systems) == 4


def test_prompts_keep_lease_services_out_of_fees_and_descriptions_out_of_product_class() -> None:
    # Seen on the real Aaron's card and EnergyGuide labels before these rules were added.
    lease = FakeGrokClient(_load("lease_valid.json"))
    scan("lease", JPEG, lease)
    assert "never the cost of lease services" in lease.calls[0]["system"]
    label = FakeGrokClient(_load("label_valid.json"))
    scan("label", JPEG, label)
    assert "is not a code, so use null" in label.calls[0]["system"]


def test_a_stated_listing_year_does_not_claim_serial_confidence() -> None:
    result = scan("listing", JPEG, FakeGrokClient({**_load("listing_valid.json"), "mfg_year": 2015}))
    assert result.valid is True
    assert result.item is not None
    assert (result.item.mfg_year, result.item.year_confidence) == (2015, "none")


@pytest.mark.parametrize(
    ("kind", "name", "key", "value"),
    [
        ("label", "label_valid.json", "volume_cuft", float("nan")),
        ("label", "label_valid.json", "label_kwh_per_year", float("inf")),
        ("listing", "listing_valid.json", "price", float("nan")),
        ("listing", "listing_valid.json", "price", float("-inf")),
        ("lease", "lease_valid.json", "weekly_payment", float("nan")),
        ("lease", "lease_valid.json", "cash_price", float("inf")),
        ("label", "label_valid.json", "label_kwh_per_year", True),
        ("listing", "listing_valid.json", "price", True),
        ("lease", "lease_valid.json", "term_weeks", 52.5),
        ("price_tag", "price_tag_valid.json", "brand", 7),
    ],
)
def test_a_value_of_the_wrong_json_type_is_an_error_not_a_crash(kind: str, name: str, key: str, value: object) -> None:
    result = scan(kind, JPEG, FakeGrokClient({**_load(name), key: value}))
    assert result.valid is False
    assert result.item is None and result.offer is None and result.lease is None
    assert any(e.startswith(f"{key}:") for e in result.errors)
    json.loads(result.model_dump_json())  # what the API sends stays valid JSON


@pytest.mark.parametrize(("key", "value"), [("label_kwh_per_year", 0), ("volume_cuft", -3), ("volume_cuft", 0)])
def test_label_kwh_and_volume_must_be_positive(key: str, value: float) -> None:
    result = scan("label", JPEG, FakeGrokClient({**_load("label_valid.json"), key: value}))
    assert result.valid is False
    assert any(e.startswith(f"{key}:") for e in result.errors)


def test_each_kind_gets_its_own_item_id_and_the_offer_points_at_it() -> None:
    for kind, name in KIND_FIXTURES.items():
        result = scan(kind, JPEG, FakeGrokClient(_load(name)))
        assert result.item is not None
        assert result.item.id == f"scan-{kind}"
        if result.offer is not None:
            assert result.offer.item_id == result.item.id


def test_an_unread_lease_fee_is_invalid_not_zero() -> None:
    result = scan("lease", JPEG, FakeGrokClient({**_load("lease_valid.json"), "fees": None}))
    assert result.valid is False
    assert result.errors == ["fees: not printed. Enter 0 if the lease has none."]
    assert result.lease is None


def test_a_lease_fee_read_as_zero_is_valid() -> None:
    result = scan("lease", JPEG, FakeGrokClient({**_load("lease_valid.json"), "fees": 0}))
    assert result.valid is True
    assert result.lease is not None and result.lease.fees == 0


def test_a_bad_fee_is_reported_once() -> None:
    result = scan("lease", JPEG, FakeGrokClient({**_load("lease_valid.json"), "fees": True}))
    assert result.errors == ["fees: not a number"]


@pytest.mark.parametrize("kind", ["label", "listing", "price_tag", "lease"])
def test_blank_brand_and_model_are_not_printed(kind: str) -> None:
    payload = {**_load(KIND_FIXTURES[kind]), "brand": " ", "model": "\t "}
    result = scan(kind, JPEG, FakeGrokClient(payload))
    assert result.valid is False
    assert "brand: missing" in result.errors
    assert "model: missing" in result.errors
    assert result.item is None
    assert "brand" not in result.fields and "model" not in result.fields


def test_printed_text_is_stripped() -> None:
    payload = {**_load("listing_valid.json"), "brand": "  Frigidaire ", "model": " FFTR1835VS\n"}
    result = scan("listing", JPEG, FakeGrokClient(payload))
    assert result.valid is True
    assert result.item is not None
    assert (result.item.brand, result.item.model) == ("Frigidaire", "FFTR1835VS")
    assert (result.fields["brand"], result.fields["model"]) == ("Frigidaire", "FFTR1835VS")


def test_true_in_a_number_field_stays_out_of_fields() -> None:
    result = scan("listing", JPEG, FakeGrokClient({**_load("listing_valid.json"), "price": True}))
    assert result.valid is False
    assert "price" not in result.fields


def test_a_failed_condition_is_not_also_reported_missing() -> None:
    result = scan("listing", JPEG, FakeGrokClient({**_load("listing_valid.json"), "condition": "excellent"}))
    assert result.valid is False
    assert any(e.startswith("condition:") for e in result.errors)
    assert "condition: missing" not in result.errors


def test_a_refurbished_listing_is_sold_by_a_refurbisher() -> None:
    result = scan("listing", JPEG, FakeGrokClient({**_load("listing_valid.json"), "condition": "refurbished"}))
    assert result.valid is True
    assert result.item is not None and result.item.condition == "refurbished"
    assert result.offer is not None and result.offer.seller_type == "refurbisher"


class RaisingClient:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def chat_json(self, *_args, **_kwargs) -> dict:
        raise self.exc


_REQUEST = httpx.Request("POST", "https://api.x.ai/v1/chat/completions")


@pytest.mark.parametrize(
    ("exc", "message"),
    [
        (httpx.ConnectError("boom", request=_REQUEST), "Could not reach Grok"),
        (httpx.ReadTimeout("slow", request=_REQUEST), "Could not reach Grok"),
        (
            httpx.HTTPStatusError("bad", request=_REQUEST, response=httpx.Response(400, request=_REQUEST)),
            "HTTP 400",
        ),
        (json.JSONDecodeError("Expecting value", "not json", 0), "reply could not be read"),
        (KeyError("choices"), "reply could not be read"),
        (UnidentifiedImageError("cannot identify image file"), "image could not be read"),
        (RuntimeError("unexpected"), "The scan failed"),
    ],
)
def test_client_failures_become_an_invalid_result_with_a_plain_message(exc: Exception, message: str) -> None:
    result = scan("label", JPEG, RaisingClient(exc))
    assert result.valid is False
    assert len(result.errors) == 1
    assert message in result.errors[0]
    assert result.item is None and result.offer is None and result.lease is None


def test_a_non_image_upload_through_the_real_client_is_a_plain_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_module, "load_dotenv", lambda *_a, **_k: None)
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setenv("XAI_MODEL", "grok-4.20-0309-non-reasoning")
    result = scan("label", b"not an image", GrokClient())
    assert result.valid is False
    assert result.errors == ["The image could not be read. Use a JPEG or PNG photo."]


def test_shrink_caps_the_long_edge_and_returns_jpeg() -> None:
    out = shrink_jpeg(_png(4000, 3000))
    with Image.open(io.BytesIO(out)) as img:
        assert img.format == "JPEG"
        assert max(img.size) == 1600
        assert img.size == (1600, 1200)


def test_payload_asks_for_the_schema_and_sends_a_shrunk_jpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_module, "load_dotenv", lambda *_a, **_k: None)
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setenv("XAI_MODEL", "grok-4.20-0309-non-reasoning")
    payload = GrokClient().build_payload("sys", "user", _png(3200, 2400), schema=_SCHEMAS["label"])
    assert payload["model"] == "grok-4.20-0309-non-reasoning"
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["schema"] == _SCHEMAS["label"]
    assert payload["response_format"]["json_schema"]["strict"] is True
    url = payload["messages"][1]["content"][1]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    with Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))) as img:
        assert max(img.size) == 1600
