"""Rent-to-own paths (PLAN.md tasks 3.2 to 3.2.4, row A4).

Every number comes from the user's lease, so every line is `user_entered` and
carries the lease's source id (`user_lease`). The keep-paying line's formula
states the full-term total against the cash price, then the effective annual
cost (spec §6); the buyout line states only its own total against the cash
price, because annualizing a buyout after a few weeks gives meaningless
percentages.

The lease's own printed numbers win over ones derived from the weekly payment
(task 3.2.2): `payment_today` is week 1's payment, and `total_of_payments` is the
full-term total, today's payment included, with the rest spread evenly over the
other weeks. Payments so far, what is left to pay, the total and the effective
annual cost all come from that week-by-week schedule.

Pay today is the fees plus week 1's payment, plus the buyout when it falls in
week 1. Fees fall in month 0 on their own line; they are not part of the total
of payments or the buyout total.

Only payments falling in months 0 to 35 count in the arrays and in a line's
amount; later ones are left out, and the formula states the full lease total.
"""

from app.models import MONTHS, Contribution, CostLine, Lease


def effective_annual_cost(total_payments: float, cash_price: float, term_weeks: int) -> float:
    """((total of payments - cash price) / cash price) / (term_weeks / 52), as a fraction: 1.5 is 150%."""
    if cash_price <= 0 or term_weeks <= 0:
        raise ValueError("an effective annual cost needs a positive cash price and term")
    return ((total_payments - cash_price) / cash_price) / (term_weeks / 52)


def full_term_total(lease: Lease) -> float:
    """Everything the lease costs to the end of its term: the payment schedule, from the printed
    numbers when set (so it matches the keep-paying line), plus fees. For cost per year (task 3.3.4),
    since a path's arrays hold only what falls inside the 36 months."""
    return _cents(sum(_schedule(lease)) + lease.fees)


def cheapest_buyout(lease: Lease) -> tuple[int, float]:
    """(week, total paid): the week whose payments so far plus buyout is lowest, earliest on a tie.

    A lease with no early purchase option returns the full term.
    """
    schedule = _schedule(lease)
    full = _cents(sum(schedule))
    if lease.early_purchase_rule == "none":
        return lease.term_weeks, full
    totals: list[tuple[int, float]] = []
    paid = 0.0
    for week, amount in enumerate(schedule, start=1):
        paid += amount
        totals.append((week, _cents(paid + _buyout_amount(lease, week, paid, full))))
    return min(totals, key=lambda wt: wt[1])  # min keeps the first, so the earliest week wins a tie


def rto_full(lease: Lease) -> Contribution:
    """Keep paying to the end of the lease."""
    schedule = _schedule(lease)
    total = _cents(sum(schedule))
    if _printed(lease):
        paid = f"{_printed_text(lease)} Total of payments = {_money(total)}."
    else:
        paid = f"{_weekly(lease.term_weeks)} of {_money(lease.weekly_payment)} from your lease = {_money(total)}."
    # Fees count toward both the cost over the cash price and the effective annual cost (task 3.2.5).
    full = full_term_total(lease)
    fees = f" Plus {_money(lease.fees)} in fees, {_money(full)} in all." if lease.fees > 0 else ""
    no_terms = " No early purchase terms entered." if lease.early_purchase_rule == "none" else ""
    formula = (
        f"{paid}{fees}{_window_text(schedule, lease.term_weeks, 0.0)}"
        f" {_vs_cash_text(full, lease.cash_price)}{no_terms}"
        f" {_eac_text(full, lease.cash_price, lease.term_weeks)}"
    )
    return _contribution(lease, schedule, lease.term_weeks, 0.0, "Total of lease payments", formula)


def rto_buyout(lease: Lease) -> Contribution:
    """Pay until the cheapest buyout week, then buy it out under the lease's early purchase rule."""
    schedule = _schedule(lease)
    week, total = cheapest_buyout(lease)
    payments = _cents(sum(schedule[:week]))
    buyout = _cents(total - payments)
    if _printed(lease):
        paid = f"{_printed_text(lease)} Payments to week {week} = {_money(payments)}"
    else:
        paid = f"{_weekly(week)} of {_money(lease.weekly_payment)} = {_money(payments)}"
    # Fees count toward the cost over the cash price, as on the keep-paying line (task 3.2.6).
    with_fees = _cents(total + lease.fees)
    fees = f" Plus {_money(lease.fees)} in fees, {_money(with_fees)} in all." if lease.fees > 0 else ""
    after = f"{fees}{_window_text(schedule, week, buyout)} {_vs_cash_text(with_fees, lease.cash_price)}"
    if lease.early_purchase_rule == "none":
        label = f"All payments to week {week}"
        formula = f"No early purchase terms entered: {paid}.{after}"
    elif week == lease.term_weeks:
        label = f"All payments to week {week}"
        formula = f"No early buyout week costs less than finishing the lease: {paid}.{after}"
    else:
        label = f"Payments plus buyout at week {week}"
        formula = (
            f"{paid}, plus a buyout of {_money(buyout)} ({_rule_text(lease, schedule, week)}) = {_money(total)}."
            f" Cheapest week under your lease's early purchase rule.{after}"
        )
    return _contribution(lease, schedule, week, buyout, label, formula)


