"""How a new item is paid for (PLAN.md row A3).

Each function returns the cash flow of paying the price by one method: its
arrays hold every dollar paid, principal included. Only `cash` knows where the
price came from, so only it carries the `purchase` line; the others carry one
`financing` line for what the method costs on top of the price.
"""

from app.models import MONTHS, BnplTerms, Contribution, CostLine, RateValue

USER_SOURCE_IDS = {"user", "user_listing", "user_lease"}


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _pct(rate: float) -> str:
    return f"{rate * 100:.2f}".rstrip("0").rstrip(".") + "%"


def _level_payment(principal: float, annual_rate: float, months: int) -> float:
    """Equal monthly payment that repays `principal` at `annual_rate` / 12 a month, rounded to cents."""
    if not 1 <= months < MONTHS:
        raise ValueError(f"months must be 1 to {MONTHS - 1}, got {months}")
    i = annual_rate / 12
    payment = principal / months if i == 0 else principal * i / (1 - (1 + i) ** -months)
    return round(payment, 2)


def cash(price: float, source_id: str) -> Contribution:
    """The whole price in month 0: paid in full today."""
    price = round(price, 2)
    monthly = [0.0] * MONTHS
    monthly[0] = price
    line = CostLine(
        kind="purchase",
        label="Price today",
        amount_low=price,
        amount_high=price,
        period="once",
        source_type="user_entered" if source_id in USER_SOURCE_IDS else "published",
        source_id=source_id,
        formula=f"${price:,.2f} paid in full today",
    )
    return Contribution(pay_today=price, monthly_low=monthly, monthly_high=list(monthly), lines=[line])


def card(price: float, apr: RateValue, months: int = 12) -> Contribution:
    """Paid off in `months` equal payments at the card rate, the first in month 1. Nothing today."""
    payment = _level_payment(price, apr.value, months)
    monthly = [0.0] * MONTHS
    for m in range(1, months + 1):
        monthly[m] = payment
    interest = round(payment * months - price, 2)
    line = CostLine(
        kind="financing",
        label="Card interest",
        amount_low=interest,
        amount_high=interest,
        period="window",
        source_type="published",
        source_id=apr.source_id,
        formula=(
            f"{months} equal payments of {_money(payment)} at {_pct(apr.value)} a year, "
            f"{_money(payment * months)} in all, less the {_money(price)} price"
        ),
    )
    return Contribution(pay_today=0.0, monthly_low=monthly, monthly_high=list(monthly), lines=[line])


def pal(
    price: float, rate_cap: RateValue, fee_cap: RateValue, max_amount: RateValue, months: int = 12
) -> Contribution | None:
    """A credit union payday alternative loan at the NCUA caps: the most it can cost, not an offer.

    The fee cap is paid today and the payments start in month 1. `None` when the
    price is over the loan cap.
    """
    if price > max_amount.value:
        return None
    payment = _level_payment(price, rate_cap.value, months)
    fee = round(fee_cap.value, 2)
    monthly = [0.0] * MONTHS
    monthly[0] = fee
    for m in range(1, months + 1):
        monthly[m] = payment
    cost = round(payment * months - price + fee, 2)
    line = CostLine(
        kind="financing",
        label="PAL interest and fee, up to",
        amount_low=cost,
        amount_high=cost,
        period="window",
        source_type="published",
        source_id=rate_cap.source_id,
        formula=(
            f"Up to: {months} equal payments of {_money(payment)} at the {_pct(rate_cap.value)} rate cap, "
            f"plus the {_money(fee)} application fee cap, less the {_money(price)} price. "
            f"The most a federal credit union may charge on a loan up to {_money(max_amount.value)}"
        ),
    )
    return Contribution(pay_today=fee, monthly_low=monthly, monthly_high=list(monthly), lines=[line])


def bnpl(price: float, terms: BnplTerms | None) -> Contribution:
    """Buy now pay later, from one provider's cached terms.

    Without terms the price is shown paid today and the method's cost is
    `not_estimated`: the total can then only be low by the fees nobody has
    sourced, and no payment schedule is invented. With terms, the installments
    fall every `interval_weeks` from today.
    """
    price = round(price, 2)
    monthly = [0.0] * MONTHS
    if terms is None:
        monthly[0] = price
        line = CostLine(
            kind="financing",
            label="Buy now pay later cost",
            amount_low=None,
            amount_high=None,
            period="window",
            source_type="not_estimated",
            source_id=None,
            formula="No provider terms cached: shown as the full price today; the payment schedule and any fees are not estimated",
        )
        return Contribution(pay_today=price, monthly_low=monthly, monthly_high=list(monthly), lines=[line])

    n = terms.installments
    r = terms.apr * terms.interval_weeks / 52
    level = price / n if r == 0 else price * r / ((1 - (1 + r) ** -n) * (1 + r))
    payment = round(level, 2)
    total = round(level * n, 2)
    payments = [payment] * (n - 1) + [round(total - payment * (n - 1), 2)]
    for k, amount in enumerate(payments):
        monthly[min(MONTHS - 1, k * terms.interval_weeks * 12 // 52)] += amount
    monthly = [round(m, 2) for m in monthly]
    cost = round(total - price, 2)
    line = CostLine(
        kind="financing",
        label="Buy now pay later cost",
        amount_low=cost,
        amount_high=cost,
        period="window",
        source_type="published",
        source_id=terms.source_id,
        formula=(
            f"{n} payments of {_money(payment)} every {terms.interval_weeks} weeks from today "
            f"at {_pct(terms.apr)} a year under {terms.provider}'s published terms, "
            f"{_money(total)} in all, less the {_money(price)} price"
        ),
    )
    return Contribution(pay_today=payments[0], monthly_low=monthly, monthly_high=list(monthly), lines=[line])
