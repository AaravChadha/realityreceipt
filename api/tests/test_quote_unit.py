"""`quote` against a fake repository, until the real data (tasks 2.1 to 2.3) lands."""

from dataclasses import dataclass, field
from datetime import date

import pytest

from app.engine.financing import USER_SOURCE_IDS
from app.engine.quote import INCOMPLETE, quote
from app.models import (
    MONTHS,
    CategoryProfile,
    Item,
    LifespanRange,
    ModelEnergy,
    Offer,
    Path,
    QuoteRequest,
    RateValue,
    Source,
    UpkeepItem,
)

RATES = {
    "ga_power_marginal_per_kwh": RateValue(value=0.15, source_id="ga_power_residential_tariff"),
    "egrid_ga_kg_per_kwh": RateValue(value=0.4, source_id="egrid_georgia"),
    "g19_card_apr_assessed": RateValue(value=0.2215, source_id="frb_g19"),
    "pal_rate_cap": RateValue(value=0.28, source_id="ncua_pals_ii"),
    "pal_fee_cap": RateValue(value=20.0, source_id="ncua_pals_ii"),
    "pal_max_amount": RateValue(value=2000.0, source_id="ncua_pals_ii"),
}
SOURCE_IDS = ["energystar_refrigerators", "ga_power_residential_tariff", "egrid_georgia", "lifespan_src", "upkeep_src", "retailer_src", "frb_g19", "ncua_pals_ii"]

OLD = Item(id="old", category="refrigerator", brand="Whirlpool", model="OLD123", condition="used_as_is", mfg_year=date.today().year - 12)
NEW = Item(id="new-a", category="refrigerator", brand="GE", model="NEW456", condition="new")
LISTING = Offer(item_id="old", price=250.0, seller_type="private", source="user_listing", source_id="user_listing")
NEW_OFFERS = [
    Offer(item_id="new-b", price=1099.0, seller_type="retailer", source="retailer_cache", source_id="retailer_src"),
    Offer(item_id="new-a", price=899.0, seller_type="retailer", source="retailer_cache", source_id="retailer_src"),
]


@dataclass
class FakeRepo:
    new: list[Offer] = field(default_factory=lambda: list(NEW_OFFERS))
    source_ids: list[str] = field(default_factory=lambda: list(SOURCE_IDS))
    energy: dict[str, float] = field(default_factory=lambda: {"OLD123": 600.0, "NEW456": 380.0})
    catalog: dict[str, Item] = field(default_factory=lambda: {NEW.id: NEW})

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

    def model_energy(self, brand: str, model: str, product_class: str | float | None = None) -> ModelEnergy | None:
        kwh = self.energy.get(model)
        return None if kwh is None else ModelEnergy(kwh_per_year=kwh, source_type="rated", source_id="energystar_refrigerators")

    def new_offers(self, category: str) -> list[Offer]:
        return list(self.new)

    def sources(self) -> list[Source]:
        return [Source(id=i, title=i, publisher="test", url="https://example.org", retrieved_date=date(2026, 9, 26)) for i in self.source_ids]

    def item(self, id: str) -> Item | None:
        return self.catalog.get(id)

    def bnpl_terms(self) -> None:
        return None

    def standard_ceiling(self, mfg_year: int, product_class: str, volume_cuft: float) -> None:
        return None


def slice_request(**overrides) -> QuoteRequest:
    return QuoteRequest(**{"items": [OLD, NEW], "offers": [LISTING], **overrides})


def by_group(paths: list[Path]) -> dict[str, Path]:
    """Each group's cash path (since task 3.3 the new offer is also paid three other ways)."""
    return {p.group: p for p in paths if p.payment_method == "cash"}


def test_slice_returns_both_groups_complete_paths_first() -> None:
    paths = quote(slice_request(), FakeRepo())
    cash_paths = [p for p in paths if p.payment_method == "cash"]
    assert [p.group for p in cash_paths] == ["new", "used_as_is"]
    # Since task 3.3.2 the used unit, past its typical life, has no replacement priced, so it is
    # flagged and sorts after new cash even though its total is lower.
    assert INCOMPLETE in cash_paths[1].flags and INCOMPLETE not in cash_paths[0].flags
    assert cash_paths[1].total_3yr_high < cash_paths[0].total_3yr_high
    # Since task 3.3.1, paths flagged `costs_not_estimated` sort after the complete ones.
    keys = [(INCOMPLETE in p.flags, p.total_3yr_high, p.pay_today) for p in paths]
    assert keys == sorted(keys)


