"""`quote` with every kind of path (PLAN.md tasks 3.3 to 3.3.3), against a fake repository."""

from dataclasses import dataclass, field
from datetime import date

import pytest

from app.engine.quote import INCOMPLETE, quote
from app.engine.rank import rank
from app.models import (
    MONTHS,
    BnplTerms,
    CategoryProfile,
    Item,
    Lease,
    LifespanRange,
    ModelEnergy,
    Offer,
    Path,
    QuoteRequest,
    RateValue,
    RepairRange,
    ShopFilters,
    Source,
    UpkeepItem,
)

THIS_YEAR = date.today().year

RATES = {
    "ga_power_marginal_per_kwh": RateValue(value=0.15, source_id="ga_power_residential_tariff"),
    "egrid_ga_kg_per_kwh": RateValue(value=0.4, source_id="egrid_georgia"),
    "g19_card_apr_assessed": RateValue(value=0.2215, source_id="frb_g19"),
    "pal_rate_cap": RateValue(value=0.28, source_id="ncua_pals_ii"),
    "pal_fee_cap": RateValue(value=20.0, source_id="ncua_pals_ii"),
    "pal_max_amount": RateValue(value=2000.0, source_id="ncua_pals_ii"),
}
SOURCE_IDS = [
    "energystar_refrigerators", "ga_power_residential_tariff", "egrid_georgia", "frb_g19", "ncua_pals_ii",
    "lifespan_src", "upkeep_src", "repair_src", "repair_src_2", "retailer_src", "doe_standards", "afterpay_terms",
    "doe_historical",
]
TERMS = BnplTerms(provider="Afterpay", installments=4, interval_weeks=2, apr=0.0, source_id="afterpay_terms")

# The one you have: a 2004 unit with no rating, so its energy is the DOE ceiling for its adjusted volume.
CURRENT = Item(
    id="current", category="refrigerator", brand="Frigidaire", model="FRT18B5", condition="used_as_is",
    mfg_year=2004, year_confidence="low", attributes={"product_class": "3", "adjusted_volume_cuft": 20.5},
)
USED = Item(id="used", category="refrigerator", brand="Whirlpool", model="OLD123", condition="used_as_is", mfg_year=THIS_YEAR - 8)
REFURB = Item(id="refurb", category="refrigerator", brand="LG", model="REF789", condition="refurbished", mfg_year=THIS_YEAR - 3, warranty_months=6)
LEASED = Item(id="leased", category="refrigerator", brand="Samsung", model="RTO111", condition="new")
NEW = Item(id="new-a", category="refrigerator", brand="GE", model="NEW456", condition="new")

USED_OFFER = Offer(item_id="used", price=250.0, seller_type="private", source="user_listing", source_id="user_listing")
REFURB_OFFER = Offer(item_id="refurb", price=420.0, seller_type="refurbisher", source="user_listing", source_id="user_listing")
LEASE_OFFER = Offer(item_id="leased", price=800.0, seller_type="rent_to_own", source="user_listing", source_id="user_listing")
NEW_OFFERS = [
    Offer(item_id="new-b", price=1099.0, seller_type="retailer", source="retailer_cache", source_id="retailer_src"),
    Offer(item_id="new-a", price=899.0, seller_type="retailer", source="retailer_cache", source_id="retailer_src"),
]
LEASE = Lease(weekly_payment=30.0, term_weeks=52, cash_price=800.0, fees=20.0, early_purchase_rule="pct_of_remaining", early_purchase_pct=0.5)


