import pathlib

import pytest
from pydantic import TypeAdapter, ValidationError

from app.models import MONTHS, CostLine, Lease, Path

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
