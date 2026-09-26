"""Rent-to-own paths (PLAN.md tasks 3.2 and 3.2.1, row A4).

Every number comes from the user's lease, so every line is `user_entered` and
carries the lease's source id (`user_lease`). The cost of keeping the lease is
shown as an effective annual cost (spec §6), in the keep-paying line's formula;
the buyout line states its total against the cash price instead, because
annualizing a buyout after a few weeks gives meaningless percentages.

Pay today is the fees plus the first weekly payment, plus the buyout when it
falls in week 1. Fees fall in month 0 on their own line; they are not part of
the total of payments or the buyout total.

Only payments falling in months 0 to 35 count in the arrays and in a line's
amount; later ones are left out, and the formula states the full lease total.
"""

from app.models import MONTHS, Contribution, CostLine, Lease


def effective_annual_cost(total_payments: float, cash_price: float, term_weeks: int) -> float:
    """((total of payments - cash price) / cash price) / (term_weeks / 52), as a fraction: 1.5 is 150%."""
    if cash_price <= 0 or term_weeks <= 0:
        raise ValueError("an effective annual cost needs a positive cash price and term")
    return ((total_payments - cash_price) / cash_price) / (term_weeks / 52)


def cheapest_buyout(lease: Lease) -> tuple[int, float]:
    """(week, total paid): the week whose payments so far plus buyout is lowest, earliest on a tie.

    A lease with no early purchase option returns the full term.
    """
    if lease.early_purchase_rule == "none":
        return lease.term_weeks, _cents(lease.weekly_payment * lease.term_weeks)
    totals = [
        (week, _cents(lease.weekly_payment * week + _buyout_amount(lease, week)))
        for week in range(1, lease.term_weeks + 1)
    ]
    return min(totals, key=lambda wt: wt[1])  # min keeps the first, so the earliest week wins a tie


def rto_full(lease: Lease) -> Contribution:
    """Keep paying to the end of the lease."""
    total = _cents(lease.weekly_payment * lease.term_weeks)
    formula = (
        f"{lease.term_weeks} weekly payments of {_money(lease.weekly_payment)} from your lease"
        f" = {_money(total)}.{_window_text(lease, lease.term_weeks, 0.0)}"
        f" {_eac_text(total, lease.cash_price, lease.term_weeks)}"
    )
    return _contribution(lease, lease.term_weeks, 0.0, "Total of lease payments", formula)


def rto_buyout(lease: Lease) -> Contribution:
    """Pay until the cheapest buyout week, then buy it out under the lease's early purchase rule."""
    week, total = cheapest_buyout(lease)
    payments = _cents(lease.weekly_payment * week)
    buyout = _cents(total - payments)
    after = f"{_window_text(lease, week, buyout)} {_vs_cash_text(total, lease.cash_price)}"
    if lease.early_purchase_rule == "none":
        label = f"All payments to week {week}"
        formula = f"No early purchase terms entered: {week} weekly payments of {_money(lease.weekly_payment)} = {_money(total)}.{after}"
    elif week == lease.term_weeks:
        label = f"All payments to week {week}"
        formula = f"No early buyout week costs less than finishing the lease: {week} weekly payments of {_money(lease.weekly_payment)} = {_money(total)}.{after}"
    else:
        label = f"Payments plus buyout at week {week}"
        formula = (
            f"{week} weekly payments of {_money(lease.weekly_payment)} = {_money(payments)}, plus a buyout of"
            f" {_money(buyout)} ({_rule_text(lease, week)}) = {_money(total)}. Cheapest week under your lease's"
            f" early purchase rule.{after}"
        )
    return _contribution(lease, week, buyout, label, formula)


def _payment_month(week: int) -> int:
    """Month (0 = today) of 1-based weekly payment `week`; 36 or more is past the 3-year window."""
    return (week - 1) * 12 // 52


def _in_window(week: int) -> bool:
    return _payment_month(week) < MONTHS