@dataclass
class FakeRepo:
    new: list[Offer] = field(default_factory=lambda: list(NEW_OFFERS))
    bnpl: BnplTerms | None = None
    repairs: list[RepairRange] = field(
        default_factory=lambda: [
            RepairRange(label="Thermostat", cost_low=150, cost_high=300, source_id="repair_src"),
            RepairRange(label="Compressor", cost_low=600, cost_high=1200, source_id="repair_src_2"),
        ]
    )
    energy: dict[str, float] = field(default_factory=lambda: {"OLD123": 600.0, "REF789": 450.0, "RTO111": 400.0, "NEW456": 380.0})
    catalog: dict[str, Item] = field(default_factory=lambda: {NEW.id: NEW})
    ceiling_calls: list[tuple[int, str, float]] = field(default_factory=list)
    energy_refs: list[str] = field(default_factory=lambda: ["energystar_refrigerators"])
    lifespan: tuple[float, float] = (10, 15)
    historical: set[str] = field(default_factory=set)  # models rated from a second source
    years: dict[str, int] = field(default_factory=dict)  # model -> year from the rating data

    def rate(self, key: str) -> RateValue:
        return RATES[key]

    def profile(self, category: str) -> CategoryProfile:
        return CategoryProfile(
            category=category,
            energy_dataset_refs=self.energy_refs,
            usage_assumption="Runs all the time",
            upkeep_schedule=[UpkeepItem(label="Clean coils", cost_low=0, cost_high=20, every_months=12, source_id="upkeep_src")],
            repair_ranges=self.repairs,
            lifespan_range=LifespanRange(low_years=self.lifespan[0], high_years=self.lifespan[1], source_id="lifespan_src"),
            carbon_applicable=True,
        )

    def model_energy(self, brand: str, model: str) -> ModelEnergy | None:
        kwh = self.energy.get(model)
        source_id = "doe_historical" if model in self.historical else "energystar_refrigerators"
        return None if kwh is None else ModelEnergy(kwh_per_year=kwh, source_type="rated", source_id=source_id)

    def new_offers(self, category: str) -> list[Offer]:
        return list(self.new)

    def sources(self) -> list[Source]:
        return [Source(id=i, title=i, publisher="test", url="https://example.org", retrieved_date=date(2026, 9, 26)) for i in SOURCE_IDS]

    def item(self, id: str) -> Item | None:
        return self.catalog.get(id)

    def bnpl_terms(self) -> BnplTerms | None:
        return self.bnpl

    def model_year(self, brand: str, model: str) -> int | None:
        return self.years.get(model)

    def standard_ceiling(self, mfg_year: int, product_class: str, volume_cuft: float) -> ModelEnergy | None:
        self.ceiling_calls.append((mfg_year, product_class, volume_cuft))
        if product_class != "3":
            return None
        return ModelEnergy(kwh_per_year=8.0 * volume_cuft + 300.0, source_type="published", source_id="doe_standards")


def full_request(**overrides) -> QuoteRequest:
    return QuoteRequest(**{
        "current": CURRENT,
        "items": [USED, REFURB, LEASED],
        "offers": [USED_OFFER, REFURB_OFFER, LEASE_OFFER],
        "lease": LEASE,
        **overrides,
    })


def pick(paths: list[Path], group: str, method: str | None) -> Path:
    [path] = [p for p in paths if p.group == group and p.payment_method == method]
    return path


ALL_KINDS = {
    ("repair", None), ("used_as_is", "cash"), ("refurbished", "cash"),
    ("new", "cash"), ("new", "card"), ("new", "bnpl"), ("new", "pal"),
    ("rent_to_own", "rto_full"), ("rent_to_own", "rto_buyout"),
}


def sort_keys(paths: list[Path]) -> list[tuple[bool, float, float]]:
    return [(INCOMPLETE in p.flags, p.total_3yr_high, p.pay_today) for p in paths]


def test_full_request_returns_nine_paths_complete_ones_first() -> None:
    paths = quote(full_request(), FakeRepo())
    assert len(paths) == 9
    assert {(p.group, p.payment_method) for p in paths} == ALL_KINDS
    # Complete paths by total (high end), then pay today; then the flagged ones in the same order.
    assert sort_keys(paths) == sorted(sort_keys(paths))
    # Blank costs here: buy now pay later with no cached terms, and (since task 3.3.2) the 2004
    # unit's replacement timing, since it is past its typical life.
    flagged = [(p.group, p.payment_method) for p in paths if INCOMPLETE in p.flags]
    assert sorted(flagged, key=str) == [("new", "bnpl"), ("repair", None)]
    assert paths[-len(flagged):] == [p for p in paths if INCOMPLETE in p.flags]


