"""Rent-to-own paths (PLAN.md task 3.2, row A4).

Every number comes from the user's lease, so every line is `user_entered` and
carries the lease's source id (`user_lease`). The cost of the lease is shown as
an effective annual cost (spec §6), in the payment line's formula.

Pay today is the fees plus the first weekly payment. Fees fall in month 0 on
their own line; they are not part of the total of payments or the buyout total.
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
        f" = {_money(total)}. {_eac_text(total, lease.cash_price, lease.term_weeks)}"
    )
    line = CostLine(
        kind="financing", label="Total of lease payments", amount_low=total, amount_high=total,
        period="window", source_type="user_entered", source_id=lease.source_id, formula=formula,
    )
    return _contribution(lease, lease.term_weeks, 0.0, line)


def rto_buyout(lease: Lease) -> Contribution:
    """Pay until the cheapest buyout week, then buy it out under the lease's early purchase rule."""
    week, total = cheapest_buyout(lease)
    payments = _cents(lease.weekly_payment * week)
    buyout = _cents(total - payments)
    eac = _eac_text(total, lease.cash_price, week)
    if lease.early_purchase_rule == "none":
        label = f"All payments to week {week}"
        formula = f"Your lease has no early purchase option: {week} weekly payments of {_money(lease.weekly_payment)} = {_money(total)}. {eac}"
    elif week == lease.term_weeks:
        label = f"All payments to week {week}"
        formula = f"No early buyout week costs less than finishing the lease: {week} weekly payments of {_money(lease.weekly_payment)} = {_money(total)}. {eac}"
    else:
        label = f"Payments plus buyout at week {week}"
        formula = (
            f"{week} weekly payments of {_money(lease.weekly_payment)} = {_money(payments)}, plus a buyout of"
            f" {_money(buyout)} ({_rule_text(lease, week)}) = {_money(total)}. Cheapest week under your lease's"
            f" early purchase rule. {eac}"
        )
    line = CostLine(
        kind="financing", label=label, amount_low=total, amount_high=total,
        period="window", source_type="user_entered", source_id=lease.source_id, formula=formula,
    )
    return _contribution(lease, week, buyout, line)


def _payment_month(week: int) -> int:
    """Month (0 = today) of 1-based weekly payment `week`; anything past month 35 lands in month 35."""
    return min(MONTHS - 1, (week - 1) * 12 // 52)


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


def _contribution(lease: Lease, weeks: int, buyout: float, line: CostLine) -> Contribution:
    monthly = [0.0] * MONTHS
    monthly[0] += lease.fees
    for week in range(1, weeks + 1):
        monthly[_payment_month(week)] += lease.weekly_payment
    monthly[_payment_month(weeks)] += buyout
    monthly = [_cents(m) for m in monthly]
    lines = [line]
    if lease.fees > 0:
        lines.append(CostLine(
            kind="financing", label="Lease fees", amount_low=_cents(lease.fees), amount_high=_cents(lease.fees),
            period="once", source_type="user_entered", source_id=lease.source_id, formula="Fees on your lease, paid today",
        ))
    return Contribution(
        pay_today=_cents(lease.fees + lease.weekly_payment),
        monthly_low=monthly, monthly_high=list(monthly), lines=lines,
    )


def _money(amount: float) -> str:
    return f"${amount:,.2f}"


def _cents(amount: float) -> float:
    return round(amount, 2)
