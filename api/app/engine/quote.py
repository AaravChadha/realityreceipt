"""Every way to get the item, as receipt paths (PLAN.md tasks 2.6, 3.3 to 3.3.2, row A2).

Nine kinds of path: repair the one you have; each used listing, as-is or refurbished;
the cheapest cached new offer paid four ways (cash, card, buy now pay later, credit
union PAL); and a lease kept to the end or bought out at its cheapest week. A path
whose inputs are absent is left out, never invented.

Card, PAL, buy now pay later and lease contributions already hold every dollar paid,
the price included, so a price line is added to those paths as a line only.

A path whose electricity, financing or replacement timing is not estimated counts that
cost as $0 in its totals, so it is flagged `costs_not_estimated` and sorted after the
complete paths (task 3.3.1): otherwise a blank cost would make it look cheapest.

Replacement (task 3.3.2): a unit at or past the low end of its typical life, or of
unknown age, gets no replacement purchase, only a `not_estimated` replacement line.
When a replacement falls inside the 36 months, the old unit's electricity and carbon
stop at that month and the replacement unit's run after it.

`quote` takes any object with the methods of `QuoteRepository`, so this module does
not import `app.repository`; the real `Repository` (task 2.1) satisfies it.
`_cash_path` is also used by `rank.py` (task 4.2); since task 3.3.1 it also sets
`costs_not_estimated`, so ranked offers carry the flag.
"""

from datetime import date
from typing import Protocol

from app.engine.financing import USER_SOURCE_IDS, bnpl, card, cash, pal
from app.engine.lease import rto_buyout, rto_full
from app.engine.lifecycle import combine, cost_per_year, remaining_life, replacement, replacement_month
from app.engine.running import aging_line, carbon_kg, energy, upkeep
from app.models import (
    MONTHS,
    BnplTerms,
    CategoryProfile,
    Contribution,
    CostLine,
    Item,
    ModelEnergy,
    Offer,
    Path,
    PathGroup,
    PaymentMethod,
    QuoteRequest,
    RateValue,
    Source,
    UpkeepItem,
)

ELECTRICITY_RATE = "ga_power_marginal_per_kwh"
GRID_EMISSIONS = "egrid_ga_kg_per_kwh"
CARD_RATE = "g19_card_apr_assessed"
PAL_RATE_CAP = "pal_rate_cap"
PAL_FEE_CAP = "pal_fee_cap"
PAL_MAX_AMOUNT = "pal_max_amount"
DEFAULT_CATEGORY = "refrigerator"

# Refrigerator ratings from before the ~2014 test procedure change are not directly
# comparable with later ones (spec §7).
TEST_PROCEDURE_YEAR = 2014

INCOMPLETE = "costs_not_estimated"

# A user listing's item condition -> path name and group.
LISTING_KINDS: dict[str, tuple[str, PathGroup]] = {
    "used_as_is": ("Used, as-is", "used_as_is"),
    "refurbished": ("Used, refurbished", "refurbished"),
}

# `running.energy` turns this into its blank "not estimated" electricity line.
_NO_KWH = ModelEnergy(kwh_per_year=0.0, source_type="not_estimated", source_id="")


class QuoteRepository(Protocol):
    """The repository methods `quote` calls."""

    def rate(self, key: str) -> RateValue: ...

    def profile(self, category: str) -> CategoryProfile: ...

    def model_energy(self, brand: str, model: str) -> ModelEnergy | None: ...

    def new_offers(self, category: str) -> list[Offer]: ...

    def sources(self) -> list[Source]: ...

    def item(self, id: str) -> Item | None: ...

    def bnpl_terms(self) -> BnplTerms | None: ...

    def standard_ceiling(self, mfg_year: int, product_class: str, volume_cuft: float) -> ModelEnergy | None: ...