def test_incomplete_rent_to_own_sorts_after_complete_new_cash() -> None:
    # The lease's unit is not in the request, so neither lease path has an electricity figure.
    paths = quote(full_request(offers=[USED_OFFER, REFURB_OFFER]), FakeRepo())
    new_cash, buyout = pick(paths, "new", "cash"), pick(paths, "rent_to_own", "rto_buyout")
    assert buyout.lines[2].source_type == "not_estimated"  # payments, fees, then electricity
    assert INCOMPLETE in buyout.flags and INCOMPLETE not in new_cash.flags
    assert buyout.total_3yr_high < new_cash.total_3yr_high  # $855.00 against $1,110.00
    assert paths.index(buyout) > paths.index(new_cash)
    assert sort_keys(paths) == sorted(sort_keys(paths))


def test_equal_totals_sort_by_pay_today() -> None:
    # With 0% terms, buy now pay later totals the same as cash but pays less today.
    paths = quote(full_request(), FakeRepo(bnpl=TERMS))
    cash, bnpl = pick(paths, "new", "cash"), pick(paths, "new", "bnpl")
    assert bnpl.total_3yr_high == cash.total_3yr_high and bnpl.pay_today < cash.pay_today
    assert paths.index(bnpl) < paths.index(cash)


def test_ranked_offers_carry_the_flag() -> None:
    # `rank` builds its paths with `quote`'s `_cash_path`, so it gets the same flag.
    repo = FakeRepo(energy={k: v for k, v in FakeRepo().energy.items() if k != "OLD123"})
    [blank, rated] = [rank(ShopFilters(), [offer], [USED, NEW], repo)[0].path for offer in (USED_OFFER, NEW_OFFERS[1])]
    assert INCOMPLETE in blank.flags
    assert INCOMPLETE not in rated.flags


def test_blank_electricity_flags_the_path() -> None:
    repo = FakeRepo(energy={k: v for k, v in FakeRepo().energy.items() if k != "OLD123"})
    used = pick(quote(full_request(), repo), "used_as_is", "cash")
    assert used.lines[1].source_type == "not_estimated"
    assert INCOMPLETE in used.flags


def test_blank_electricity_does_not_count_for_a_category_without_energy_data() -> None:
    repo = FakeRepo(energy={k: v for k, v in FakeRepo().energy.items() if k != "OLD123"}, energy_refs=[])
    used = pick(quote(full_request(), repo), "used_as_is", "cash")
    assert used.lines[1].source_type == "not_estimated"
    assert INCOMPLETE not in used.flags


def test_blank_financing_flags_the_path_and_cached_terms_do_not() -> None:
    assert INCOMPLETE in pick(quote(full_request(), FakeRepo()), "new", "bnpl").flags
    assert INCOMPLETE not in pick(quote(full_request(), FakeRepo(bnpl=TERMS)), "new", "bnpl").flags


def test_blank_replacement_flags_the_path() -> None:
    # 8 years into a 10 to 15 year life: replaced at month 24 at the high end, and no new offer prices it.
    paths = quote(QuoteRequest(items=[USED], offers=[USED_OFFER]), FakeRepo(new=[]))
    [used] = paths
    [line] = [line for line in used.lines if line.kind == "replacement"]
    assert line.source_type == "not_estimated"
    assert INCOMPLETE in used.flags


def test_the_blank_aging_line_alone_does_not_flag_a_path() -> None:
    used = pick(quote(full_request(), FakeRepo()), "used_as_is", "cash")
    assert any(line.label == "Extra use from age" and line.source_type == "not_estimated" for line in used.lines)
    assert INCOMPLETE not in used.flags


@pytest.mark.parametrize("terms", [None, TERMS])
def test_each_paths_totals_equal_the_sums_of_its_arrays(terms: BnplTerms | None) -> None:
    for p in quote(full_request(), FakeRepo(bnpl=terms)):
        assert len(p.monthly_low) == len(p.monthly_high) == MONTHS
        assert p.total_3yr_low == round(sum(p.monthly_low), 2)
        assert p.total_3yr_high == round(sum(p.monthly_high), 2)


@pytest.mark.parametrize("terms", [None, TERMS])
def test_financed_paths_count_the_price_once(terms: BnplTerms | None) -> None:
    paths = quote(full_request(), FakeRepo(bnpl=terms))
    cash = pick(paths, "new", "cash")
    for method in ("card", "bnpl", "pal"):
        p = pick(paths, "new", method)
        [price] = [line for line in p.lines if line.kind == "purchase"]
        assert (price.label, price.amount_low, price.amount_high) == ("Price", 899.0, 899.0)
        [cost] = [line for line in p.lines if line.kind == "financing"]
        # Same unit and running costs as cash, so the only difference is what the method costs.
        assert p.total_3yr_high == pytest.approx(cash.total_3yr_high + (cost.amount_high or 0.0), abs=0.02)


