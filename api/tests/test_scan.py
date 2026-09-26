"""Grok scan: fake client + recorded fixtures, never the network (PLAN.md 3.7)."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import pytest
from PIL import Image

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
    assert result.item.year_confidence == "high"
    assert result.item.attributes == {"product_class": "top_freezer", "volume_cuft": 18.1, "label_kwh_per_year": 369.0}
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


def test_lease_missing_term_is_invalid_and_keeps_what_parsed() -> None:
    payload = {**_load("lease_valid.json"), "term_weeks": None}
    result = scan("lease", JPEG, FakeGrokClient(payload))
    assert result.valid is False
    assert "term_weeks: missing" in result.errors
    assert result.lease is not None
    assert result.lease.weekly_payment == 30.0
    assert result.lease.cash_price == 800.0
    sent = json.loads(result.model_dump_json())
    assert sent["lease"]["weekly_payment"] == 30.0
    assert "term_weeks" not in sent["lease"]


def test_listing_valid() -> None:
    result = scan("listing", JPEG, FakeGrokClient(_load("listing_valid.json")))
    assert result.valid is True
    assert result.item is not None
    assert (result.item.brand, result.item.condition) == ("Frigidaire", "used_as_is")
    assert result.item.mfg_year is None
    assert result.offer is not None
    assert result.offer.price == 250.0
    assert result.offer.source == "user_listing"


def test_label_malformed_keeps_partial_fields() -> None:
    result = scan("label", JPEG, FakeGrokClient(_load("label_malformed.json")))
    assert result.valid is False
    assert any(e.startswith("model:") for e in result.errors)
    assert any(e.startswith("volume_cuft:") for e in result.errors)
    assert result.item is not None
    assert result.item.brand == "GE"
    assert result.item.serial == "FG123456A"
    assert result.item.attributes == {"product_class": "top_freezer"}
    assert result.item.model == ""


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
