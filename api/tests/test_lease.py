import json
import re
from pathlib import Path

import pytest

from app.engine.lease import cheapest_buyout, effective_annual_cost, full_term_total, rto_buyout, rto_full
from app.models import MONTHS, Lease


def lease(**overrides) -> Lease:
    return Lease(**{"weekly_payment": 30.0, "term_weeks": 52, "cash_price": 800.0, **overrides})


def test_effective_annual_cost_pinned_examples() -> None:
    assert effective_annual_cost(2000, 800, 52) == 1.5
    assert effective_annual_cost(2000, 800, 104) == 0.75


def test_effective_annual_cost_needs_a_cash_price() -> None:
    with pytest.raises(ValueError):
        effective_annual_cost(2000, 0, 52)


def test_pct_of_remaining_cheapest_buyout_is_week_1() -> None:
    assert cheapest_buyout(lease(early_purchase_rule="pct_of_remaining", early_purchase_pct=0.5)) == (1, 795.0)


def test_no_early_purchase_returns_the_full_term() -> None:
    assert cheapest_buyout(lease()) == (52, 1560.0)


def test_cash_price_minus_pct_paid_ties_go_to_the_earliest_week() -> None:
    # 30w + (800 - 30w) = 800 for every week up to 26, so week 1 wins the tie.
    assert cheapest_buyout(lease(early_purchase_rule="cash_price_minus_pct_paid", early_purchase_pct=1.0)) == (1, 800.0)


def test_full_term_payments_fall_in_their_months() -> None:
    c = rto_full(lease(fees=20.0))
    # Weeks 1 to 5 fall in month 0 with the fees; weeks 49 to 52 in month 11; nothing after.
    assert c.monthly_low[0] == 5 * 30 + 20
    assert c.monthly_low[11] == 4 * 30
    assert c.monthly_low[12:] == [0.0] * (MONTHS - 12)
    assert sum(c.monthly_low) == pytest.approx(1580.0)
    assert c.monthly_low == c.monthly_high
    assert c.pay_today == 50.0
    assert [line.amount_high for line in c.lines] == [1560.0, 20.0]


def test_a_208_week_lease_counts_only_the_payments_inside_the_window() -> None:
    c = rto_full(lease(term_weeks=208))
    assert len(c.monthly_low) == MONTHS
    # Weeks 1 to 156 fall in months 0 to 35; weeks 157 to 208 are left out, not piled into month 35.
    assert sum(c.monthly_low) == pytest.approx(4680.0)
    assert c.monthly_low[35] == 4 * 30  # weeks 153 to 156
    assert c.monthly_low == c.monthly_high
    line = c.lines[0]
    assert line.amount_low == line.amount_high == 4680.0
    assert line.label == "Total of lease payments (first 3 years)"
    # The formula states the full lease total, and the effective annual cost is on the full lease.
    assert "208 weekly payments of $30.00 from your lease = $6,240.00." in line.formula
    assert "Only the 156 payments due in the first 36 months, $4,680.00, count toward the 3-year total." in line.formula
    assert line.formula.endswith("/ (208 / 52) = 170%.")


def test_a_long_lease_with_no_early_terms_stops_at_month_35_on_the_buyout_path_too() -> None:
    c = rto_buyout(lease(term_weeks=208))
    assert sum(c.monthly_low) == pytest.approx(4680.0)
    assert c.lines[0].amount_high == 4680.0
    assert c.lines[0].label == "All payments to week 208 (first 3 years)"
    assert "$6,240.00" in c.lines[0].formula
    assert "$5,440.00 more than the cash price" in c.lines[0].formula


def test_buyout_is_paid_in_the_buyout_week_month() -> None:
    c = rto_buyout(lease(early_purchase_rule="pct_of_remaining", early_purchase_pct=0.5))
    assert c.monthly_low[0] == 795.0
    assert sum(c.monthly_low) == pytest.approx(795.0)
    assert c.lines[0].label == "Payments plus buyout at week 1"
    assert c.lines[0].amount_low == c.lines[0].amount_high == 795.0


