"""Retailer cache: real new offers with URL, date, and a resolvable source (task 2.3)."""

from __future__ import annotations

import json
import pathlib

from pydantic import TypeAdapter

from app.models import Item, Offer
from app.repository import DATA_DIR, Repository

CACHE_PATH = DATA_DIR / "retailer_cache.json"


def _load_raw() -> dict:
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def test_cache_file_exists() -> None:
    assert CACHE_PATH.is_file()


def test_offer_count_in_range() -> None:
    raw = _load_raw()
    n = len(raw["offers"])
    assert 8 <= n <= 15, n


def test_every_offer_validates_has_url_and_date() -> None:
    raw = _load_raw()
    offers = TypeAdapter(list[Offer]).validate_python(raw["offers"])
    assert offers
    for o in offers:
        assert o.source == "retailer_cache"
        assert o.seller_type == "retailer"
        assert o.url and o.url.startswith("https://"), o.item_id
        assert o.retrieved_at is not None, o.item_id
        assert o.price >= 0


def test_every_offer_source_resolves() -> None:
    repo = Repository.load()
    ids = {s.id for s in repo.sources()}
    for o in repo.new_offers("refrigerator"):
        assert o.source_id in ids, o.source_id
        assert repo.source(o.source_id).id == o.source_id


def test_every_offer_has_matching_item_with_required_attrs() -> None:
    raw = _load_raw()
    items = {i.id: i for i in TypeAdapter(list[Item]).validate_python(raw["items"])}
    offers = TypeAdapter(list[Offer]).validate_python(raw["offers"])
    for o in offers:
        item = items[o.item_id]
        assert item.category == "refrigerator"
        assert item.condition == "new"
        assert item.brand and item.model
        attrs = item.attributes
        assert "product_class" in attrs
        assert isinstance(attrs["volume_cuft"], (int, float)) and attrs["volume_cuft"] > 0
        assert isinstance(attrs["width_in"], (int, float)) and attrs["width_in"] > 0


def test_repository_loads_new_offers() -> None:
    repo = Repository.load()
    offers = repo.new_offers("refrigerator")
    assert 8 <= len(offers) <= 15
    for o in offers:
        item = repo.item(o.item_id)
        assert item is not None
        assert item.condition == "new"


def test_every_model_noted_or_in_energystar_csv() -> None:
    raw = _load_raw()
    notes = raw.get("energystar_notes") or {}
    csv_path = DATA_DIR / "energystar_refrigerators.csv"
    csv_models: set[str] = set()
    if csv_path.is_file():
        lines = csv_path.read_text(encoding="utf-8").splitlines()
        # brand,model_number,model_normalized,annual_kwh
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split(",")
            if len(parts) >= 2:
                csv_models.add(parts[1].strip())
                if len(parts) >= 3:
                    csv_models.add(parts[2].strip())

    items = TypeAdapter(list[Item]).validate_python(raw["items"])
    for item in items:
        in_csv = item.model in csv_models
        noted = notes.get(item.model) == "missing" or str(notes.get(item.model, "")).startswith("missing")
        assert in_csv or noted, f"{item.model} neither in CSV nor noted missing"