def quote(req: QuoteRequest, repo: QuoteRepository) -> list[Path]:
    """Complete paths sorted by total over 3 years (high end), ties by pay today; then the
    paths flagged `costs_not_estimated`, in the same order.

    Raises `ValueError` if any line or carbon figure names a source id that is neither
    reserved (`user`, `user_listing`, `user_lease`) nor in `repo.sources()`.
    """
    category = _category(req)
    profile = repo.profile(category)
    items = {item.id: item for item in req.items}
    cheapest_new = min(repo.new_offers(category), key=lambda o: o.price, default=None)
    new_item = (repo.item(cheapest_new.item_id) or items.get(cheapest_new.item_id)) if cheapest_new is not None else None
    # The unit that replaces a worn-out one is the cheapest new offer's.
    replacement_kwh = _kwh(new_item, repo)
    this_year = date.today().year

    built: list[tuple[Path, int | None]] = []  # each path with its unit's manufacture year
    if req.current is not None:
        repair = _repair_cost(req, profile)
        if repair is not None:
            path = _unit_path("Repair the one you have", "repair", None, repair, req.current, _age(req.current), True, profile, cheapest_new, repo, [], replacement_kwh=replacement_kwh)
            built.append((path, req.current.mfg_year))

    for offer in req.offers:
        item = items.get(offer.item_id)
        if offer.source != "user_listing" or offer.seller_type == "rent_to_own" or item is None or item.condition not in LISTING_KINDS:
            continue
        name, group = LISTING_KINDS[item.condition]
        flags = [f"warranty_{item.warranty_months}_months"] if group == "refurbished" and item.warranty_months else []
        path = _unit_path(name, group, "cash", cash(offer.price, offer.source_id), item, _age(item), True, profile, cheapest_new, repo, flags, replacement_kwh=replacement_kwh)
        built.append((path, item.mfg_year))

    if cheapest_new is not None:
        for name, method, acquire, flags in _new_ways(cheapest_new, repo):
            path = _unit_path(name, "new", method, acquire, new_item, 0.0, False, profile, cheapest_new, repo, flags, replacement_kwh=replacement_kwh)
            built.append((path, this_year))

    if req.lease is not None:
        unit = _leased_item(req, items)
        is_new = unit is not None and unit.condition == "new"
        age = 0.0 if is_new else (_age(unit) if unit is not None else None)
        year = this_year if is_new else (unit.mfg_year if unit is not None else None)
        aged = unit is not None and not is_new
        for name, method, acquire in (
            ("Rent-to-own, keep paying", "rto_full", rto_full(req.lease)),
            ("Rent-to-own, early buyout", "rto_buyout", rto_buyout(req.lease)),
        ):
            built.append((_unit_path(name, "rent_to_own", method, acquire, unit, age, aged, profile, cheapest_new, repo, [], replacement_kwh=replacement_kwh), year))

    paths = _flag_test_procedure(built)
    paths.sort(key=lambda p: (INCOMPLETE in p.flags, p.total_3yr_high, p.pay_today))
    _check_sources(paths, repo)
    return paths


def _cash_path(
    name: str,
    group: PathGroup,
    offer: Offer,
    item: Item | None,
    age_years: float | None,
    profile: CategoryProfile,
    cheapest_new: Offer | None,
    repo: QuoteRepository,
) -> Path:
    kwh = repo.model_energy(item.brand, item.model) if item is not None else None
    electricity = energy(kwh or _NO_KWH, repo.rate(ELECTRICITY_RATE))
    parts = [cash(offer.price, offer.source_id), electricity]
    if group == "used_as_is":
        parts.append(_line_only(aging_line()))
    parts.append(upkeep(profile.upkeep_schedule))

    life_low, life_high = remaining_life(age_years, profile.lifespan_range)
    # The replacement unit's electricity is not switched in here yet (task 3.3.3).
    parts += _replacement_parts(group == "used_as_is", life_low, life_high, profile, cheapest_new)
    total = combine(parts)

    annual_low, annual_high = _annual_cost(electricity, profile.upkeep_schedule)
    cpy_low, cpy_high = cost_per_year(offer.price, offer.price, annual_low, annual_high, life_low, life_high)

    carbon: float | None = None
    carbon_ids: list[str] = []
    if profile.carbon_applicable and kwh is not None:
        grid = repo.rate(GRID_EMISSIONS)
        carbon = carbon_kg(kwh.kwh_per_year, grid)
        carbon_ids = [kwh.source_id, grid.source_id]

    return Path(
        name=name,
        group=group,
        payment_method="cash",
        pay_today=total.pay_today,
        total_3yr_low=round(sum(total.monthly_low), 2),
        total_3yr_high=round(sum(total.monthly_high), 2),
        cost_per_year_low=cpy_low,
        cost_per_year_high=cpy_high,
        expected_life_low=life_low,
        expected_life_high=life_high,
        monthly_low=total.monthly_low,
        monthly_high=total.monthly_high,
        carbon_kg=carbon,
        carbon_source_ids=carbon_ids,
        lines=total.lines,
        flags=(["past_typical_life"] if life_low == 0 else []) + ([INCOMPLETE] if _costs_not_estimated(total.lines, profile) else []),
    )


