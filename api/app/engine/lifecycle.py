"""Remaining life, cost per year of use, the replacement purchase, and adding contributions up
(PLAN.md task 2.6, row A2; formulas pinned in PLAN.md "Decisions").

Month 0 is today. Money is rounded to cents.
"""

import math

from app.engine.financing import USER_SOURCE_IDS
from app.models import MONTHS, Contribution, CostLine, LifespanRange, Offer


def remaining_life(age_years: float | None, lifespan: LifespanRange | None) -> tuple[float | None, float | None]:
    """Years of typical life left at each end, never below 0. Unknown age or lifespan gives (None, None)."""
    if age_years is None or lifespan is None:
        return None, None
    age = max(0.0, age_years)
    return round(max(0.0, lifespan.low_years - age), 2), round(max(0.0, lifespan.high_years - age), 2)


def cost_per_year(
    purchase_low: float,
    purchase_high: float,
    annual_low: float,
    annual_high: float,
    life_low: float | None,
    life_high: float | None,
) -> tuple[float | None, float | None]:
    """low = purchase low / life high + annual low; high = purchase high / life low + annual high.

    Both `None` without a lifespan; an end whose life is 0 is `None` (past typical life).
    """
    if life_low is None or life_high is None:
        return None, None
    low = round(purchase_low / life_high + annual_low, 2) if life_high > 0 else None
    high = round(purchase_high / life_low + annual_high, 2) if life_low > 0 else None
    return low, high


def replacement(offer: Offer, life_low: float | None, life_high: float | None) -> Contribution:
    """`offer`'s price in `monthly_high` at month ceil(life_low * 12) and in `monthly_low` at month
    ceil(life_high * 12), each only when that month is inside the 36. No line when neither is."""
    low = [0.0] * MONTHS
    high = [0.0] * MONTHS
    if life_low is None or life_high is None:
        return Contribution(pay_today=0.0, monthly_low=low, monthly_high=high, lines=[])
    price = round(offer.price, 2)
    month_high = replacement_month(life_low)
    month_low = replacement_month(life_high)
    if month_high >= MONTHS:
        return Contribution(pay_today=0.0, monthly_low=low, monthly_high=high, lines=[])
    high[month_high] = price
    if month_low < MONTHS:
        low[month_low] = price
        later = f"or month {month_low} if it lasts {_years(life_high)}"
    else:
        later = f"and not inside the 36 months if it lasts {_years(life_high)}"
    line = CostLine(
        kind="replacement",
        label="Replacement when it wears out",
        amount_low=price if month_low < MONTHS else 0.0,
        amount_high=price,
        period="once",
        source_type="user_entered" if offer.source_id in USER_SOURCE_IDS else "published",
        source_id=offer.source_id,
        formula=f"Cheapest cached new offer, ${price:,.2f}: bought at month {month_high} if this one lasts {_years(life_low)}, {later}",
    )
    return Contribution(pay_today=0.0, monthly_low=low, monthly_high=high, lines=[line])


def combine(parts: list[Contribution]) -> Contribution:
    """Month-by-month sums, pay today summed, lines in order."""
    low = [0.0] * MONTHS
    high = [0.0] * MONTHS
    for part in parts:
        for m in range(MONTHS):
            low[m] += part.monthly_low[m]
            high[m] += part.monthly_high[m]
    return Contribution(
        pay_today=round(sum(p.pay_today for p in parts), 2),
        monthly_low=[round(x, 2) for x in low],
        monthly_high=[round(x, 2) for x in high],
        lines=[line for p in parts for line in p.lines],
    )


def replacement_month(life_years: float) -> int:
    """Month in which a unit with `life_years` of life left is replaced: ceil(life_years * 12)."""
    # Round first so float noise (3.0000000000000004 years) does not push the purchase a month later.
    return math.ceil(round(life_years * 12, 6))


def _years(life_years: float) -> str:
    n = f"{life_years:.2f}".rstrip("0").rstrip(".")
    return f"{n} more year" if n == "1" else f"{n} more years"
