"""The stage numbers in PLAN.md's "Demo Script for Judges", through the real routes (tasks 4.8.3, 4.8.5).

Each scenario enters its demo card from `demo/cards/cards.json` as the presenter does, through
`/item` and `/quote` on the committed data, and checks what is said aloud. Scenario 3 posts the
filters the live request parses to straight to `/shop/rank`, so no Grok call is needed. Formulas are checked
by substring, so a formula can gain a sentence without failing here; a merge that moves a stage
number fails CI.
"""

import json
from pathlib import Path as FilePath

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.main import app
from app.models import CostLine, Path, RankedOffer

CARDS = {
    card["file"]: card["typed"]
    for card in json.loads((FilePath(__file__).resolve().parents[2] / "demo" / "cards" / "cards.json").read_text())["cards"]
}
LEASE_CARD = CARDS["lease-aarons-frigidaire-frte1936av.png"]
MAYTAG_CARD = CARDS["label-older-maytag-mb2562.png"]
REPAIR_QUOTE = 180.0  # "with a repair quote (for example $180)"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def entered(client: TestClient, item: dict) -> dict:
    response = client.post("/item", json=item)
    assert response.status_code == 200, response.text
    return response.json()


def quoted(client: TestClient, body: dict) -> list[Path]:
    response = client.post("/quote", json=body)
    assert response.status_code == 200, response.text
    return TypeAdapter(list[Path]).validate_python(response.json())


def only(lines: list[CostLine], label: str) -> CostLine:
    [line] = [line for line in lines if line.label == label]
    return line


# Scenario 1: the lease.


@pytest.fixture(scope="module")
def scenario_1(client: TestClient) -> list[Path]:
    item = entered(client, LEASE_CARD["item"])
    return quoted(client, {"items": [item], "offers": [LEASE_CARD["offer"]], "lease": LEASE_CARD["lease"]})


@pytest.fixture(scope="module")
def keep_paying(scenario_1: list[Path]) -> Path:
    [path] = [p for p in scenario_1 if p.name == "Rent-to-own, keep paying"]
    return path


def test_scenario_1_pays_one_cent_today(keep_paying: Path) -> None:
    assert keep_paying.pay_today == 0.01


def test_scenario_1_total_of_lease_payments_is_as_printed(keep_paying: Path) -> None:
    line = only(keep_paying.lines, "Total of lease payments")
    assert (line.amount_low, line.amount_high) == (1739.88, 1739.88)
    assert "$1,739.88" in line.formula


def test_scenario_1_cost_over_the_cash_price_and_effective_annual_cost(keep_paying: Path) -> None:
    formula = only(keep_paying.lines, "Total of lease payments").formula
    assert "$542.89 more than the cash price of $1,196.99" in formula
    assert "45%" in formula
    assert "APR" not in formula


def test_scenario_1_one_lease_card_after_every_complete_new_path(scenario_1: list[Path]) -> None:
    lease = [i for i, p in enumerate(scenario_1) if p.group == "rent_to_own"]
    assert [scenario_1[i].name for i in lease] == ["Rent-to-own, keep paying"]
    new_complete = [i for i, p in enumerate(scenario_1) if p.group == "new" and "costs_not_estimated" not in p.flags]
    assert new_complete, "no complete new path to compare the lease with"
    assert max(new_complete) < lease[0]


def test_scenario_1_cheapest_new_offer_is_548(scenario_1: list[Path]) -> None:
    [new_cash] = [p for p in scenario_1 if (p.group, p.payment_method) == ("new", "cash")]
    assert new_cash.pay_today == 548.0
    assert only(new_cash.lines, "Price today").amount_high == 548.0


# Scenario 2: every line has a source.


@pytest.fixture(scope="module")
def maytag(client: TestClient) -> dict:
    return entered(client, MAYTAG_CARD["item"])


@pytest.fixture(scope="module")
def maytag_repair(client: TestClient, maytag: dict) -> Path:
    paths = quoted(client, {"current": maytag, "repair_quote_low": REPAIR_QUOTE, "repair_quote_high": REPAIR_QUOTE})
    [repair] = [p for p in paths if p.group == "repair"]
    return repair