def test_buy_now_pay_later_without_terms_stays_not_estimated() -> None:
    bnpl = pick(quote(full_request(), FakeRepo()), "new", "bnpl")
    [cost] = [line for line in bnpl.lines if line.kind == "financing"]
    assert (cost.source_type, cost.amount_high) == ("not_estimated", None)
    assert bnpl.pay_today == 899.0
    assert "bnpl_terms_not_an_offer" not in bnpl.flags


def test_buy_now_pay_later_with_terms_is_flagged_as_not_an_offer() -> None:
    bnpl = pick(quote(full_request(), FakeRepo(bnpl=TERMS)), "new", "bnpl")
    [cost] = [line for line in bnpl.lines if line.kind == "financing"]
    assert (cost.source_type, cost.source_id) == ("published", "afterpay_terms")
    assert "bnpl_terms_not_an_offer" in bnpl.flags
    assert bnpl.pay_today == pytest.approx(899.0 / 4, abs=0.01)


def test_pal_is_flagged_and_left_out_over_the_loan_cap() -> None:
    assert "pal_caps_not_an_offer" in pick(quote(full_request(), FakeRepo()), "new", "pal").flags
    pricey = [Offer(item_id="new-a", price=2500.0, seller_type="retailer", source="retailer_cache", source_id="retailer_src")]
    paths = quote(full_request(), FakeRepo(new=pricey))
    assert ("new", "pal") not in {(p.group, p.payment_method) for p in paths}
    assert len(paths) == 8


def test_repair_from_the_users_quote() -> None:
    repair = pick(quote(full_request(repair_quote_low=180.0, repair_quote_high=260.0), FakeRepo()), "repair", None)
    [line] = [line for line in repair.lines if line.kind == "repair"]
    assert (line.source_type, line.source_id, line.amount_low, line.amount_high) == ("user_entered", "user", 180.0, 260.0)
    assert repair.pay_today == 260.0


def test_repair_from_the_published_ranges() -> None:
    repair = pick(quote(full_request(), FakeRepo()), "repair", None)
    [line] = [line for line in repair.lines if line.kind == "repair"]
    assert (line.source_type, line.amount_low, line.amount_high) == ("published", 150.0, 1200.0)
    assert (line.source_id, line.other_source_ids) == ("repair_src", ["repair_src_2"])
    assert "Thermostat" in line.formula and "Compressor" in line.formula


def test_repair_is_left_out_without_a_current_unit_or_a_cost() -> None:
    assert "repair" not in {p.group for p in quote(full_request(current=None), FakeRepo())}
    assert "repair" not in {p.group for p in quote(full_request(), FakeRepo(repairs=[]))}


def test_old_unit_energy_is_the_standard_ceiling_for_its_adjusted_volume() -> None:
    repo = FakeRepo()
    repair = pick(quote(full_request(), repo), "repair", None)
    electricity = repair.lines[1]
    assert (electricity.label, electricity.source_type, electricity.source_id) == ("Electricity, up to when new", "published", "doe_standards")
    assert electricity.amount_high == round((8.0 * 20.5 + 300.0) * 0.15, 2)
    assert repo.ceiling_calls == [(2004, "3", 20.5)]


def test_total_volume_alone_gives_no_ceiling() -> None:
    repo = FakeRepo()
    total_only = CURRENT.model_copy(update={"attributes": {"product_class": "3", "volume_cuft": 20.5}})
    repair = pick(quote(full_request(current=total_only), repo), "repair", None)
    assert repair.lines[1].source_type == "not_estimated"
    assert repair.carbon_kg is None
    assert repo.ceiling_calls == []


def test_refurbished_path_shows_its_warranty() -> None:
    refurb = pick(quote(full_request(), FakeRepo()), "refurbished", "cash")
    assert "warranty_6_months" in refurb.flags
    assert any(line.label == "Extra use from age" for line in refurb.lines)


