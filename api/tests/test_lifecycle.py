import pytest

from app.engine.lifecycle import combine, cost_per_year, remaining_life, replacement
from app.models import MONTHS, Contribution, LifespanRange, Offer

LIFESPAN = LifespanRange(low_years=10, high_years=15, source_id="lifespan_src")


def offer(price: float = 899.0) -> Offer:
    return Offer(item_id="new-a", price=price, seller_type="retailer", source="retailer_cache", source_id="retailer_src")


def test_remaining_life_pinned_example() -> None:
    assert remaining_life(12, LIFESPAN) == (0, 3)


def test_remaining_life_needs_an_age_and_a_lifespan() -> None:
    assert remaining_life(0, LIFESPAN) == (10, 15)
    assert remaining_life(None, LIFESPAN) == (None, None)
    assert remaining_life(3, None) == (None, None)


def test_cost_per_year_pinned_example() -> None:
    assert cost_per_year(1200, 1800, 100, 150, 10, 15) == (1200 / 15 + 100, 1800 / 10 + 150)


def test_cost_per_year_without_lifespan_or_past_typical_life() -> None:
    assert cost_per_year(1200, 1800, 100, 150, None, None) == (None, None)
    assert cost_per_year(250, 250, 78, 78, 0, 3) == (round(250 / 3 + 78, 2), None)


def test_replacement_falls_at_the_end_of_each_life() -> None:
    c = replacement(offer(), 1, 2)
    assert c.monthly_high[12] == 899.0 and sum(c.monthly_high) == 899.0
    assert c.monthly_low[24] == 899.0 and sum(c.monthly_low) == 899.0
    [line] = c.lines
    assert (line.kind, line.amount_low, line.amount_high) == ("replacement", 899.0, 899.0)
    assert (line.source_type, line.source_id) == ("published", "retailer_src")


def test_replacement_counts_only_months_inside_the_window() -> None:
    c = replacement(offer(), 0, 3)  # high end today, low end at month 36
    assert c.monthly_high[0] == 899.0
    assert sum(c.monthly_low) == 0
    assert (c.lines[0].amount_low, c.lines[0].amount_high) == (0.0, 899.0)
    assert replacement(offer(), 10, 15).lines == []
    assert replacement(offer(), None, None).lines == []


def test_combine_adds_month_by_month_and_keeps_lines() -> None:
    flat = Contribution(pay_today=10.0, monthly_low=[1.0] * MONTHS, monthly_high=[2.0] * MONTHS, lines=[])
    part = replacement(offer(), 1, 2)
    c = combine([flat, part])
    assert c.pay_today == 10.0
    assert c.monthly_high[12] == 901.0 and c.monthly_low[24] == 900.0
    assert sum(c.monthly_low) == pytest.approx(36 + 899)
    assert c.lines == part.lines
    assert combine([]).monthly_low == [0.0] * MONTHS
