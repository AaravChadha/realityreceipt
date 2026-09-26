import pytest

from app.engine.lease import cheapest_buyout, effective_annual_cost, rto_buyout, rto_full
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


LEASES = [
    lease(),
    lease(fees=25.0),
    lease(cash_price=0.0),
    lease(early_purchase_rule="pct_of_remaining", early_purchase_pct=0.5),
    lease(early_purchase_rule="cash_price_minus_pct_paid", early_purchase_pct=0.6, fees=10.0),
    lease(early_purchase_rule="pct_of_remaining", early_purchase_pct=1.0),
    lease(term_weeks=208, fees=15.0),
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