def test_rent_to_own_paths_come_from_the_lease() -> None:
    paths = quote(full_request(), FakeRepo())
    full, buyout = pick(paths, "rent_to_own", "rto_full"), pick(paths, "rent_to_own", "rto_buyout")
    assert full.lines[0].label == "Total of lease payments"
    assert buyout.lines[0].label == "Payments plus buyout at week 1"
    assert {line.source_id for p in (full, buyout) for line in p.lines if line.kind == "financing"} == {"user_lease"}
    # The leased unit is new, so its energy is rated and it has its whole life ahead.
    assert (full.expected_life_low, full.expected_life_high) == (10, 15)
    assert full.carbon_kg == 400 * 0.4 * 3
    assert not any(p.group == "rent_to_own" for p in quote(full_request(lease=None), FakeRepo()))


def test_lease_without_its_unit_leaves_energy_and_life_blank() -> None:
    full = pick(quote(full_request(offers=[USED_OFFER, REFURB_OFFER]), FakeRepo()), "rent_to_own", "rto_full")
    assert full.lines[2].source_type == "not_estimated"  # payments, fees, then electricity
    assert (full.expected_life_low, full.cost_per_year_high, full.carbon_kg) == (None, None, None)


def test_a_rent_to_own_listing_is_not_also_a_used_path() -> None:
    used_lease = LEASED.model_copy(update={"condition": "used_as_is", "mfg_year": THIS_YEAR - 2})
    paths = quote(full_request(items=[USED, REFURB, used_lease]), FakeRepo())
    assert [p.group for p in paths].count("used_as_is") == 1


def test_flags_on_the_old_unit() -> None:
    paths = quote(full_request(), FakeRepo())
    repair = pick(paths, "repair", None)
    assert {"past_typical_life", "test_procedure_changed", "year_from_serial_low_confidence"} <= set(repair.flags)
    assert (repair.cost_per_year_low, repair.cost_per_year_high) == (None, None)
    others = [p for p in paths if p.group != "repair"]
    assert not any("test_procedure_changed" in p.flags or "year_from_serial_low_confidence" in p.flags for p in others)


def test_no_test_procedure_flag_without_a_newer_unit() -> None:
    paths = quote(QuoteRequest(current=CURRENT), FakeRepo(new=[]))
    assert [p.group for p in paths] == ["repair"]
    assert "test_procedure_changed" not in paths[0].flags


def test_nothing_is_invented_from_an_empty_request() -> None:
    assert quote(QuoteRequest(), FakeRepo(new=[])) == []


# Task 3.3.2: replacement and past-typical-life honesty.


def used_path(item: Item, repo: FakeRepo | None = None) -> Path:
    """The used-as-is path for `item` (id "used") sold through `USED_OFFER`."""
    return pick(quote(QuoteRequest(items=[item], offers=[USED_OFFER]), repo or FakeRepo()), "used_as_is", "cash")


def replacement_lines(path: Path) -> list:
    return [line for line in path.lines if line.kind == "replacement"]


def test_a_20_year_old_unit_gets_no_replacement_amount() -> None:
    old = used_path(USED.model_copy(update={"mfg_year": THIS_YEAR - 20}))
    assert {"past_typical_life", INCOMPLETE} <= set(old.flags)
    [line] = replacement_lines(old)
    assert (line.source_type, line.amount_low, line.amount_high) == ("not_estimated", None, None)
    assert line.formula.startswith("When it will need replacing is not estimated")
    # $250 today, 600 kWh x $0.15 = $7.50 a month for all 36 months, coils $0 to $20 at months 12
    # and 24, and no $899 replacement anywhere in either array.
    assert (old.total_3yr_low, old.total_3yr_high) == (520.0, 560.0)
    assert (old.cost_per_year_low, old.cost_per_year_high) == (None, None)
    assert old.carbon_kg == 600 * 0.4 * 3