def test_used_path_past_typical_life() -> None:
    used = by_group(quote(slice_request(), FakeRepo()))["used_as_is"]
    # 250 today; 600 kWh x $0.15 = $7.50 a month; coils $0 to $20 at months 12 and 24;
    # 12 years into a 10 to 15 year life: at or past its typical life, so since task 3.3.2 no
    # replacement is bought and when it will need replacing is not estimated.
    assert used.pay_today == 250.0
    assert (used.total_3yr_low, used.total_3yr_high) == (520.0, 560.0)
    assert used.monthly_high[0] == 250.0 + 7.5
    assert (used.expected_life_low, used.expected_life_high) == (0, 3)
    assert (used.cost_per_year_low, used.cost_per_year_high) == (round(250 / 3 + 90, 2), None)
    assert used.flags == ["past_typical_life", INCOMPLETE]
    replacement = used.lines[-1]
    assert (replacement.source_type, replacement.amount_low, replacement.amount_high) == ("not_estimated", None, None)
    assert used.carbon_kg == 720.0
    assert used.carbon_source_ids == ["energystar_refrigerators", "egrid_georgia"]
    assert [line.label for line in used.lines] == [
        "Price today", "Electricity", "Extra use from age", "Clean coils", "Replacement when it wears out",
    ]
    aging = used.lines[2]
    assert (aging.source_type, aging.amount_low, aging.amount_high) == ("not_estimated", None, None)


def test_new_path_is_the_cheapest_cached_offer() -> None:
    new = by_group(quote(slice_request(), FakeRepo()))["new"]
    assert new.pay_today == 899.0
    assert (new.total_3yr_low, new.total_3yr_high) == (1070.0, 1110.0)
    assert (new.cost_per_year_low, new.cost_per_year_high) == (round(899 / 15 + 57, 2), round(899 / 10 + 57 + 20, 2))
    assert (new.expected_life_low, new.expected_life_high) == (10, 15)
    assert new.carbon_kg == 456.0
    assert new.flags == []
    assert not any(line.kind == "replacement" for line in new.lines)


def test_totals_are_the_sums_of_the_arrays() -> None:
    for p in quote(slice_request(), FakeRepo()):
        assert len(p.monthly_low) == len(p.monthly_high) == MONTHS
        assert p.total_3yr_low == round(sum(p.monthly_low), 2)
        assert p.total_3yr_high == round(sum(p.monthly_high), 2)


def test_every_line_is_sourced_and_nothing_is_fixture() -> None:
    known = set(SOURCE_IDS) | USER_SOURCE_IDS
    for p in quote(slice_request(), FakeRepo()):
        assert "fixture" not in p.flags
        for line in p.lines:
            assert (line.source_id is None) == (line.source_type == "not_estimated")
            assert line.source_id is None or line.source_id in known


def test_unknown_model_leaves_energy_and_carbon_blank() -> None:
    used = by_group(quote(slice_request(), FakeRepo(energy={"NEW456": 380.0})))["used_as_is"]
    electricity = used.lines[1]
    assert (electricity.label, electricity.source_type, electricity.amount_high) == ("Electricity", "not_estimated", None)
    assert (used.carbon_kg, used.carbon_source_ids) == (None, [])
    assert used.cost_per_year_low == round(250 / 3, 2)


def test_new_offer_without_its_item_has_no_energy_figure() -> None:
    new = by_group(quote(slice_request(items=[OLD]), FakeRepo(catalog={})))["new"]
    assert new.lines[1].source_type == "not_estimated"
    assert new.carbon_kg is None


def test_listing_without_its_item_is_left_out() -> None:
    paths = quote(slice_request(items=[NEW]), FakeRepo())
    assert {p.group for p in paths} == {"new"}


def test_no_new_offers_leaves_the_replacement_blank() -> None:
    paths = quote(slice_request(), FakeRepo(new=[]))
    assert [p.group for p in paths] == ["used_as_is"]
    [replacement] = [line for line in paths[0].lines if line.kind == "replacement"]
    assert (replacement.source_type, replacement.amount_high) == ("not_estimated", None)


def test_unknown_manufacture_year_leaves_life_blank() -> None:
    undated = OLD.model_copy(update={"mfg_year": None})
    used = by_group(quote(slice_request(items=[undated, NEW]), FakeRepo()))["used_as_is"]
    assert (used.expected_life_low, used.cost_per_year_low, used.cost_per_year_high) == (None, None, None)
    # Since task 3.3.2 its replacement timing is shown as not estimated, which flags the path.
    assert used.flags == [INCOMPLETE]
    [replacement] = [line for line in used.lines if line.kind == "replacement"]
    assert (replacement.source_type, replacement.amount_high) == ("not_estimated", None)
    assert "year it was made is unknown" in replacement.formula


def test_a_source_missing_from_the_repository_is_refused() -> None:
    with pytest.raises(ValueError, match="egrid_georgia"):
        quote(slice_request(), FakeRepo(source_ids=[s for s in SOURCE_IDS if s != "egrid_georgia"]))
