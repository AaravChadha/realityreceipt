"""Demo cards run through the real pipeline (PLAN.md task 3.13.1)."""

import json
from pathlib import Path as FilePath
from typing import Any

import pytest

from app.models import Item, Lease, Offer
from app.repository import Repository

CARDS_DIR = FilePath(__file__).resolve().parents[2] / "demo" / "cards"
CARDS = json.loads((CARDS_DIR / "cards.json").read_text())["cards"]
FRIDGE_CARDS = [c for c in CARDS if c["kind"] in ("label", "listing")]
LEASE_CARDS = [c for c in CARDS if c["kind"] == "lease"]

# The condition a scan of each kind gives the item when the card prints none.
SCAN_CONDITION = {"label": "used_as_is", "lease": "new"}
LABEL_ATTRIBUTES = ("product_class", "volume_cuft", "label_kwh_per_year")
LEASE_FIELDS = (
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


@pytest.fixture(scope="module")
def repo() -> Repository:
    return Repository.load()


def _corrected(card: dict) -> dict[str, Any]:
    fields = dict(card["printed"])
    for fix in card["corrections"]:
        assert fields[fix["field"]] == fix["printed"], f"correction to {fix['field']} does not match the card"
        assert fix["why"]
        fields[fix["field"]] = fix["typed"]
    return fields


def _expected_typed(card: dict) -> dict[str, Any]:
    """What a person types from the card: the printed fields plus the recorded corrections, nothing else."""
    kind, fields = card["kind"], _corrected(card)
    item_id = card["typed"]["item"]["id"]
    item: dict[str, Any] = {
        "id": item_id,
        "category": "refrigerator",
        "brand": fields["brand"],
        "model": fields["model"],
        "condition": fields.get("condition", SCAN_CONDITION.get(kind)),
    }
    if "mfg_year" in fields:
        item["mfg_year"] = fields["mfg_year"]
    if kind == "label":
        item["attributes"] = {k: fields[k] for k in LABEL_ATTRIBUTES if k in fields}
    out: dict[str, Any] = {"item": Item.model_validate(item)}
    if kind == "listing":
        out["offer"] = Offer.model_validate(
            {"item_id": item_id, "price": fields["price"], "seller_type": "private",
             "source": "user_listing", "source_id": "user_listing"}
        )
    if kind == "lease":
        out["offer"] = Offer.model_validate(
            {"item_id": item_id, "price": fields["cash_price"], "seller_type": "rent_to_own",
             "source": "user_listing", "source_id": "user_listing"}
        )
        lease = {k: fields[k] for k in LEASE_FIELDS if k in fields}
        out["lease"] = Lease.model_validate({**lease, "source_id": "user_lease"})
    return out


def test_every_scenario_has_a_card() -> None:
    kinds = [c["kind"] for c in CARDS]
    assert kinds.count("label") >= 2
    assert "lease" in kinds
    assert "listing" in kinds


@pytest.mark.parametrize("card", CARDS, ids=lambda c: c["file"])
def test_card_file_exists_and_typed_equivalent_validates(card: dict) -> None:
    assert (CARDS_DIR / card["file"]).is_file()
    assert card["source_url"].startswith("https://")
    typed = card["typed"]
    item = Item.model_validate(typed["item"])
    if "offer" in typed:
        assert Offer.model_validate(typed["offer"]).item_id == item.id
    if "lease" in typed:
        Lease.model_validate(typed["lease"])


@pytest.mark.parametrize("card", CARDS, ids=lambda c: c["file"])
def test_typed_equals_printed_plus_recorded_corrections(card: dict) -> None:
    expected = _expected_typed(card)
    typed = card["typed"]
    assert set(typed) == set(expected)
    assert Item.model_validate(typed["item"]) == expected["item"]
    if "offer" in expected:
        assert Offer.model_validate(typed["offer"]) == expected["offer"]
    if "lease" in expected:
        assert Lease.model_validate(typed["lease"]) == expected["lease"]


@pytest.mark.parametrize("card", FRIDGE_CARDS, ids=lambda c: c["file"])
def test_fridge_card_model_returns_a_rated_figure(card: dict, repo: Repository) -> None:
    item = card["typed"]["item"]
    energy = repo.model_energy(item["brand"], item["model"])
    assert energy is not None, f"{item['brand']} {item['model']} has no rated figure"
    assert energy.source_type == "rated"
    printed_kwh = card["printed"].get("label_kwh_per_year")
    if printed_kwh is not None:
        assert energy.kwh_per_year == printed_kwh


@pytest.mark.parametrize("card", LEASE_CARDS, ids=lambda c: c["file"])
def test_lease_card_has_a_term_and_a_cash_price(card: dict) -> None:
    lease = Lease.model_validate(card["typed"]["lease"])
    assert lease.term_weeks > 0
    assert lease.cash_price > 0
    assert lease.term_weeks == card["printed"]["term_weeks"]
    assert lease.cash_price == card["printed"]["cash_price"]
    assert lease.weekly_payment == card["printed"]["weekly_payment"]
    assert lease.payment_today == card["printed"]["payment_today"]
    assert lease.total_of_payments == card["printed"]["total_of_payments"]