def _buyout_amount(lease: Lease, week: int) -> float:
    """What the early purchase rule charges after `week` payments; nothing once every payment is made."""
    if week >= lease.term_weeks:
        return 0.0
    paid = lease.weekly_payment * week
    pct = lease.early_purchase_pct or 0.0
    if lease.early_purchase_rule == "pct_of_remaining":
        return pct * (lease.weekly_payment * lease.term_weeks - paid)
    if lease.early_purchase_rule == "cash_price_minus_pct_paid":
        return max(0.0, lease.cash_price - pct * paid)
    raise ValueError("this lease has no early purchase option")


def _rule_text(lease: Lease, week: int) -> str:
    paid = lease.weekly_payment * week
    pct = lease.early_purchase_pct or 0.0
    if lease.early_purchase_rule == "pct_of_remaining":
        remaining = lease.weekly_payment * lease.term_weeks - paid
        return f"{pct:.0%} of the {_money(remaining)} left to pay"
    return f"cash price {_money(lease.cash_price)} minus {pct:.0%} of the {_money(paid)} paid"


def _eac_text(total: float, cash_price: float, weeks: int) -> str:
    if cash_price <= 0:
        return "Effective annual cost not estimated: the lease shows no cash price."
    eac = effective_annual_cost(total, cash_price, weeks)
    return f"Effective annual cost = (({total:.2f} - {cash_price:.2f}) / {cash_price:.2f}) / ({weeks} / 52) = {eac:.0%}."


def _vs_cash_text(total: float, cash_price: float) -> str:
    if cash_price <= 0:
        return "The lease shows no cash price to compare with."
    diff = _cents(total - cash_price)
    if diff > 0:
        return f"That is {_money(diff)} more than the cash price of {_money(cash_price)}."
    if diff < 0:
        return f"That is {_money(-diff)} less than the cash price of {_money(cash_price)}."
    return f"That is the same as the cash price of {_money(cash_price)}."


def _window_text(lease: Lease, weeks: int, buyout: float) -> str:
    """A sentence for the formula when some of `weeks` payments fall after month 35; else empty."""
    if _in_window(weeks):
        return ""
    counted = sum(1 for week in range(1, weeks + 1) if _in_window(week))
    text = (
        f" Only the {counted} payments due in the first 36 months,"
        f" {_money(lease.weekly_payment * counted)}, count toward the 3-year total."
    )
    return text + (" The buyout falls after them." if buyout > 0 else "")


def _contribution(lease: Lease, weeks: int, buyout: float, label: str, formula: str) -> Contribution:
    """Fees in month 0, weekly payments 1 to `weeks` and the buyout in their months, each left out
    past month 35. The payment line's amount is what falls inside the window."""
    monthly = [0.0] * MONTHS
    for week in range(1, weeks + 1):
        if _in_window(week):
            monthly[_payment_month(week)] += lease.weekly_payment
    if _in_window(weeks):
        monthly[_payment_month(weeks)] += buyout
    counted = _cents(sum(monthly))
    monthly[0] += lease.fees
    monthly = [_cents(m) for m in monthly]
    if not _in_window(weeks):
        label = f"{label} (first 3 years)"
    lines = [CostLine(
        kind="financing", label=label, amount_low=counted, amount_high=counted,
        period="window", source_type="user_entered", source_id=lease.source_id, formula=formula,
    )]
    if lease.fees > 0:
        lines.append(CostLine(
            kind="financing", label="Lease fees", amount_low=_cents(lease.fees), amount_high=_cents(lease.fees),
            period="once", source_type="user_entered", source_id=lease.source_id, formula="Fees on your lease, paid today",
        ))
    buyout_today = buyout if weeks == 1 else 0.0
    return Contribution(
        pay_today=_cents(lease.fees + lease.weekly_payment + buyout_today),
        monthly_low=monthly, monthly_high=list(monthly), lines=lines,
    )


def _money(amount: float) -> str:
    return f"${amount:,.2f}"


def _cents(amount: float) -> float:
    return round(amount, 2)