def test_scenario_2_new_fridge_is_the_closest_in_size(client: TestClient, maytag: dict) -> None:
    # Task 3.3.10, the stage line "about $8 a year": the Maytag (25.1 cu ft) is compared with the closest
    # size in the cache, a $699 GE at 21.9 cu ft, $70.54 a year against the Maytag's $78.99.
    paths = quoted(client, {"current": maytag, "repair_quote_low": REPAIR_QUOTE, "repair_quote_high": REPAIR_QUOTE})
    [cash] = [p for p in paths if (p.group, p.payment_method) == ("new", "cash")]
    [price] = [line for line in cash.lines if line.kind == "purchase"]
    assert cash.pay_today == 699.0
    assert price.formula.startswith("The closest in size to yours: 21.9 cu ft against your 25.1")
    new_electricity = next(line for line in cash.lines if line.label.startswith("Electricity"))
    [keep] = [p for p in paths if p.group == "keep"]
    old_electricity = next(line for line in keep.lines if line.label.startswith("Electricity"))
    assert (old_electricity.amount_high, new_electricity.amount_high) == (78.99, 70.54)


def test_scenario_2_electricity_is_rated_505_kwh_from_doe(client: TestClient, maytag_repair: Path) -> None:
    line = only(maytag_repair.lines, "Electricity")
    assert (line.source_type, line.source_id) == ("rated", "doe_wap_refrigerators")
    assert line.formula.startswith("505 kWh/yr x $")
    # "times the Georgia Power rate (tap through to both sources)"
    sources = {s["id"] for s in client.get("/sources").json()}
    assert {line.source_id, *line.other_source_ids} <= sources
    assert len(line.other_source_ids) == 1


def test_scenario_2_replacement_is_not_estimated(maytag_repair: Path) -> None:
    line = only(maytag_repair.lines, "Replacement when it wears out")
    assert (line.source_type, line.amount_low, line.amount_high) == ("not_estimated", None, None)
    assert "past_typical_life" in maytag_repair.flags


def test_scenario_2_states_no_year(maytag: dict, maytag_repair: Path) -> None:
    assert maytag["mfg_year"] is None
    # The two flag sentences the script says are shown, both true.
    assert {"year_from_rating_data", "test_procedure_changed"} <= set(maytag_repair.flags)


# Scenario 3: new offers ranked by cost per year, asked in plain words.

# "About $300, small space, need it this week." as Grok parsed it live (PLAN.md, 23:25 measurement).
SCENARIO_3_FILTERS = {"budget_today": 300, "need_within_days": 7}


@pytest.fixture(scope="module")
def scenario_3(client: TestClient) -> list[RankedOffer]:
    response = client.post("/shop/rank", json={"filters": SCENARIO_3_FILTERS})
    assert response.status_code == 200, response.text
    ranked = TypeAdapter(list[RankedOffer]).validate_python(response.json())
    assert ranked, "the shop ranked no offers"
    return ranked


def offer_at(ranked: list[RankedOffer], price: float, per_year: float) -> int:
    """Index of the offer at `price` costing `per_year` a year (two offers cost $649.99)."""
    [index] = [i for i, r in enumerate(ranked) if r.offer.price == price and r.path.cost_per_year_high == per_year]
    return index


def test_scenario_3_every_offer_is_flagged_over_budget(scenario_3: list[RankedOffer]) -> None:
    assert all("over_budget_today" in r.path.flags for r in scenario_3)


def test_scenario_3_first_is_548_at_98_46_a_year(scenario_3: list[RankedOffer]) -> None:
    first = scenario_3[0]
    assert first.offer.price == 548.0
    assert (first.path.cost_per_year_low, first.path.cost_per_year_high) == (98.46, 98.46)


def test_scenario_3_ranks_by_cost_per_year_not_price(scenario_3: list[RankedOffer]) -> None:
    # The $649.99 fridge at $106.31 a year ranks above the $599 one at $110.21.
    assert offer_at(scenario_3, 649.99, 106.31) < offer_at(scenario_3, 599.0, 110.21)