def _category(req: QuoteRequest) -> str:
    if req.current is not None:
        return req.current.category
    return req.items[0].category if req.items else DEFAULT_CATEGORY


def _age(item: Item) -> float | None:
    """Whole years since the manufacture year; `None` when the year is unknown."""
    if item.mfg_year is None:
        return None
    return float(max(0, date.today().year - item.mfg_year))


def _annual_cost(electricity: Contribution, schedule: list[UpkeepItem]) -> tuple[float, float]:
    """Running plus upkeep per year. A not-estimated electricity line adds nothing."""
    energy_low = sum(line.amount_low or 0.0 for line in electricity.lines)
    energy_high = sum(line.amount_high or 0.0 for line in electricity.lines)
    upkeep_low = sum(item.cost_low * 12 / item.every_months for item in schedule)
    upkeep_high = sum(item.cost_high * 12 / item.every_months for item in schedule)
    return energy_low + upkeep_low, energy_high + upkeep_high


def _costs_not_estimated(lines: list[CostLine], profile: CategoryProfile) -> bool:
    """True when the electricity (for a category with energy data), financing or replacement
    line is blank. The "Extra use from age" line is blank on every used unit and is shown on
    its own, so it does not count."""
    aging = aging_line().label
    for line in lines:
        if line.source_type != "not_estimated":
            continue
        if line.kind in ("financing", "replacement"):
            return True
        if line.kind == "running" and line.label != aging and profile.energy_dataset_refs:
            return True
    return False


def _line_only(line: CostLine) -> Contribution:
    return Contribution(pay_today=0.0, monthly_low=[0.0] * MONTHS, monthly_high=[0.0] * MONTHS, lines=[line])


def _replacement_not_estimated(formula: str) -> CostLine:
    return CostLine(
        kind="replacement",
        label="Replacement when it wears out",
        amount_low=None,
        amount_high=None,
        period="once",
        source_type="not_estimated",
        source_id=None,
        formula=formula,
    )


def _replacement_parts(
    aged: bool, life_low: float | None, life_high: float | None, profile: CategoryProfile, cheapest_new: Offer | None
) -> list[Contribution]:
    """The replacement purchase, or a blank line saying why its timing or price is not estimated.

    At or past the low end of typical life, or for an aged unit of unknown age, no replacement
    is bought in the arrays: when it will need replacing is not estimated.
    """
    lifespan = profile.lifespan_range
    if life_low == 0 and lifespan is not None:
        years = f"{lifespan.low_years:g}" if lifespan.low_years == lifespan.high_years else f"{lifespan.low_years:g} to {lifespan.high_years:g}"
        return [_line_only(_replacement_not_estimated(
            "When it will need replacing is not estimated: it is at or past the low end of the typical"
            f" {years} year life, so no replacement is priced"
        ))]
    if life_low is None:
        if aged and lifespan is not None:
            return [_line_only(_replacement_not_estimated(
                "When it will need replacing is not estimated: the year it was made is unknown, so its remaining life is unknown"
            ))]
        return []
    if cheapest_new is not None:
        return [replacement(cheapest_new, life_low, life_high)]
    if replacement_month(life_low) < MONTHS:
        return [_line_only(_replacement_not_estimated(
            "Typical life may end inside the 36 months, and no cached new offer prices a replacement"
        ))]
    return []