def test_a_week_1_buyout_is_paid_today() -> None:
    # Task 3.2's example lease: the first payment plus the buyout, both in week 1.
    assert rto_buyout(lease(early_purchase_rule="pct_of_remaining", early_purchase_pct=0.5)).pay_today == 795.0
    assert rto_buyout(lease(early_purchase_rule="pct_of_remaining", early_purchase_pct=0.5, fees=20.0)).pay_today == 815.0
    # Keeping the lease pays only the first week today.
    assert rto_full(lease(early_purchase_rule="pct_of_remaining", early_purchase_pct=0.5)).pay_today == 30.0


def test_effective_annual_cost_is_shown_in_the_formula() -> None:
    # (1560 - 800) / 800 over one year = 95%.
    assert "Effective annual cost" in rto_full(lease()).lines[0].formula
    assert rto_full(lease()).lines[0].formula.endswith("= 95%.")


@pytest.mark.parametrize(
    ("terms", "wording"),
    [
        (lease(early_purchase_rule="pct_of_remaining", early_purchase_pct=0.5), "That is $5.00 less than the cash price of $800.00."),
        (lease(early_purchase_rule="cash_price_minus_pct_paid", early_purchase_pct=0.6), "That is $12.00 more than the cash price of $800.00."),
        (lease(early_purchase_rule="cash_price_minus_pct_paid", early_purchase_pct=1.0), "That is the same as the cash price of $800.00."),
        (lease(), "That is $760.00 more than the cash price of $800.00."),
        (lease(cash_price=0.0), "The lease shows no cash price to compare with."),
    ],
)
def test_buyout_states_its_total_against_the_cash_price_not_an_effective_annual_cost(terms: Lease, wording: str) -> None:
    formula = rto_buyout(terms).lines[0].formula
    assert formula.endswith(wording)
    assert "effective annual cost" not in formula.lower()


def test_no_early_purchase_terms_are_described_as_not_entered() -> None:
    formula = rto_buyout(lease()).lines[0].formula
    assert formula.startswith("No early purchase terms entered: 52 weekly payments of $30.00 = $1,560.00.")


# The Aaron's demo card (demo/cards/cards.json): its own printed payment today and total of payments.
AARONS = lease(weekly_payment=33.48, cash_price=1196.99, payment_today=0.01, total_of_payments=1739.88)


def test_the_aarons_card_uses_the_numbers_printed_on_the_lease() -> None:
    full = rto_full(AARONS)
    assert full.pay_today == 0.01
    assert full.lines[0].amount_low == full.lines[0].amount_high == 1739.88
    assert sum(full.monthly_low) == pytest.approx(1739.88)
    # $0.01 in week 1, then $1,739.87 spread evenly over weeks 2 to 52 ($34.11, the last week $34.37).
    assert full.monthly_low[0] == 136.45  # weeks 1 to 5: 0.01 + 4 x 34.11
    assert "$0.01 today and $1,739.88 in all over 52 weeks, as printed on your lease" in full.lines[0].formula
    # ((1739.88 - 1196.99) / 1196.99) / (52 / 52) = 45%.
    assert full.lines[0].formula.endswith("= 45%.")
    # No early purchase terms entered, so the buyout path pays the lease out too.
    buyout = rto_buyout(AARONS)
    assert buyout.pay_today == 0.01
    assert buyout.lines[0].amount_high == 1739.88
    assert "as printed on your lease" in buyout.lines[0].formula
    # The card's printed "cost of lease services".
    assert buyout.lines[0].formula.endswith("That is $542.89 more than the cash price of $1,196.99.")


def test_a_printed_total_alone_is_spread_evenly_over_every_week() -> None:
    c = rto_full(lease(total_of_payments=1600.0))
    assert sum(c.monthly_low) == pytest.approx(1600.0)
    assert c.pay_today == 30.76  # 1600 / 52 = 30.769..., whole cents, the last week takes the rest
    assert c.lines[0].formula.startswith(
        "$1,600.00 in all over 52 weeks, as printed on your lease, spread evenly over 52 weekly payments of about $30.76."
    )
    assert c.lines[0].formula.endswith("(52 / 52) = 100%.")


