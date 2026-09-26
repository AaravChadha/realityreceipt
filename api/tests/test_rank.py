"""`rank` against a fake repository, until the real data (tasks 2.1 to 2.3) lands."""

from dataclasses import dataclass, field
from datetime import date

import pytest

from app.engine.rank import OVER_BUDGET, rank
from app.models import (
    CategoryProfile,
    Item,
    LifespanRange,
    ModelEnergy,
    Offer,
    RankedOffer,
    RateValue,
    ShopFilters,
    Source,
    UpkeepItem,
)

THIS_YEAR = date.today().year
RATES = {
    "ga_power_marginal_per_kwh": RateValue(value=0.15, source_id="ga_power_residential_tariff"),
    "egrid_ga_kg_per_kwh": RateValue(value=0.4, source_id="egrid_georgia"),
}
SOURCE_IDS = ["energystar_refrigerators", "ga_power_residential_tariff", "egrid_georgia", "lifespan_src", "upkeep_src", "retailer_src"]
KWH = {"OLD123": 600.0, "NEW456": 380.0}

# 9 years into a 10 to 15 year life: 1 to 6 years left. 14 years in: 0 to 1 left.
USED = Item(id="used", category="refrigerator", brand="Whirlpool", model="OLD123", condition="used_as_is",
            mfg_year=THIS_YEAR - 9, attributes={"width_in": 30.0})
WORN = Item(id="worn", category="refrigerator", brand="Whirlpool", model="OLD123", condition="used_as_is",
            mfg_year=THIS_YEAR - 14, attributes={"width_in": 30.0})
NEW = Item(id="new", category="refrigerator", brand="GE", model="NEW456", condition="new", attributes={"width_in": 29.75})
ITEMS = [USED, WORN, NEW]

USED_OFFER = Offer(item_id="used", price=250.0, seller_type="private", source="user_listing", source_id="user_listing",
                   available_within_days=1)
WORN_OFFER = Offer(item_id="worn", price=150.0, seller_type="private", source="user_listing", source_id="user_listing",
                   available_within_days=1)
NEW_OFFER = Offer(item_id="new", price=899.0, seller_type="retailer", source="retailer_cache", source_id="retailer_src",
                  available_within_days=3)


@dataclass
class FakeRepo:
    new: list[Offer] = field(default_factory=lambda: [NEW_OFFER])

    def rate(self, key: str) -> RateValue:
        return RATES[key]

    def profile(self, category: str) -> CategoryProfile:
        return CategoryProfile(
            category=category,
            energy_dataset_refs=["energystar_refrigerators"],
            usage_assumption="Runs all the time",
            upkeep_schedule=[UpkeepItem(label="Clean coils", cost_low=0, cost_high=20, every_months=12, source_id="upkeep_src")],
            repair_ranges=[],
            lifespan_range=LifespanRange(low_years=10, high_years=15, source_id="lifespan_src"),
            carbon_applicable=True,
        )

    def model_energy(self, brand: str, model: str) -> ModelEnergy | None:
        kwh = KWH.get(model)
        return None if kwh is None else ModelEnergy(kwh_per_year=kwh, source_type="rated", source_id="energystar_refrigerators")

    def new_offers(self, category: str) -> list[Offer]:
        return list(self.new)

    def sources(self) -> list[Source]:
        return [Source(id=i, title=i, publisher="test", url="https://example.org", retrieved_date=date(2026, 9, 26)) for i in SOURCE_IDS]


def ids(ranked: list[RankedOffer]) -> list[str]:
    return [r.offer.item_id for r in ranked]


def test_cheap_used_offer_with_one_year_left_ranks_below_a_new_offer() -> None:
    # Used: $250, 600 kWh x $0.15 = $90 a year, coils $0 to $20 a year, 1 to 6 years left.
    #   cost per year high = 250 / 1 + 90 + 20 = 360.00; low = 250 / 6 + 90 = 131.67
    # New: $899, 380 kWh x $0.15 = $57 a year, coils $0 to $20, 10 to 15 years left.
    #   cost per year high = 899 / 10 + 57 + 20 = 166.90; low = 899 / 15 + 57 = 116.93
    ranked = rank(ShopFilters(), [USED_OFFER, NEW_OFFER], ITEMS, FakeRepo())
    assert ids(ranked) == ["new", "used"]
    new, used = (r.path for r in ranked)
    assert used.pay_today < new.pay_today
    assert (used.expected_life_low, used.expected_life_high) == (1, 6)
    assert (used.cost_per_year_low, used.cost_per_year_high) == (131.67, 360.0)
    assert (new.cost_per_year_low, new.cost_per_year_high) == (116.93, 166.9)
    assert (used.group, new.group) == ("used_as_is", "new")
    assert (used.payment_method, new.payment_method) == ("cash", "cash")