def _switch_months(life_low: float | None, life_high: float | None, cheapest_new: Offer | None) -> tuple[int, int]:
    """(low array, high array) month in which the unit is replaced by the cheapest new offer;
    `MONTHS` when it is not replaced inside the window. Same months as `lifecycle.replacement`."""
    if cheapest_new is None or life_low is None or life_high is None or life_low == 0:
        return MONTHS, MONTHS
    return min(MONTHS, replacement_month(life_high)), min(MONTHS, replacement_month(life_low))


def _switch_electricity(old: Contribution, new: Contribution, month_low: int, month_high: int) -> Contribution:
    """The old unit's electricity up to each array's replacement month, the replacement unit's from it."""
    if month_low == month_high:
        when = f"month {month_high}"
    elif month_low < MONTHS:
        when = f"month {month_high} at the soonest, month {month_low} at the latest"
    else:
        when = f"month {month_high} at the soonest, or not inside the 36 months"
    [old_line] = old.lines
    [new_line] = new.lines
    return Contribution(
        pay_today=0.0,
        monthly_low=[old.monthly_low[m] if m < month_low else new.monthly_low[m] for m in range(MONTHS)],
        monthly_high=[old.monthly_high[m] if m < month_high else new.monthly_high[m] for m in range(MONTHS)],
        lines=[
            old_line.model_copy(update={"formula": f"{old_line.formula}. Runs until it is replaced: {when}"}),
            new_line.model_copy(update={
                "label": "Electricity, replacement unit",
                "formula": f"Runs after the replacement: {when}. {new_line.formula}",
            }),
        ],
    )


def _carbon(
    kwh: ModelEnergy | None,
    replacement_kwh: ModelEnergy | None,
    month_low: int,
    month_high: int,
    profile: CategoryProfile,
    repo: QuoteRepository,
) -> tuple[float | None, list[str]]:
    """Carbon over the 36 months and the sources of the figures it uses. With a replacement inside
    the window, the old unit's until then and the replacement's after, taking the higher of the two
    timelines (low and high array) so it is never understated; `None` when a kWh it needs is missing."""
    if not profile.carbon_applicable or kwh is None:
        return None, []
    grid = repo.rate(GRID_EMISSIONS)
    if month_high >= MONTHS:
        return carbon_kg(kwh.kwh_per_year, grid), [kwh.source_id, grid.source_id]
    if replacement_kwh is None:
        return None, []
    timelines = [
        (carbon_kg(kwh.kwh_per_year, grid), [kwh.source_id, grid.source_id])
        if m >= MONTHS
        else (
            round(carbon_kg(kwh.kwh_per_year, grid, m) + carbon_kg(replacement_kwh.kwh_per_year, grid, MONTHS - m), 2),
            list(dict.fromkeys([kwh.source_id, replacement_kwh.source_id, grid.source_id])),
        )
        for m in (month_low, month_high)
    ]
    return max(timelines, key=lambda t: t[0])


def _check_sources(paths: list[Path], repo: QuoteRepository) -> None:
    known = {s.id for s in repo.sources()} | USER_SOURCE_IDS
    named = {
        source_id
        for path in paths
        for source_id in [
            *path.carbon_source_ids,
            *(line.source_id for line in path.lines if line.source_id is not None),
            *(other for line in path.lines for other in line.other_source_ids),
        ]
    }
    missing = sorted(named - known)
    if missing:
        raise ValueError(f"no source recorded for {missing}")


