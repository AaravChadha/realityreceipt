import re

import pytest

from app.engine.running import aging_line, carbon_kg, energy, upkeep
from app.models import MONTHS, ModelEnergy, RateValue, UpkeepItem

RATE = RateValue(value=0.15, source_id="ga_power_residential_tariff")
RATED_600 = ModelEnergy(kwh_per_year=600, source_type="rated", source_id="energystar_refrigerators")


def test_energy_600_kwh_at_15_cents() -> None:
    c = energy(RATED_600, RATE)
    assert c.monthly_low == [7.50] * MONTHS
    assert c.monthly_high == [7.50] * MONTHS
    assert sum(c.monthly_low) == pytest.approx(270.00)
    assert sum(c.monthly_high) == pytest.approx(270.00)
    assert c.pay_today == 0.0


def test_energy_has_one_running_line_with_the_kwh_source() -> None:
    [line] = energy(RATED_600, RATE).lines
    assert line.kind == "running"
    assert line.source_type == "rated"
    assert line.source_id == "energystar_refrigerators"
    assert (line.amount_low, line.amount_high, line.period) == (90.0, 90.0, "year")
    assert "600 kWh/yr" in line.formula and "$0.15/kWh" in line.formula


def test_energy_names_the_rate_source_only_when_estimated() -> None:
    ceiling = ModelEnergy(kwh_per_year=660, source_type="published", source_id="doe_standards_refrigerators")
    unknown = ModelEnergy(kwh_per_year=0, source_type="not_estimated", source_id="none")
    for kwh in (RATED_600, ceiling):
        [line] = energy(kwh, RATE).lines
        assert line.source_id == kwh.source_id
        assert line.other_source_ids == ["ga_power_residential_tariff"]
    [blank] = energy(unknown, RATE).lines
    assert blank.other_source_ids == []


def test_energy_published_ceiling_is_labeled_up_to_when_new() -> None:
    ceiling = ModelEnergy(kwh_per_year=660, source_type="published", source_id="doe_standards_refrigerators")
    [line] = energy(ceiling, RATE).lines
    assert line.source_type == "published"
    assert line.label == "Electricity, up to when new"


def test_energy_not_estimated_kwh_stays_blank() -> None:
    unknown = ModelEnergy(kwh_per_year=0, source_type="not_estimated", source_id="none")
    c = energy(unknown, RATE)
    assert c.monthly_low == [0.0] * MONTHS and c.monthly_high == [0.0] * MONTHS
    [line] = c.lines
    assert line.source_type == "not_estimated"
    assert line.amount_low is None and line.amount_high is None


def test_energy_stops_after_months() -> None:
    c = energy(RATED_600, RATE, months=20)
    assert c.monthly_low[:20] == [7.50] * 20
    assert c.monthly_low[20:] == [0.0] * 16
    with pytest.raises(ValueError):
        energy(RATED_600, RATE, months=37)


def test_aging_line_is_not_estimated() -> None:
    line = aging_line()
    assert line.kind == "running"
    assert line.label == "Extra use from age"
    assert line.source_type == "not_estimated"
    assert line.amount_low is None and line.amount_high is None


def test_carbon_600_kwh_at_0_4_kg_over_36_months() -> None:
    assert carbon_kg(600, RateValue(value=0.4, source_id="egrid_georgia")) == pytest.approx(720.0)
    assert carbon_kg(600, RateValue(value=0.4, source_id="egrid_georgia"), months=12) == pytest.approx(240.0)


def test_upkeep_falls_due_every_n_months_never_today() -> None:
    filter_ = UpkeepItem(label="Water filter", cost_low=30, cost_high=50, every_months=12, source_id="upkeep_src")
    c = upkeep([filter_])
    due = [m for m in range(MONTHS) if c.monthly_high[m]]
    assert due == [12, 24]
    assert c.monthly_low[12] == 30.0 and c.monthly_high[12] == 50.0
    assert c.pay_today == 0.0
    [line] = c.lines
    assert line.kind == "upkeep"
    assert (line.amount_low, line.amount_high, line.period) == (60.0, 100.0, "window")
    assert line.source_type == "published" and line.source_id == "upkeep_src"
    assert sum(c.monthly_low) == pytest.approx(line.amount_low)
    assert sum(c.monthly_high) == pytest.approx(line.amount_high)


def test_upkeep_empty_or_out_of_window_adds_nothing() -> None:
    for schedule in ([], [UpkeepItem(label="Coils", cost_low=10, cost_high=20, every_months=36, source_id="s")]):
        c = upkeep(schedule)
        assert c.monthly_low == [0.0] * MONTHS and c.monthly_high == [0.0] * MONTHS
        assert c.lines == []


def test_copy_has_no_em_dash_or_apr() -> None:
    ceiling = ModelEnergy(kwh_per_year=660, source_type="published", source_id="doe_standards_refrigerators")
    item = UpkeepItem(label="Water filter", cost_low=30, cost_high=50, every_months=6, source_id="s")
    lines = [*energy(RATED_600, RATE).lines, *energy(ceiling, RATE).lines, aging_line(), *upkeep([item]).lines]
    for line in lines:
        for text in (line.label, line.formula):
            assert "—" not in text and "APR" not in text and "qualif" not in text.lower()


# The electricity formula: "<kWh> kWh/yr x $<rate>/kWh = $<per year>/yr, $<per month>/month".
FORMULA = re.compile(r"([\d,.]+) kWh/yr x \$([\d.]+)/kWh = \$([\d,.]+)/yr, \$([\d,.]+)/month")
GA_RATE = RateValue(value=0.15641, source_id="ga_power_residential_tariff")  # the rate recorded in rates.json


def test_electricity_formula_reproduces_its_own_amount() -> None:
    [line] = energy(ModelEnergy(kwh_per_year=633, source_type="rated", source_id="s"), GA_RATE).lines
    assert "$0.15641/kWh" in line.formula
    wrong = []
    for kwh_per_year in [*range(300, 901), 399.135, 512.3456789, 1234.5]:
        [line] = energy(ModelEnergy(kwh_per_year=kwh_per_year, source_type="rated", source_id="s"), GA_RATE).lines
        match = FORMULA.fullmatch(line.formula)
        assert match, line.formula
        kwh, rate, per_year, per_month = (float(g.replace(",", "")) for g in match.groups())
        # Recomputed only from the numbers printed in the formula.
        if not (round(kwh * rate, 2) == per_year == line.amount_high and round(kwh / 12 * rate, 2) == per_month):
            wrong.append(line.formula)
    assert wrong == []


ICEMAKER_NOTE = (
    "DOE lists this model at two figures one icemaker apart; the lower is taken for a unit without an automatic icemaker"
)


def test_a_note_on_the_kwh_figure_goes_in_the_formula_with_its_sources() -> None:
    noted = ModelEnergy(
        kwh_per_year=505, source_type="rated", source_id="doe_wap_refrigerators",
        note=ICEMAKER_NOTE, note_source_ids=["doe_standards_refrigerators"],
    )
    [line] = energy(noted, RATE).lines
    assert line.formula.endswith(f"/month. {ICEMAKER_NOTE}")
    assert line.source_id == "doe_wap_refrigerators"
    assert line.other_source_ids == ["ga_power_residential_tariff", "doe_standards_refrigerators"]
    # A figure with no note is unchanged.
    [plain] = energy(RATED_600, RATE).lines
    assert plain.formula.endswith("/month")
    assert plain.other_source_ids == ["ga_power_residential_tariff"]