def test_sorted_by_the_high_end_not_the_low_end() -> None:
    # $100 used, 1 to 6 years left: low = 100 / 6 + 90 = 106.67, below new's 116.93;
    # high = 100 / 1 + 110 = 210.00, above new's 166.90. The high end decides.
    bargain = USED_OFFER.model_copy(update={"price": 100.0})
    ranked = rank(ShopFilters(), [bargain, NEW_OFFER], ITEMS, FakeRepo())
    assert ids(ranked) == ["new", "used"]
    assert (ranked[1].path.cost_per_year_low, ranked[1].path.cost_per_year_high) == (106.67, 210.0)


def test_no_cost_per_year_ranks_last() -> None:
    # 0 to 1 years left: the high end of cost per year is not estimated.
    ranked = rank(ShopFilters(), [WORN_OFFER, USED_OFFER, NEW_OFFER], ITEMS, FakeRepo())
    assert ids(ranked) == ["new", "used", "worn"]
    assert ranked[-1].path.cost_per_year_high is None
    assert "past_typical_life" in ranked[-1].path.flags


def test_over_budget_offers_stay_in_the_ranking_with_a_flag() -> None:
    ranked = rank(ShopFilters(budget_today=300), [USED_OFFER, NEW_OFFER], ITEMS, FakeRepo())
    assert ids(ranked) == ["new", "used"]
    flags = {r.offer.item_id: r.path.flags for r in ranked}
    assert flags == {"new": [OVER_BUDGET], "used": []}
    # Exactly at the budget is not over it.
    at_budget = rank(ShopFilters(budget_today=899), [NEW_OFFER], ITEMS, FakeRepo())
    assert at_budget[0].path.flags == []


def test_condition_and_category_filters() -> None:
    offers = [USED_OFFER, NEW_OFFER]
    assert ids(rank(ShopFilters(conditions=["new"]), offers, ITEMS, FakeRepo())) == ["new"]
    assert ids(rank(ShopFilters(conditions=["used_as_is"]), offers, ITEMS, FakeRepo())) == ["used"]
    assert ids(rank(ShopFilters(conditions=[]), offers, ITEMS, FakeRepo())) == ["new", "used"]
    assert rank(ShopFilters(category="washer"), offers, ITEMS, FakeRepo()) == []


def test_need_within_days_excludes_late_and_unknown_delivery() -> None:
    unknown = USED_OFFER.model_copy(update={"item_id": "used2", "available_within_days": None})
    items = [*ITEMS, USED.model_copy(update={"id": "used2"})]
    ranked = rank(ShopFilters(need_within_days=2), [USED_OFFER, NEW_OFFER, unknown], items, FakeRepo())
    assert ids(ranked) == ["used"]  # new takes 3 days; used2 does not say


def test_max_width_excludes_wider_and_unknown_width() -> None:
    no_width = NEW.model_copy(update={"id": "no-width", "attributes": {}})
    wide = NEW.model_copy(update={"id": "wide", "attributes": {"width_in": "35.5"}})
    garbled = NEW.model_copy(update={"id": "garbled", "attributes": {"width_in": "about thirty"}})
    offers = [USED_OFFER, NEW_OFFER] + [NEW_OFFER.model_copy(update={"item_id": i.id}) for i in (no_width, wide, garbled)]
    ranked = rank(ShopFilters(max_width_in=30), offers, [*ITEMS, no_width, wide, garbled], FakeRepo())
    assert ids(ranked) == ["new", "used"]  # 29.75 and 30.0 fit; the rest are wider or unknown


def test_offers_that_cannot_be_priced_are_left_out() -> None:
    price_tag = NEW_OFFER.model_copy(update={"source": "price_tag"})
    used_at_retailer = NEW_OFFER.model_copy(update={"item_id": "used"})
    no_item = USED_OFFER.model_copy(update={"item_id": "missing"})
    refurbished = USED.model_copy(update={"id": "refurb", "condition": "refurbished"})
    refurb_offer = USED_OFFER.model_copy(update={"item_id": "refurb"})
    offers = [price_tag, used_at_retailer, no_item, refurb_offer]
    assert rank(ShopFilters(), offers, [*ITEMS, refurbished], FakeRepo()) == []


def test_an_unrecorded_source_is_refused() -> None:
    unsourced = NEW_OFFER.model_copy(update={"source_id": "somewhere"})
    with pytest.raises(ValueError, match="somewhere"):
        rank(ShopFilters(), [unsourced], ITEMS, FakeRepo())