def _unit_path(
    name: str,
    group: PathGroup,
    method: PaymentMethod | None,
    acquire: Contribution,
    item: Item | None,
    age_years: float | None,
    aged: bool,
    profile: CategoryProfile,
    cheapest_new: Offer | None,
    repo: QuoteRepository,
    flags: list[str],
    *,
    replacement_kwh: ModelEnergy | None,
) -> Path:
    """One path: `acquire` (every dollar paid to get the unit), then electricity, the aging
    line when `aged`, upkeep and the replacement for `item`, with cost per year and carbon.
    `replacement_kwh` is the replacement unit's figure, used from the month it is bought."""
    kwh = _kwh(item, repo)
    rate = repo.rate(ELECTRICITY_RATE)
    electricity = energy(kwh or _NO_KWH, rate)
    life_low, life_high = remaining_life(age_years, profile.lifespan_range)
    month_low, month_high = _switch_months(life_low, life_high, cheapest_new)
    running = electricity
    if month_high < MONTHS:
        running = _switch_electricity(electricity, energy(replacement_kwh or _NO_KWH, rate), month_low, month_high)

    parts = [acquire, running]
    if aged:
        parts.append(_line_only(aging_line()))
    parts.append(upkeep(profile.upkeep_schedule))
    parts += _replacement_parts(aged, life_low, life_high, profile, cheapest_new)
    total = combine(parts)

    # Cost per year of use is this unit's: its own electricity, not the replacement's.
    annual_low, annual_high = _annual_cost(electricity, profile.upkeep_schedule)
    # "Purchase total" includes financing: everything `acquire` pays, not just the price.
    cpy_low, cpy_high = cost_per_year(
        sum(acquire.monthly_low), sum(acquire.monthly_high), annual_low, annual_high, life_low, life_high
    )
    carbon, carbon_ids = _carbon(kwh, replacement_kwh, month_low, month_high, profile, repo)

    flags = [*flags]
    if life_low == 0:
        flags.append("past_typical_life")
    if item is not None and item.year_confidence == "low":
        flags.append("year_from_serial_low_confidence")
    if _costs_not_estimated(total.lines, profile):
        flags.append(INCOMPLETE)

    return Path(
        name=name,
        group=group,
        payment_method=method,
        pay_today=total.pay_today,
        total_3yr_low=round(sum(total.monthly_low), 2),
        total_3yr_high=round(sum(total.monthly_high), 2),
        cost_per_year_low=cpy_low,
        cost_per_year_high=cpy_high,
        expected_life_low=life_low,
        expected_life_high=life_high,
        monthly_low=total.monthly_low,
        monthly_high=total.monthly_high,
        carbon_kg=carbon,
        carbon_source_ids=carbon_ids,
        lines=total.lines,
        flags=flags,
    )


def _kwh(item: Item | None, repo: QuoteRepository) -> ModelEnergy | None:
    """The rated figure for the model. For a unit that is not new and has no rating, the DOE
    standard ceiling for its year, class and adjusted volume; total volume alone gives nothing,
    because the standard is written in adjusted volume."""
    if item is None:
        return None
    rated = repo.model_energy(item.brand, item.model)
    if rated is not None or item.condition == "new" or item.mfg_year is None:
        return rated
    product_class = item.attributes.get("product_class")
    try:
        adjusted = float(item.attributes["adjusted_volume_cuft"])
    except (KeyError, ValueError):
        return None
    if product_class is None or not adjusted > 0:
        return None
    if isinstance(product_class, float):  # a class sent as a number: 3.0 is CFR class "3"
        product_class = f"{product_class:g}"
    return repo.standard_ceiling(item.mfg_year, product_class, adjusted)


