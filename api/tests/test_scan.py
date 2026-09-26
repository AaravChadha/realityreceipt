"""Grok scan: fake client + recorded fixtures, never the network (PLAN.md 3.7)."""

from __future__ import annotations

import json
from pathlib import Path

from app.grok.scan import scan
from app.models import ScanKind

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "scan"
JPEG = b"\xff\xd8\xff\xd9"  # minimal stand-in; client is faked


class FakeGrokClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str, bytes | None]] = []

    def chat_json(self, system: str, user: str, image_jpeg: bytes | None = None) -> dict:
        self.calls.append((system, user, image_jpeg))
        return self.payload


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_label_valid() -> None:
    client = FakeGrokClient(_load("label_valid.json"))
    result = scan("label", JPEG, client)
    assert result.valid is True
    assert result.errors == []
    assert result.item is not None
    assert result.item.brand == "GE"
    assert result.item.model == "GTS18GSNRSS"
    assert result.item.serial == "FG123456A"
    assert result.item.attributes["product_class"] == "top_freezer"
    assert result.item.attributes["volume_cuft"] == 18.1
    assert result.offer is None
    assert result.lease is None
    assert len(client.calls) == 1
    assert client.calls[0][2] == JPEG


def test_price_tag_valid() -> None:
    result = scan("price_tag", JPEG, FakeGrokClient(_load("price_tag_valid.json")))
    assert result.valid is True
    assert result.item is not None
    assert result.item.brand == "Whirlpool"
    assert result.item.model == "WRT318FZDB"
    assert result.item.condition == "new"
    assert result.offer is not None
    assert result.offer.price == 698.0
    assert result.offer.source == "price_tag"


def test_lease_valid() -> None:
    result = scan("lease", JPEG, FakeGrokClient(_load("lease_valid.json")))
    assert result.valid is True
    assert result.lease is not None
    assert result.lease.weekly_payment == 30.0
    assert result.lease.term_weeks == 52
    assert result.lease.cash_price == 800.0
    assert result.lease.early_purchase_rule == "pct_of_remaining"
    assert result.lease.early_purchase_pct == 0.5
    assert "50%" in result.lease.early_purchase_text


def test_listing_valid() -> None:
    result = scan("listing", JPEG, FakeGrokClient(_load("listing_valid.json")))
    assert result.valid is True
    assert result.item is not None
    assert result.item.brand == "Frigidaire"
    assert result.item.condition == "used_as_is"
    assert result.offer is not None
    assert result.offer.price == 250.0
    assert result.offer.source == "user_listing"


def test_label_malformed_keeps_partial_fields() -> None:
    result = scan("label", JPEG, FakeGrokClient(_load("label_malformed.json")))
    assert result.valid is False
    assert result.errors  # model type + volume_cuft type + model missing
    assert result.item is not None
    assert result.item.brand == "GE"
    assert result.item.serial == "FG123456A"
    assert result.item.attributes.get("product_class") == "top_freezer"
    # Bad model / volume must not be invented or force-coerced into the item.
    assert result.item.model == ""
    assert "volume_cuft" not in result.item.attributes


def test_each_kind_uses_its_own_system_prompt() -> None:
    kinds: list[ScanKind] = ["label", "price_tag", "lease", "listing"]
    files = {
        "label": "label_valid.json",
        "price_tag": "price_tag_valid.json",
        "lease": "lease_valid.json",
        "listing": "listing_valid.json",
    }
    systems: list[str] = []
    for kind in kinds:
        client = FakeGrokClient(_load(files[kind]))
        scan(kind, JPEG, client)
        systems.append(client.calls[0][0])
    assert len(set(systems)) == 4
