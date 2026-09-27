"""The vertical slice on the committed data (PLAN.md task 2.6): each demo fridge card, typed,
plus a used listing, through `quote` on the real `Repository`.

The listing card carries its own offer; a label card shows no price, so its unit is listed
at $250. The demo cards and their typed equivalents are in `demo/cards/cards.json` (3.13.1).
"""

import json
from pathlib import Path as FilePath

import pytest

from app.engine.quote import GRID_EMISSIONS, INCOMPLETE, quote
from app.models import Item, Offer, Path, QuoteRequest
from app.repository import Repository

CARDS = json.loads((FilePath(__file__).resolve().parents[2] / "demo" / "cards" / "cards.json").read_text())["cards"]
FRIDGE_CARDS = {card["file"]: card for card in CARDS if card["kind"] in ("label", "listing")}
LABEL_CARD_PRICE = 250.0


@pytest.fixture(scope="module")
def repo() -> Repository:
    return Repository.load()


def slice_request(card: dict) -> tuple[Item, QuoteRequest]:
    item = Item.model_validate(card["typed"]["item"])
    if "offer" in card["typed"]:
        offer = Offer.model_validate(card["typed"]["offer"])
    else:
        offer = Offer(item_id=item.id, price=LABEL_CARD_PRICE, seller_type="private", source="user_listing", source_id="user_listing")
    return item, QuoteRequest(items=[item], offers=[offer])


@pytest.fixture(scope="module", params=sorted(FRIDGE_CARDS))
def card(request: pytest.FixtureRequest, repo: Repository) -> tuple[Item, list[Path]]:
    item, req = slice_request(FRIDGE_CARDS[request.param])
    return item, quote(req, repo)


def test_there_are_demo_fridge_cards() -> None:
    assert {c["kind"] for c in FRIDGE_CARDS.values()} == {"label", "listing"}


def test_both_groups(card: tuple[Item, list[Path]]) -> None:
    _, paths = card
    assert {"used_as_is", "new"} <= {p.group for p in paths}
    assert [p.group for p in paths].count("used_as_is") == 1
    assert ("new", "cash") in {(p.group, p.payment_method) for p in paths}


def test_every_line_is_sourced(card: tuple[Item, list[Path]], repo: Repository) -> None:
    _, paths = card
    known = {s.id for s in repo.sources()} | {"user", "user_listing"}
    for p in paths:
        for line in p.lines:
            assert (line.source_id is None) == (line.source_type == "not_estimated"), line
            assert line.source_id is None or line.source_id in known, line.source_id
            assert set(line.other_source_ids) <= known, line.other_source_ids
        assert set(p.carbon_source_ids) <= known, p.carbon_source_ids


def test_nothing_is_fixture(card: tuple[Item, list[Path]]) -> None:
    _, paths = card
    assert paths
    assert not any("fixture" in p.flags for p in paths)


def test_new_cash_is_the_cheapest_cached_offer(card: tuple[Item, list[Path]], repo: Repository) -> None:
    _, paths = card
    cheapest = min(repo.new_offers("refrigerator"), key=lambda o: o.price)
    [new_cash] = [p for p in paths if (p.group, p.payment_method) == ("new", "cash")]
    [price] = [line for line in new_cash.lines if line.kind == "purchase"]
    assert (price.amount_high, price.source_id) == (round(cheapest.price, 2), cheapest.source_id)
    assert new_cash.pay_today == round(cheapest.price, 2)


def test_used_unit_energy_comes_from_the_model_lookup(card: tuple[Item, list[Path]], repo: Repository) -> None:
    item, paths = card
    [used] = [p for p in paths if p.group == "used_as_is"]
    rated = repo.model_energy(item.brand, item.model)
    assert rated is not None, f"demo card model {item.brand} {item.model} has no rated figure"
    electricity = used.lines[1]
    assert electricity.label.startswith("Electricity")
    assert (electricity.source_type, electricity.source_id) == ("rated", rated.source_id)
    assert f"{rated.kwh_per_year:g} kWh/yr" in electricity.formula
    assert used.carbon_source_ids[0] == rated.source_id
    assert used.carbon_source_ids[-1] == repo.rate(GRID_EMISSIONS).source_id


def test_used_unit_has_the_blank_aging_line(card: tuple[Item, list[Path]]) -> None:
    _, paths = card
    [used] = [p for p in paths if p.group == "used_as_is"]
    [aging] = [line for line in used.lines if line.label == "Extra use from age"]
    assert (aging.source_type, aging.amount_low, aging.amount_high) == ("not_estimated", None, None)


def test_paths_are_sorted_complete_first(card: tuple[Item, list[Path]]) -> None:
    # PLAN.md sort-order Verdict: complete paths by total (high end) then pay today, then the
    # paths flagged costs_not_estimated in the same order.
    _, paths = card
    keys = [(INCOMPLETE in p.flags, p.total_3yr_high, p.pay_today) for p in paths]
    assert keys == sorted(keys)