def test_a_printed_payment_today_alone_replaces_the_first_weekly_payment() -> None:
    c = rto_full(lease(payment_today=0.01))
    assert c.pay_today == 0.01
    assert sum(c.monthly_low) == pytest.approx(0.01 + 51 * 30)
    assert c.lines[0].formula.startswith(
        "$0.01 today, as printed on your lease, then 51 weekly payments of $30.00. Total of payments = $1,530.01."
    )


def test_the_buyout_rule_works_from_the_printed_total() -> None:
    # 40% of what is left of the printed $1,739.88 after the $0.01 paid today: 0.01 + 695.948 = 695.96.
    c = rto_buyout(AARONS.model_copy(update={"early_purchase_rule": "pct_of_remaining", "early_purchase_pct": 0.4}))
    assert c.pay_today == 695.96
    assert "Payments to week 1 = $0.01, plus a buyout of $695.95 (40% of the $1,739.87 left to pay)" in c.lines[0].formula


def test_a_printed_total_on_a_long_lease_counts_only_the_weeks_in_the_window() -> None:
    c = rto_full(lease(term_weeks=208, total_of_payments=6448.0))  # $31.00 a week, as printed
    assert sum(c.monthly_low) == pytest.approx(156 * 31)
    assert "$6,448.00 in all over 208 weeks, as printed on your lease" in c.lines[0].formula
    assert "Only the 156 payments due in the first 36 months, $4,836.00, count" in c.lines[0].formula


@pytest.mark.parametrize("printed", [
    {"payment_today": 100.0, "total_of_payments": 50.0},
    {"term_weeks": 1, "payment_today": 10.0, "total_of_payments": 30.0},
])
def test_a_payment_today_that_does_not_fit_the_printed_total_is_refused(printed: dict) -> None:
    with pytest.raises(ValueError, match="does not fit"):
        rto_full(lease(**printed))


def test_one_payment_is_singular() -> None:
    buyout = rto_buyout(lease(early_purchase_rule="pct_of_remaining", early_purchase_pct=0.5)).lines[0].formula
    assert buyout.startswith("1 weekly payment of $30.00 = $30.00, plus a buyout of $765.00")
    assert rto_full(lease(term_weeks=1)).lines[0].formula.startswith("1 weekly payment of $30.00 from your lease = $30.00.")
    assert "then 1 weekly payment of $30.00." in rto_full(lease(term_weeks=2, payment_today=0.01)).lines[0].formula


LEASES = [
    lease(),
    lease(fees=25.0),
    lease(cash_price=0.0),
    lease(early_purchase_rule="pct_of_remaining", early_purchase_pct=0.5),
    lease(early_purchase_rule="cash_price_minus_pct_paid", early_purchase_pct=0.6, fees=10.0),
    lease(early_purchase_rule="pct_of_remaining", early_purchase_pct=1.0),
    lease(term_weeks=208, fees=15.0),
    lease(term_weeks=1),
    AARONS,
    lease(total_of_payments=1600.0),
    lease(term_weeks=2, payment_today=0.01),
    AARONS.model_copy(update={"early_purchase_rule": "cash_price_minus_pct_paid", "early_purchase_pct": 0.5}),
]


@pytest.mark.parametrize("terms", LEASES)
def test_lines_carry_the_lease_source_and_follow_the_copy_rules(terms: Lease) -> None:
    for c in (rto_full(terms), rto_buyout(terms)):
        assert c.lines
        for line in c.lines:
            assert line.source_id == "user_lease"
            assert line.source_type == "user_entered"
            for text in (line.label, line.formula):
                assert "APR" not in text.upper()
                assert "\u2014" not in text
                assert "no early purchase option" not in text.lower()
                assert not re.search(r"\b1 weekly payments", text)


def test_full_term_total_of_a_208_week_lease_is_every_payment() -> None:
    assert full_term_total(lease(term_weeks=208)) == 6240.0  # not the $4,680 inside the window


def test_full_term_total_uses_a_printed_total_over_the_weekly_figure() -> None:
    assert full_term_total(AARONS) == 1739.88  # 52 x $33.48 would be $1,740.96


