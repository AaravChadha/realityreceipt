import pytest

from app.engine.financing import bnpl, card, cash, pal
from app.models import MONTHS, BnplTerms, RateValue


def test_cash_pays_the_whole_price_today() -> None:
    c = cash(800.0, "user_listing")
    assert c.pay_today == 800.0
    assert c.monthly_low[0] == c.monthly_high[0] == 800.0
    assert sum(c.monthly_low) == sum(c.monthly_high) == 800.0
    assert len(c.monthly_low) == len(c.monthly_high) == MONTHS


def test_cash_has_one_purchase_line_from_its_source() -> None:
    (line,) = cash(800.0, "user_listing").lines
    assert line.kind == "purchase"
    assert line.amount_low == line.amount_high == 800.0
    assert line.source_id == "user_listing"
    assert line.source_type == "user_entered"


def test_cash_from_a_cached_source_is_published() -> None:
    (line,) = cash(899.0, "retailer_cache_homedepot").lines
    assert line.source_type == "published"


G19 = RateValue(value=0.24, source_id="frb_g19")
PAL_RATE = RateValue(value=0.28, source_id="ncua_pals_ii")
PAL_FEE = RateValue(value=20.0, source_id="ncua_pals_ii")
PAL_MAX = RateValue(value=2000.0, source_id="ncua_pals_ii")


def within_cents(x: float, target: float, cents: int = 1) -> bool:
    """`x` is within `cents` of `target`, compared in whole cents so float noise cannot tip it."""
    return abs(round(x * 100) - round(target * 100)) <= cents


def test_card_pays_twelve_equal_payments_from_month_one() -> None:
    c = card(1000, G19)
    assert c.pay_today == 0
    assert c.monthly_low == c.monthly_high
    assert c.monthly_low[0] == 0
    assert all(within_cents(c.monthly_low[m], 94.56) for m in range(1, 13))
    assert all(c.monthly_low[m] == 0 for m in range(13, MONTHS))
    assert within_cents(sum(c.monthly_low), 1134.72)


def test_card_line_is_the_interest_from_the_rate_source() -> None:
    (line,) = card(1000, G19).lines
    assert line.kind == "financing"
    assert line.source_type == "published"
    assert line.source_id == "frb_g19"
    assert line.amount_low == line.amount_high
    assert within_cents(line.amount_low, 134.72)


def test_pal_pays_at_the_caps_plus_the_fee_today() -> None:
    c = pal(1000, PAL_RATE, PAL_FEE, PAL_MAX)
    assert c is not None
    assert c.pay_today == c.monthly_low[0] == 20.0
    assert c.monthly_low == c.monthly_high
    assert all(within_cents(c.monthly_low[m], 96.50) for m in range(1, 13))
    assert all(c.monthly_low[m] == 0 for m in range(13, MONTHS))
    (line,) = c.lines
    assert line.kind == "financing"
    assert "up to" in line.label.lower()
    assert line.amount_low == line.amount_high
    assert within_cents(line.amount_low, 96.50 * 12 - 1000 + 20, cents=12)
    assert line.amount_low == pytest.approx(sum(c.monthly_low) - 1000, abs=0.001)


def test_pal_only_up_to_the_loan_cap() -> None:
    assert pal(2500, PAL_RATE, PAL_FEE, PAL_MAX) is None
    assert pal(2000, PAL_RATE, PAL_FEE, PAL_MAX) is not None


def test_financing_copy_never_says_apr_or_implies_approval() -> None:
    lines = card(1000, G19).lines + pal(1000, PAL_RATE, PAL_FEE, PAL_MAX).lines + bnpl(500, None).lines
    for line in lines:
        for text in (line.label, line.formula):
            assert "APR" not in text
            assert "qualif" not in text.lower()
            assert "—" not in text


def test_bnpl_without_terms_is_not_estimated() -> None:
    c = bnpl(500, None)
    (line,) = c.lines
    assert line.kind == "financing"
    assert line.source_type == "not_estimated"
    assert line.amount_low is None and line.amount_high is None
    assert c.pay_today == c.monthly_low[0] == c.monthly_high[0] == 500.0
    assert sum(c.monthly_low) == sum(c.monthly_high) == 500.0


def test_bnpl_pay_in_four_from_cached_terms() -> None:
    terms = BnplTerms(provider="Example", installments=4, interval_weeks=2, apr=0.0, source_id="example_bnpl")
    c = bnpl(1000, terms)
    assert c.pay_today == 250.0
    assert c.monthly_low[0] == 750.0 and c.monthly_low[1] == 250.0
    assert sum(c.monthly_low) == 1000.0
    (line,) = c.lines
    assert line.source_type == "published" and line.source_id == "example_bnpl"
    assert line.amount_low == line.amount_high == 0.0


def test_bnpl_interest_from_cached_terms_is_what_is_paid_over_the_price() -> None:
    terms = BnplTerms(provider="Example", installments=12, interval_weeks=4, apr=0.30, source_id="example_bnpl")
    c = bnpl(1000, terms)
    (line,) = c.lines
    assert line.amount_low > 0
    assert line.amount_low == pytest.approx(sum(c.monthly_low) - 1000, abs=0.001)


def test_bnpl_installments_after_month_35_are_left_out_of_the_window() -> None:
    # 48 payments every 4 weeks: payment k (0 = today) falls in month k * 48 // 52,
    # so payments 0 to 38 fall in months 0 to 35 and payments 39 to 47 fall after them.
    terms = BnplTerms(provider="Example", installments=48, interval_weeks=4, apr=0.0, source_id="example_bnpl")
    c = bnpl(4800, terms)
    assert len(c.monthly_low) == len(c.monthly_high) == MONTHS
    assert sum(c.monthly_low) == pytest.approx(3900.0)
    assert c.monthly_low[35] == 100.0  # payment 38 only; the nine later ones are not piled in here
    assert c.monthly_low == c.monthly_high
    assert c.pay_today == 100.0
    (line,) = c.lines
    assert line.amount_low == line.amount_high == 0.0  # the method's cost over the price, under the full terms
    # The formula still states the full schedule, then what the 3 years count.
    assert line.formula.startswith("48 payments of $100.00 every 4 weeks from today")
    assert "$4,800.00 in all" in line.formula
    assert line.formula.endswith("Only the 39 payments due in the first 36 months, $3,900.00, count toward the 3-year total")
    pay_in_4 = BnplTerms(provider="Example", installments=4, interval_weeks=2, apr=0.0, source_id="example_bnpl")
    assert "first 36 months" not in bnpl(1000, pay_in_4).lines[0].formula
