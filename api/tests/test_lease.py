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


def test_payments_past_month_35_land_in_month_35() -> None:
    c = rto_full(lease(weekly_payment=10.0, term_weeks=200))
    assert len(c.monthly_low) == MONTHS
    assert c.monthly_low[35] == 48 * 10  # weeks 153 to 200
    assert sum(c.monthly_low) == pytest.approx(2000.0)


def test_buyout_is_paid_in_the_buyout_week_month() -> None:
    c = rto_buyout(lease(early_purchase_rule="pct_of_remaining", early_purchase_pct=0.5))
    assert c.monthly_low[0] == 795.0
    assert sum(c.monthly_low) == pytest.approx(795.0)
    assert c.pay_today == 30.0
    assert c.lines[0].label == "Payments plus buyout at week 1"
    assert c.lines[0].amount_low == c.lines[0].amount_high == 795.0


def test_effective_annual_cost_is_shown_in_the_formula() -> None:
    # (1560 - 800) / 800 over one year = 95%.
    assert "Effective annual cost" in rto_full(lease()).lines[0].formula
    assert rto_full(lease()).lines[0].formula.endswith("= 95%.")


LEASES = [
    lease(),
    lease(fees=25.0),
    lease(cash_price=0.0),
    lease(early_purchase_rule="pct_of_remaining", early_purchase_pct=0.5),
    lease(early_purchase_rule="cash_price_minus_pct_paid", early_purchase_pct=0.6, fees=10.0),
    lease(early_purchase_rule="pct_of_remaining", early_purchase_pct=1.0),
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