def test_full_term_total_adds_fees() -> None:
    assert full_term_total(lease(fees=20.0)) == 1580.0
    long_lease = lease(term_weeks=208, fees=15.0)
    assert full_term_total(long_lease) == 6255.0
    assert "= $6,240.00." in rto_full(long_lease).lines[0].formula  # the keep-paying line's full total


def test_full_term_total_with_only_a_printed_payment_today() -> None:
    # $0.01 today replaces the first $30 payment (task 3.2.2): 0.01 + 51 x 30.
    assert full_term_total(lease(payment_today=0.01)) == 1530.01


@pytest.mark.parametrize("terms", [t for t in LEASES if t.term_weeks <= 156])
def test_full_term_total_matches_the_keep_paying_path(terms: Lease) -> None:
    # Every payment falls inside the 36 months, so the keep-paying arrays hold the whole lease, fees included.
    full = rto_full(terms)
    assert full_term_total(terms) == pytest.approx(sum(full.monthly_high), abs=0.001)
    assert full_term_total(terms) == pytest.approx(full.lines[0].amount_high + terms.fees, abs=0.001)


CARDS = Path(__file__).resolve().parents[2] / "demo" / "cards" / "cards.json"


def test_the_aarons_demo_lease_keep_paying_formula_states_its_cost_over_the_cash_price() -> None:
    card = next(c for c in json.loads(CARDS.read_text())["cards"] if c["kind"] == "lease")
    formula = rto_full(Lease(**card["typed"]["lease"])).lines[0].formula
    assert "$542.89 more than the cash price of $1,196.99" in formula  # the card's "cost of lease services"
    assert "45%" in formula
    assert "No early purchase terms entered" in formula
    assert formula.index("$542.89 more than the cash price") < formula.index("Effective annual cost")


def test_keep_paying_compares_the_full_term_total_fees_included() -> None:
    # full_term_total: 52 x $30 + $20 fees = $1,580, against an $800 cash price.
    assert "That is $780.00 more than the cash price of $800.00." in rto_full(lease(fees=20.0)).lines[0].formula
    # A 208-week lease is compared on its full $6,240, not the $4,680 inside the window.
    assert "That is $5,440.00 more than the cash price of $800.00." in rto_full(lease(term_weeks=208)).lines[0].formula


def test_keep_paying_mentions_missing_early_terms_only_when_none_are_entered() -> None:
    assert "No early purchase terms entered" in rto_full(lease()).lines[0].formula
    with_terms = rto_full(lease(early_purchase_rule="pct_of_remaining", early_purchase_pct=0.5)).lines[0].formula
    assert "No early purchase terms entered" not in with_terms
    assert "That is $760.00 more than the cash price of $800.00." in with_terms


def test_the_aarons_demo_lease_names_the_even_spread_and_its_weekly_figure() -> None:
    card = next(c for c in json.loads(CARDS.read_text())["cards"] if c["kind"] == "lease")
    formula = rto_full(Lease(**card["typed"]["lease"])).lines[0].formula
    # 52 x $33.48 would be $1,740.96; the printed $1,739.88 less today's $0.01 is what the weeks share.
    assert "the remaining $1,739.87 is spread evenly over 51 weekly payments of about $34.11" in formula


def test_an_exact_spread_says_its_weekly_figure_without_about() -> None:
    formula = rto_full(lease(term_weeks=208, total_of_payments=6448.0)).lines[0].formula
    assert "spread evenly over 208 weekly payments of $31.00." in formula


def test_the_effective_annual_cost_uses_the_same_fee_inclusive_total_as_the_cash_comparison() -> None:
    formula = rto_full(lease(fees=40.0)).lines[0].formula
    # 52 x $30 = $1,560 plus $40 in fees = $1,600 = full_term_total, used by both figures.
    assert full_term_total(lease(fees=40.0)) == 1600.0
    assert "Plus $40.00 in fees, $1,600.00 in all." in formula
    assert "That is $800.00 more than the cash price of $800.00." in formula
    assert formula.endswith("Effective annual cost = ((1600.00 - 800.00) / 800.00) / (52 / 52) = 100%.")
