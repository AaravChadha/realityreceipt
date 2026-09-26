from app.engine.financing import cash
from app.models import MONTHS


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