def test_after_a_replacement_at_month_12_electricity_is_the_new_units() -> None:
    # 9 years into a 10 to 15 year life: replaced at month 12 at the soonest (the high array),
    # not inside the 36 months at the latest (the low array).
    used = used_path(USED.model_copy(update={"mfg_year": THIS_YEAR - 9}))
    [old_line, new_line] = [line for line in used.lines if line.label.startswith("Electricity")]
    assert (old_line.source_type, old_line.amount_high) == ("rated", 90.0)  # 600 kWh x $0.15
    assert (new_line.label, new_line.source_type, new_line.amount_high) == ("Electricity, replacement unit", "rated", 57.0)  # 380 kWh
    assert "month 12" in old_line.formula and "month 12" in new_line.formula
    # High array: $7.50 a month (600 kWh) to month 11, then $4.75 (380 kWh); month 12 also buys
    # the $899 replacement and the $20 coil cleaning.
    assert used.monthly_high[11] == 7.5
    assert used.monthly_high[12] == 4.75 + 20.0 + 899.0
    assert used.monthly_high[13] == used.monthly_high[35] == 4.75
    assert used.total_3yr_high == 250 + 12 * 7.5 + 24 * 4.75 + 40 + 899
    # Low array: it lasts past the window, so the old unit runs all 36 months.
    assert used.monthly_low[13] == used.monthly_low[35] == 7.5
    # Carbon: the higher timeline, here the old unit all 36 months (720 kg against 240 + 304 = 544).
    assert used.carbon_kg == 720.0
    # Cost per year of use stays this unit's: $250 / 1 year + $90 + $20.
    assert used.cost_per_year_high == 360.0
    assert INCOMPLETE not in used.flags


def test_a_replacement_unit_without_a_figure_leaves_its_electricity_blank() -> None:
    # The cheapest new offer's item is in neither the catalog nor the request.
    used = used_path(USED.model_copy(update={"mfg_year": THIS_YEAR - 9}), FakeRepo(catalog={}))
    [new_line] = [line for line in used.lines if line.label == "Electricity, replacement unit"]
    assert (new_line.source_type, new_line.amount_high) == ("not_estimated", None)
    assert used.monthly_high[11] == 7.5 and used.monthly_high[13] == 0.0
    assert used.carbon_kg is None and used.carbon_source_ids == []
    assert INCOMPLETE in used.flags


@pytest.mark.parametrize(("item", "offer", "group"), [(USED, USED_OFFER, "used_as_is"), (REFURB, REFURB_OFFER, "refurbished")])
def test_a_used_unit_of_unknown_age_has_its_replacement_timing_not_estimated(item: Item, offer: Offer, group: str) -> None:
    undated = item.model_copy(update={"mfg_year": None})
    path = pick(quote(QuoteRequest(items=[undated], offers=[offer]), FakeRepo()), group, "cash")
    [line] = replacement_lines(path)
    assert (line.source_type, line.amount_high) == ("not_estimated", None)
    assert "year it was made is unknown" in line.formula
    assert INCOMPLETE in path.flags


def test_new_and_unknown_lease_units_get_no_blank_replacement_line() -> None:
    paths = quote(full_request(offers=[USED_OFFER, REFURB_OFFER]), FakeRepo())
    for p in (pick(paths, "new", "cash"), pick(paths, "rent_to_own", "rto_full")):
        assert replacement_lines(p) == []


def test_ranked_past_life_offer_gets_no_replacement_amount() -> None:
    old = USED.model_copy(update={"mfg_year": THIS_YEAR - 20})
    [ranked] = rank(ShopFilters(), [USED_OFFER], [old], FakeRepo())
    [line] = replacement_lines(ranked.path)
    assert (line.source_type, line.amount_high) == ("not_estimated", None)
    assert {"past_typical_life", INCOMPLETE} <= set(ranked.path.flags)


def test_both_arrays_switch_in_the_same_month_on_a_single_figure_life() -> None:
    # A 13-year typical life (as in the real profile), 12 years in: replaced at month 12 in both arrays.
    used = used_path(USED.model_copy(update={"mfg_year": THIS_YEAR - 12}), FakeRepo(lifespan=(13, 13)))
    for monthly, coils in ((used.monthly_low, 0.0), (used.monthly_high, 20.0)):
        assert monthly[11] == 7.5
        assert monthly[12] == 4.75 + coils + 899.0
        assert monthly[13] == monthly[35] == 4.75
    old_line = used.lines[1]
    assert old_line.formula.endswith("Runs until it is replaced: month 12")
    # 600 kWh x 0.4 kg for 1 year, then 380 kWh x 0.4 kg for 2 years.
    assert used.carbon_kg == 240.0 + 304.0


