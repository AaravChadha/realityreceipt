"""Every way to get the item, as receipt paths (PLAN.md task 2.6, row A2).

Task 2.6 builds the slice: each used listing bought as-is, and the cheapest cached
new offer paid in cash. A path whose inputs are absent is left out, never invented.

`quote` takes any object with the methods of `QuoteRepository`, so this module does
not import `app.repository`; the real `Repository` (task 2.1) satisfies it.
"""

from datetime import date
from typing import Protocol

from app.engine.financing import USER_SOURCE_IDS, cash
from app.engine.lifecycle import combine, cost_per_year, remaining_life, replacement, replacement_month
from app.engine.running import aging_line, carbon_kg, energy, upkeep
from app.models import (
    MONTHS,
    CategoryProfile,
    Contribution,
    CostLine,
    Item,
    ModelEnergy,
    Offer,
    Path,
    PathGroup,
    QuoteRequest,
    RateValue,
    Source,
    UpkeepItem,
)

ELECTRICITY_RATE = "ga_power_marginal_per_kwh"
GRID_EMISSIONS = "egrid_ga_kg_per_kwh"
DEFAULT_CATEGORY = "refrigerator"

# `running.energy` turns this into its blank "not estimated" electricity line.
_NO_KWH = ModelEnergy(kwh_per_year=0.0, source_type="not_estimated", source_id="")


class QuoteRepository(Protocol):
    """The repository methods `quote` calls."""

    def rate(self, key: str) -> RateValue: ...

    def profile(self, category: str) -> CategoryProfile: ...

    def model_energy(self, brand: str, model: str) -> ModelEnergy | None: ...

    def new_offers(self, category: str) -> list[Offer]: ...

    def sources(self) -> list[Source]: ...


def quote(req: QuoteRequest, repo: QuoteRepository) -> list[Path]:
    """Paths sorted by total over 3 years (high end), ties by pay today.

    Raises `ValueError` if any line or carbon figure names a source id that is neither
    reserved (`user`, `user_listing`, `user_lease`) nor in `repo.sources()`.
    """
    category = _category(req)
    profile = repo.profile(category)
    items = {item.id: item for item in req.items}
    cheapest_new = min(repo.new_offers(category), key=lambda o: o.price, default=None)

    paths: list[Path] = []
    for offer in req.offers:
        item = items.get(offer.item_id)
        if offer.source == "user_listing" and item is not None and item.condition == "used_as_is":
            paths.append(_cash_path("Used, as-is", "used_as_is", offer, item, _age(item), profile, cheapest_new, repo))
    if cheapest_new is not None:
        # The new offer's brand and model are known only when the request carries its item.
        paths.append(_cash_path("New, pay cash", "new", cheapest_new, items.get(cheapest_new.item_id), 0.0, profile, cheapest_new, repo))

    paths.sort(key=lambda p: (p.total_3yr_high, p.pay_today))
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
    if cheapest_new is not None:
        parts.append(replacement(cheapest_new, life_low, life_high))
    elif life_low is not None and replacement_month(life_low) < MONTHS:
        parts.append(_line_only(_replacement_not_estimated()))
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
        flags=["past_typical_life"] if life_low == 0 else [],
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


def _line_only(line: CostLine) -> Contribution:
    return Contribution(pay_today=0.0, monthly_low=[0.0] * MONTHS, monthly_high=[0.0] * MONTHS, lines=[line])


def _replacement_not_estimated() -> CostLine:
    return CostLine(
        kind="replacement",
        label="Replacement when it wears out",
        amount_low=None,
        amount_high=None,
        period="once",
        source_type="not_estimated",
        source_id=None,
        formula="Typical life may end inside the 36 months, and no cached new offer prices a replacement",
    )


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