def _repair_cost(req: QuoteRequest, profile: CategoryProfile) -> Contribution | None:
    """The repair, paid today: the user's quote, else the profile's published ranges from the
    lowest to the highest. `None` when there is neither. Pay today is the high end."""
    if req.repair_quote_low is not None or req.repair_quote_high is not None:
        given = [x for x in (req.repair_quote_low, req.repair_quote_high) if x is not None]
        low, high = round(min(given), 2), round(max(given), 2)
        amount = f"${low:,.2f}" if low == high else f"${low:,.2f} to ${high:,.2f}"
        line = CostLine(
            kind="repair", label="Repair quote", amount_low=low, amount_high=high, period="once",
            source_type="user_entered", source_id="user", formula=f"Quote you entered: {amount}, paid today",
        )
    elif profile.repair_ranges:
        ranges = profile.repair_ranges
        low = round(min(r.cost_low for r in ranges), 2)
        high = round(max(r.cost_high for r in ranges), 2)
        source_ids = list(dict.fromkeys(r.source_id for r in ranges))
        listed = "; ".join(f"{r.label} ${r.cost_low:,.2f} to ${r.cost_high:,.2f}" for r in ranges)
        line = CostLine(
            kind="repair", label="Repair, published ranges", amount_low=low, amount_high=high, period="once",
            source_type="published", source_id=source_ids[0], other_source_ids=source_ids[1:],
            formula=f"No quote entered. Published ranges: {listed}. Shown from the lowest to the highest, paid today",
        )
    else:
        return None
    monthly_low = [0.0] * MONTHS
    monthly_high = [0.0] * MONTHS
    monthly_low[0], monthly_high[0] = low, high
    return Contribution(pay_today=high, monthly_low=monthly_low, monthly_high=monthly_high, lines=[line])


def _new_ways(offer: Offer, repo: QuoteRepository) -> list[tuple[str, PaymentMethod, Contribution, list[str]]]:
    """The new offer paid in cash, by card, by buy now pay later, and by a PAL when its price is
    under the loan cap. Each contribution holds the price once."""
    price_line = _line_only(_price_line(offer))
    terms = repo.bnpl_terms()
    ways: list[tuple[str, PaymentMethod, Contribution, list[str]]] = [
        ("New, pay cash", "cash", cash(offer.price, offer.source_id), []),
        ("New, credit card", "card", combine([price_line, card(offer.price, repo.rate(CARD_RATE))]), []),
        (
            "New, buy now pay later", "bnpl", combine([price_line, bnpl(offer.price, terms)]),
            ["bnpl_terms_not_an_offer"] if terms is not None else [],
        ),
    ]
    loan = pal(offer.price, repo.rate(PAL_RATE_CAP), repo.rate(PAL_FEE_CAP), repo.rate(PAL_MAX_AMOUNT))
    if loan is not None:
        ways.append(("New, credit union PAL", "pal", combine([price_line, loan]), ["pal_caps_not_an_offer"]))
    return ways


def _price_line(offer: Offer) -> CostLine:
    """The price as a line only, for a method whose payments already include it."""
    price = round(offer.price, 2)
    user = offer.source_id in USER_SOURCE_IDS
    where = "the price on your listing" if user else "the cached retailer price"
    return CostLine(
        kind="purchase", label="Price", amount_low=price, amount_high=price, period="once",
        source_type="user_entered" if user else "published", source_id=offer.source_id,
        formula=f"${price:,.2f}, {where}, counted once inside the payments",
    )


def _leased_item(req: QuoteRequest, items: dict[str, Item]) -> Item | None:
    """The item of the request's rent-to-own offer, when it has one."""
    for offer in req.offers:
        if offer.seller_type == "rent_to_own" and offer.item_id in items:
            return items[offer.item_id]
    return None


def _flag_test_procedure(built: list[tuple[Path, int | None]]) -> list[Path]:
    """Flag each pre-2014 unit's paths when the quote also holds a newer unit."""
    years = [year for _, year in built if year is not None]
    if not any(y < TEST_PROCEDURE_YEAR for y in years) or not any(y >= TEST_PROCEDURE_YEAR for y in years):
        return [path for path, _ in built]
    return [
        path.model_copy(update={"flags": [*path.flags, "test_procedure_changed"]})
        if year is not None and year < TEST_PROCEDURE_YEAR
        else path
        for path, year in built
    ]