def test_arrays_switch_in_different_months_and_carbon_takes_the_higher_timeline() -> None:
    # A 10 to 11 year life, 9 years in: replaced at month 12 (high array) or month 24 (low array).
    repo = FakeRepo(lifespan=(10, 11), historical={"NEW456"})
    used = used_path(USED.model_copy(update={"mfg_year": THIS_YEAR - 9}), repo)
    assert (used.monthly_high[11], used.monthly_high[12], used.monthly_high[13]) == (7.5, 4.75 + 20.0 + 899.0, 4.75)
    assert (used.monthly_low[23], used.monthly_low[24], used.monthly_low[25]) == (7.5, 4.75 + 899.0, 4.75)
    assert "month 12 at the soonest, month 24 at the latest" in used.lines[1].formula
    # Month 24: 480 + 152 = 632 kg; month 12: 240 + 304 = 544 kg. Both units' sources are named.
    assert used.carbon_kg == 632.0
    assert used.carbon_source_ids == ["energystar_refrigerators", "doe_historical", "egrid_georgia"]


def test_carbon_names_only_the_sources_of_the_timeline_it_uses() -> None:
    # 10 to 15 year life, 9 years in: the higher timeline is the old unit alone (720 kg).
    used = used_path(USED.model_copy(update={"mfg_year": THIS_YEAR - 9}), FakeRepo(historical={"NEW456"}))
    assert used.carbon_kg == 720.0
    assert used.carbon_source_ids == ["energystar_refrigerators", "egrid_georgia"]
    assert any(line.source_id == "doe_historical" for line in used.lines)  # the replacement's electricity


def test_a_single_figure_life_reads_as_one_number() -> None:
    old = used_path(USED.model_copy(update={"mfg_year": THIS_YEAR - 20}), FakeRepo(lifespan=(13, 13)))
    [line] = replacement_lines(old)
    assert "typical 13 year life" in line.formula


# Task 3.3.3: one energy lookup for every path, including the shop.

CLASS_3 = {"product_class": "3", "adjusted_volume_cuft": 20.5}  # ceiling: 8 x 20.5 + 300 = 464 kWh


def unit(model: str = "UNRATED", year: int | None = THIS_YEAR - 9, **attributes: str | float) -> Item:
    """A used unit (id "used", sold through `USED_OFFER`); the fake rates only OLD123 and the new models."""
    return USED.model_copy(update={"model": model, "mfg_year": year, "attributes": attributes})


PARITY_UNITS = {
    "rated": unit("OLD123"),
    "label kWh": unit(label_kwh_per_year=700.0),
    "standard ceiling": unit(year=2004, **CLASS_3),
    "no figure": unit(),
    "year from the rating data": unit("OLD123", year=None),
}


@pytest.mark.parametrize("name", PARITY_UNITS)
def test_quote_and_rank_give_a_used_unit_the_same_electricity(name: str) -> None:
    item = PARITY_UNITS[name]
    repo = FakeRepo(years={"OLD123": THIS_YEAR - 9})
    quoted = used_path(item, repo)
    [ranked] = rank(ShopFilters(), [USED_OFFER], [item], repo)
    running = [line for line in quoted.lines if line.kind == "running"]
    assert running == [line for line in ranked.path.lines if line.kind == "running"]
    # The whole path matches too, apart from the flag that compares units across one quote.
    same = [f for f in quoted.flags if f != "test_procedure_changed"]
    assert quoted.model_copy(update={"flags": same}) == ranked.path


def test_lookup_takes_the_rated_figure_first() -> None:
    repo = FakeRepo()
    line = used_path(unit("OLD123", year=2004, label_kwh_per_year=700.0, **CLASS_3), repo).lines[1]
    assert (line.source_type, line.source_id, line.amount_high) == ("rated", "energystar_refrigerators", 90.0)
    assert repo.ceiling_calls == []


def test_lookup_rated_figure_can_come_from_the_historical_ratings() -> None:
    line = used_path(unit("OLD123"), FakeRepo(historical={"OLD123"})).lines[1]
    assert (line.source_type, line.source_id, line.amount_high) == ("rated", "doe_historical", 90.0)


