"""Demo cards run through the real pipeline (PLAN.md task 3.13.1)."""

import json
from pathlib import Path as FilePath

import pytest

from app.models import Item, Lease, Offer
from app.repository import Repository

CARDS_DIR = FilePath(__file__).resolve().parents[2] / "demo" / "cards"
CARDS = json.loads((CARDS_DIR / "cards.json").read_text())["cards"]
FRIDGE_CARDS = [c for c in CARDS if c["kind"] in ("label", "listing")]
LEASE_CARDS = [c for c in CARDS if c["kind"] == "lease"]


@pytest.fixture(scope="module")
def repo() -> Repository:
    return Repository.load()


def _landed(task: str, repo: Repository) -> bool:
    """Whether the repository feature a card depends on is on main yet."""
    if task == "2.2.1":
        return repo.model_energy("GE", "GTE18FSL****") is not None
    if task == "2.2.2":
        return hasattr(repo, "model_year")
    raise AssertionError(f"unknown dependency {task}")


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


@pytest.mark.parametrize("card", FRIDGE_CARDS, ids=lambda c: c["file"])
def test_fridge_card_model_returns_a_rated_figure(card: dict, repo: Repository) -> None:
    needs = card.get("needs")
    if needs and not _landed(needs, repo):
        pytest.skip(f"needs task {needs} on main")
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