def _schedule(lease: Lease) -> list[float]:
    """Each week's payment, week 1 (paid today) first, from the lease's printed numbers when set.

    Raises `ValueError` when the printed payment today does not fit the printed total.
    """
    n, today, total = lease.term_weeks, lease.payment_today, lease.total_of_payments
    if total is None:
        first = lease.weekly_payment if today is None else today
        return [first] + [lease.weekly_payment] * (n - 1)
    if today is None:
        return _spread(total, n)
    if today > total or (n == 1 and today != total):
        raise ValueError("the payment today printed on the lease does not fit its total of payments")
    return [today] + (_spread(total - today, n - 1) if n > 1 else [])


def _spread(amount: float, weeks: int) -> list[float]:
    """`amount` as `weeks` equal whole-cent payments, the last one taking the leftover cents."""
    each, extra = divmod(round(amount * 100), weeks)
    return [each / 100] * (weeks - 1) + [(each + extra) / 100]


def _printed(lease: Lease) -> bool:
    return lease.payment_today is not None or lease.total_of_payments is not None


def _printed_text(lease: Lease) -> str:
    """The lease's printed numbers, and how the other weeks are filled from them, as one sentence."""
    n, today, total = lease.term_weeks, lease.payment_today, lease.total_of_payments
    if total is None:
        then = f", then {_weekly(n - 1)} of {_money(lease.weekly_payment)}" if n > 1 else ""
        return f"{_money(today)} today, as printed on your lease{then}."
    if today is None:
        return f"{_money(total)} in all over {_weeks(n)}, as printed on your lease, spread evenly over {_even_text(total, n)}."
    rest = f"; the remaining {_money(total - today)} is spread evenly over {_even_text(total - today, n - 1)}" if n > 1 else ""
    return f"{_money(today)} today and {_money(total)} in all over {_weeks(n)}, as printed on your lease{rest}."


def _even_text(amount: float, weeks: int) -> str:
    """How `_spread` fills `weeks`: "51 weekly payments of about $34.11" ("about" when the last week
    takes leftover cents), so the monthly figures are not read as printed payments."""
    each, extra = divmod(round(amount * 100), weeks)
    return f"{_weekly(weeks)} of {'about ' if extra else ''}{_money(each / 100)}"


def _payment_month(week: int) -> int:
    """Month (0 = today) of 1-based weekly payment `week`; 36 or more is past the 3-year window."""
    return (week - 1) * 12 // 52


def _in_window(week: int) -> bool:
    return _payment_month(week) < MONTHS


def _buyout_amount(lease: Lease, week: int, paid: float, full: float) -> float:
    """What the early purchase rule charges after `week` payments totalling `paid` of `full`;
    nothing once every payment is made."""
    if week >= lease.term_weeks:
        return 0.0
    pct = lease.early_purchase_pct or 0.0
    if lease.early_purchase_rule == "pct_of_remaining":
        return pct * (full - paid)
    if lease.early_purchase_rule == "cash_price_minus_pct_paid":
        return max(0.0, lease.cash_price - pct * paid)
    raise ValueError("this lease has no early purchase option")


def _rule_text(lease: Lease, schedule: list[float], week: int) -> str:
    paid = sum(schedule[:week])
    pct = lease.early_purchase_pct or 0.0
    if lease.early_purchase_rule == "pct_of_remaining":
        return f"{pct:.0%} of the {_money(sum(schedule) - paid)} left to pay"
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


def _window_text(schedule: list[float], weeks: int, buyout: float) -> str:
    """A sentence for the formula when some of `weeks` payments fall after month 35; else empty."""
    if _in_window(weeks):
        return ""
    counted = sum(1 for week in range(1, weeks + 1) if _in_window(week))
    text = (
        f" Only the {counted} payments due in the first 36 months,"
        f" {_money(sum(schedule[:counted]))}, count toward the 3-year total."
    )
    return text + (" The buyout falls after them." if buyout > 0 else "")


def _contribution(
    lease: Lease, schedule: list[float], weeks: int, buyout: float, label: str, formula: str
) -> Contribution:
    """Fees in month 0, the payments for weeks 1 to `weeks` and the buyout in their months, each
    left out past month 35. The payment line's amount is what falls inside the window."""
    monthly = [0.0] * MONTHS
    for week, amount in enumerate(schedule[:weeks], start=1):
        if _in_window(week):
            monthly[_payment_month(week)] += amount
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
        pay_today=_cents(lease.fees + schedule[0] + buyout_today),
        monthly_low=monthly, monthly_high=list(monthly), lines=lines,
    )


def _weekly(n: int) -> str:
    """With the right plural: "1 weekly payment", "52 weekly payments"."""
    return f"{n} weekly payment{'' if n == 1 else 's'}"


def _weeks(n: int) -> str:
    return f"{n} week{'' if n == 1 else 's'}"


def _money(amount: float) -> str:
    return f"${amount:,.2f}"


def _cents(amount: float) -> float:
    return round(amount, 2)