def test_lookup_then_the_label_kwh_before_the_ceiling() -> None:
    repo = FakeRepo()
    used = used_path(unit(year=2004, label_kwh_per_year=700.0, **CLASS_3), repo)
    line = used.lines[1]
    assert (line.label, line.source_type, line.source_id, line.amount_high) == ("Electricity", "user_entered", "user", 105.0)
    assert used.carbon_source_ids == ["user", "egrid_georgia"]
    assert repo.ceiling_calls == []


def test_lookup_then_the_standard_ceiling() -> None:
    repo = FakeRepo()
    line = used_path(unit(year=2004, **CLASS_3), repo).lines[1]
    assert (line.label, line.source_type, line.source_id) == ("Electricity, up to when new", "published", "doe_standards")
    assert line.amount_high == round(464 * 0.15, 2)
    assert repo.ceiling_calls == [(2004, "3", 20.5)]


def test_lookup_else_not_estimated() -> None:
    used = used_path(unit(year=2004))
    assert used.lines[1].source_type == "not_estimated"
    assert INCOMPLETE in used.flags


@pytest.mark.parametrize("label", ["about 700", 0.0, -5.0, "nan", "inf"])
def test_a_label_kwh_that_is_not_a_positive_number_is_skipped(label: str | float) -> None:
    line = used_path(unit(year=2004, label_kwh_per_year=label, **CLASS_3)).lines[1]
    assert line.source_id == "doe_standards"


def test_a_new_unit_uses_its_label_kwh_too() -> None:
    leased = LEASED.model_copy(update={"model": "UNRATED", "attributes": {"label_kwh_per_year": "500"}})
    full = pick(quote(full_request(items=[USED, REFURB, leased]), FakeRepo()), "rent_to_own", "rto_full")
    [line] = [line for line in full.lines if line.label == "Electricity"]
    assert (line.source_type, line.source_id, line.amount_high) == ("user_entered", "user", 75.0)


def test_a_missing_year_comes_from_the_rating_data() -> None:
    repo = FakeRepo(years={"OLD123": THIS_YEAR - 9})
    used = used_path(unit("OLD123", year=None), repo)
    assert (used.expected_life_low, used.expected_life_high) == (1, 6)
    assert [line.source_type for line in replacement_lines(used)] == ["published"]  # priced, not "year unknown"
    repair = pick(quote(QuoteRequest(current=unit("OLD123", year=None)), repo), "repair", None)
    assert (repair.expected_life_low, repair.expected_life_high) == (1, 6)


def test_an_entered_year_is_kept() -> None:
    used = used_path(unit("OLD123", year=THIS_YEAR - 8), FakeRepo(years={"OLD123": THIS_YEAR - 20}))
    assert (used.expected_life_low, used.expected_life_high) == (2, 7)


def test_the_ceiling_uses_the_year_from_the_rating_data() -> None:
    repo = FakeRepo(years={"UNRATED": 2004})
    used = used_path(unit(year=None, **CLASS_3), repo)
    assert repo.ceiling_calls == [(2004, "3", 20.5)]
    assert used.lines[1].source_id == "doe_standards"


def test_a_new_unit_is_not_dated_from_the_rating_data() -> None:
    # A new unit was made recently, not when its model was rated, so no 2004 ceiling for it.
    repo = FakeRepo(years={"UNRATED": 2004})
    leased = LEASED.model_copy(update={"model": "UNRATED", "attributes": CLASS_3})
    # No current unit: the request's 2004 repair unit would ask for its own ceiling.
    full = pick(quote(full_request(current=None, items=[USED, REFURB, leased]), repo), "rent_to_own", "rto_full")
    assert [line.source_type for line in full.lines if line.label.startswith("Electricity")] == ["not_estimated"]
    assert repo.ceiling_calls == []


def test_quote_and_rank_price_the_new_offer_the_same() -> None:
    repo = FakeRepo()
    quoted = pick(quote(QuoteRequest(), repo), "new", "cash")
    [ranked] = rank(ShopFilters(), [NEW_OFFERS[1]], [NEW], repo)
    assert quoted == ranked.path
    assert not any(line.label == "Extra use from age" for line in ranked.path.lines)
