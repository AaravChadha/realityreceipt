import pathlib
import re

import pytest
from pydantic import TypeAdapter, ValidationError

from app.models import MONTHS, CostLine, Item, Lease, ModelEnergy, Offer, Path, RepairRange, ScanResult, UpkeepItem

FIXTURE = pathlib.Path(__file__).resolve().parents[2] / "contracts" / "receipt_fridge.json"


@pytest.fixture(scope="module")
def paths() -> list[Path]:
    return TypeAdapter(list[Path]).validate_json(FIXTURE.read_text())


def test_monthly_arrays_are_36_long(paths: list[Path]) -> None:
    for p in paths:
        assert len(p.monthly_low) == MONTHS == 36
        assert len(p.monthly_high) == MONTHS


def test_not_estimated_lines_are_blank(paths: list[Path]) -> None:
    lines = [line for p in paths for line in p.lines if line.source_type == "not_estimated"]
    assert lines, "the fixture must show at least one not_estimated line"
    assert all(line.amount_low is None and line.amount_high is None for line in lines)


def test_every_group_and_source_type_is_present(paths: list[Path]) -> None:
    assert {p.group for p in paths} == {"repair", "used_as_is", "refurbished", "new", "rent_to_own"}
    assert {line.source_type for p in paths for line in p.lines} == {
        "rated", "published", "user_entered", "not_estimated"
    }


def test_fixture_can_never_pass_as_real_data(paths: list[Path]) -> None:
    assert all("fixture" in p.flags for p in paths)


def test_fixture_covers_the_edge_cases(paths: list[Path]) -> None:
    assert any(p.cost_per_year_high is None for p in paths)
    assert any(line.kind == "replacement" for p in paths for line in p.lines)


def test_every_input_of_a_multi_input_number_is_sourced(paths: list[Path]) -> None:
    electricity = [ln for p in paths for ln in p.lines if ln.label.startswith("Electricity") and ln.source_type != "not_estimated"]
    assert electricity and all(ln.other_source_ids for ln in electricity)
    assert all(len(p.carbon_source_ids) == 2 for p in paths if p.carbon_kg is not None)


def test_carbon_without_sources_is_rejected(paths: list[Path]) -> None:
    unsourced = paths[0].model_dump() | {"carbon_kg": 100.0, "carbon_source_ids": []}
    with pytest.raises(ValidationError):
        Path.model_validate(unsourced)


def test_not_estimated_with_an_amount_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CostLine(kind="running", label="x", amount_low=1.0, amount_high=None, period="year",
                 source_type="not_estimated", source_id=None, formula="x")


def test_estimated_line_needs_a_source() -> None:
    with pytest.raises(ValidationError):
        CostLine(kind="running", label="x", amount_low=1.0, amount_high=2.0, period="year",
                 source_type="rated", source_id=None, formula="x")


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Lease(weekly_payment=30, term_weeks=52, cash_price=700, apr=0.9)


def test_lease_rule_needs_its_percentage() -> None:
    with pytest.raises(ValidationError):
        Lease(weekly_payment=30, term_weeks=52, cash_price=700, early_purchase_rule="pct_of_remaining")


def test_infinite_money_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Offer(item_id="x", price=float("inf"), seller_type="retailer", source="retailer_cache", source_id="s")


def test_cost_ranges_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        UpkeepItem(label="x", cost_low=100, cost_high=10, every_months=12, source_id="s")
    with pytest.raises(ValidationError):
        RepairRange(label="x", cost_low=100, cost_high=10, source_id="s")
    assert UpkeepItem(label="x", cost_low=10, cost_high=10, every_months=12, source_id="s").cost_high == 10


def test_manufacture_year_must_be_plausible() -> None:
    with pytest.raises(ValidationError):
        Item(id="x", category="refrigerator", brand="b", model="m", condition="used_as_is", mfg_year=1800)
    with pytest.raises(ValidationError):
        Item(id="x", category="refrigerator", brand="b", model="m", condition="used_as_is", mfg_year=2999)
    assert Item(id="x", category="refrigerator", brand="b", model="m", condition="used_as_is", mfg_year=2004).mfg_year == 2004


def test_lease_term_is_bounded() -> None:
    with pytest.raises(ValidationError):
        Lease(weekly_payment=30, term_weeks=261, cash_price=700)


def test_an_invalid_scan_carries_fields_not_objects() -> None:
    lease = Lease(weekly_payment=33.48, term_weeks=52, cash_price=1196.99)
    with pytest.raises(ValidationError):
        ScanResult(kind="lease", valid=False, errors=["term_weeks: missing"], lease=lease)
    partial = ScanResult(kind="lease", valid=False, errors=["term_weeks: missing"],
                         fields={"weekly_payment": 33.48, "term_weeks": None, "cash_price": 1196.99})
    assert ScanResult.model_validate_json(partial.model_dump_json()) == partial


def test_a_valid_scan_has_no_errors() -> None:
    with pytest.raises(ValidationError):
        ScanResult(kind="label", valid=True, errors=["model: missing"])


def test_a_lease_keeps_its_printed_numbers() -> None:
    lease = Lease(weekly_payment=33.48, term_weeks=52, cash_price=1196.99,
                  payment_today=0.01, total_of_payments=1739.88)
    assert (lease.payment_today, lease.total_of_payments) == (0.01, 1739.88)
    with pytest.raises(ValidationError):
        Lease(weekly_payment=33.48, term_weeks=52, cash_price=1196.99, total_of_payments=-1)


def test_a_payment_today_above_the_total_is_refused() -> None:
    # Task 1.8: this lease made /quote answer HTTP 500 before the contract refused it.
    with pytest.raises(ValidationError, match="does not fit"):
        Lease(weekly_payment=30, term_weeks=52, cash_price=700, payment_today=100, total_of_payments=50)
    with pytest.raises(ValidationError, match="does not fit"):
        Lease(weekly_payment=30, term_weeks=1, cash_price=700, payment_today=10, total_of_payments=30)
    assert Lease(weekly_payment=30, term_weeks=1, cash_price=700, payment_today=30, total_of_payments=30)
    assert Lease(weekly_payment=30, term_weeks=52, cash_price=700, payment_today=50, total_of_payments=50)
    assert Lease(weekly_payment=30, term_weeks=52, cash_price=700, payment_today=100)  # no total: nothing to fit


CONTRACTS_TS = pathlib.Path(__file__).resolve().parents[2] / "web" / "src" / "contracts.ts"


def test_a_kwh_figure_has_no_note_unless_a_rule_picked_it() -> None:
    energy = ModelEnergy(kwh_per_year=505, source_type="rated", source_id="doe_wap_refrigerators")
    assert (energy.note, energy.note_source_ids) == ("", [])


def test_the_web_mirror_of_model_energy_has_every_field() -> None:
    keys = re.search(r"export const MODEL_ENERGY_KEYS = \[(.*?)\]", CONTRACTS_TS.read_text(), re.S)
    assert keys is not None
    assert re.findall(r"'(\w+)'", keys.group(1)) == list(ModelEnergy.model_fields)
