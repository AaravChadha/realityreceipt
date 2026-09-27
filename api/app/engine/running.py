"""Running cost, upkeep and carbon (PLAN.md task 2.4, row A5).

Month 0 is today. Nothing here is paid at the register, so every
contribution has `pay_today == 0`. Money is rounded to cents.
"""

from app.models import MONTHS, Contribution, CostLine, ModelEnergy, RateValue, UpkeepItem


def _num(x: float) -> str:
    """600.0 -> "600", 0.15641 -> "0.15641": up to 6 decimals, no trailing zeros, so the
    numbers a formula prints reproduce its amount."""
    return f"{x:,.6f}".rstrip("0").rstrip(".")


def _check_months(months: int) -> None:
    if not 0 <= months <= MONTHS:
        raise ValueError(f"months must be between 0 and {MONTHS}, got {months}")


def energy(kwh: ModelEnergy, rate: RateValue, months: int = 36) -> Contribution:
    """Electricity at the unit's kWh figure, the same amount in months 0 to `months - 1`."""
    _check_months(months)
    label = "Electricity, up to when new" if kwh.source_type == "published" else "Electricity"
    if kwh.source_type == "not_estimated":
        line = CostLine(
            kind="running",
            label=label,
            amount_low=None,
            amount_high=None,
            period="year",
            source_type="not_estimated",
            source_id=None,
            formula="No rated or published kWh figure for this model",
        )
        return Contribution(pay_today=0.0, monthly_low=[0.0] * MONTHS, monthly_high=[0.0] * MONTHS, lines=[line])
    per_month = round(kwh.kwh_per_year / 12 * rate.value, 2)
    per_year = round(kwh.kwh_per_year * rate.value, 2)
    monthly = [per_month if m < months else 0.0 for m in range(MONTHS)]
    line = CostLine(
        kind="running",
        label=label,
        amount_low=per_year,
        amount_high=per_year,
        period="year",
        source_type=kwh.source_type,
        source_id=kwh.source_id,
        formula=(
            f"{_num(kwh.kwh_per_year)} kWh/yr x ${_num(rate.value)}/kWh"
            f" = ${per_year:,.2f}/yr, ${per_month:,.2f}/month"
            + (f". {kwh.note}" if kwh.note else "")  # how the kWh figure was chosen (task 1.9)
        ),
        other_source_ids=list(dict.fromkeys([rate.source_id, *kwh.note_source_ids])),
    )
    return Contribution(pay_today=0.0, monthly_low=monthly, monthly_high=list(monthly), lines=[line])


def aging_line() -> CostLine:
    """Extra draw from age has no sourced figure, so it stays blank."""
    return CostLine(
        kind="running",
        label="Extra use from age",
        amount_low=None,
        amount_high=None,
        period="year",
        source_type="not_estimated",
        source_id=None,
        formula="Left blank on purpose: no published source for how much more an aged unit draws",
    )


def carbon_kg(kwh_per_year: float, kg_per_kwh: RateValue, months: int = 36) -> float:
    return round(kwh_per_year * kg_per_kwh.value * months / 12, 2)


def upkeep(schedule: list[UpkeepItem], months: int = 36) -> Contribution:
    """Each item falls due at months every_months, 2 x every_months, ... below `months`; never today.

    An item that never falls due inside the window adds no line.
    """
    _check_months(months)
    low = [0.0] * MONTHS
    high = [0.0] * MONTHS
    lines: list[CostLine] = []
    for item in schedule:
        due = range(item.every_months, months, item.every_months)
        if not due:
            continue
        for m in due:
            low[m] += item.cost_low
            high[m] += item.cost_high
        lines.append(
            CostLine(
                kind="upkeep",
                label=item.label,
                amount_low=round(item.cost_low * len(due), 2),
                amount_high=round(item.cost_high * len(due), 2),
                period="window",
                source_type="published",
                source_id=item.source_id,
                formula=(
                    f"${item.cost_low:,.2f} to ${item.cost_high:,.2f} every {item.every_months} months,"
                    f" {len(due)} times in {months} months"
                ),
            )
        )
    return Contribution(
        pay_today=0.0,
        monthly_low=[round(x, 2) for x in low],
        monthly_high=[round(x, 2) for x in high],
        lines=lines,
    )
