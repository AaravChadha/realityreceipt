"""Shop offers ranked by cost per year of use (PLAN.md task 4.2, row A2).

Each offer is priced with its own `Item` as one cash path: a retailer-cache offer for a
new item as `new`, a user listing for a used item as `used_as_is`. Any other offer, or
one whose item was not passed in, is left out, never invented.

`ShopFilters` narrow the offers, except the budget: an offer that costs more today than
`budget_today` stays in the ranking with the `over_budget_today` flag, so the UI can dim
it the way the receipt does (task 3.11) and a cheap used unit can still be compared with
the new ones. A filter the offer has no value for (no delivery days, no width) excludes
it, because the ranking cannot claim it fits.
"""

from datetime import date

from app.engine.financing import USER_SOURCE_IDS
from app.engine.quote import QuoteRepository, _cash_path
from app.models import CategoryProfile, Item, Offer, Path, PathGroup, RankedOffer, ShopFilters

OVER_BUDGET = "over_budget_today"

# (offer source, item condition) -> path group and name, matching `quote`'s path names.
KINDS: dict[tuple[str, str], tuple[PathGroup, str]] = {
    ("retailer_cache", "new"): ("new", "New, pay cash"),
    ("user_listing", "used_as_is"): ("used_as_is", "Used, as-is"),
}


def rank(filters: ShopFilters, offers: list[Offer], items: list[Item], repo: QuoteRepository) -> list[RankedOffer]:
    """Offers that pass the filters, sorted by `cost_per_year_high`, `None` last.

    Ties keep the order the offers came in. Raises `ValueError` if a path names a source
    id that is neither reserved nor in `repo.sources()`.
    """
    by_id = {item.id: item for item in items}
    categories: dict[str, tuple[CategoryProfile, Offer | None]] = {}
    ranked: list[RankedOffer] = []
    for offer in offers:
        item = by_id.get(offer.item_id)
        if item is None or (offer.source, item.condition) not in KINDS or not _passes(filters, offer, item):
            continue
        group, name = KINDS[(offer.source, item.condition)]
        if item.category not in categories:
            cheapest_new = min(repo.new_offers(item.category), key=lambda o: o.price, default=None)
            categories[item.category] = (repo.profile(item.category), cheapest_new)
        profile, cheapest_new = categories[item.category]

        age = 0.0 if group == "new" else _age(item)
        path = _cash_path(name, group, offer, item, age, profile, cheapest_new, repo)
        if filters.budget_today is not None and path.pay_today > filters.budget_today:
            path = path.model_copy(update={"flags": [*path.flags, OVER_BUDGET]})
        ranked.append(RankedOffer(offer=offer, path=path))

    ranked.sort(key=lambda r: (r.path.cost_per_year_high is None, r.path.cost_per_year_high or 0.0))
    _check_sources([r.path for r in ranked], repo)
    return ranked


def _passes(filters: ShopFilters, offer: Offer, item: Item) -> bool:
    if filters.category is not None and item.category != filters.category:
        return False
    if filters.conditions and item.condition not in filters.conditions:
        return False
    if filters.need_within_days is not None:
        days = offer.available_within_days
        if days is None or days > filters.need_within_days:
            return False
    if filters.max_width_in is not None:
        width = _width(item)
        if width is None or width > filters.max_width_in:
            return False
    return True


def _width(item: Item) -> float | None:
    """The item's `width_in` attribute in inches; `None` when absent or not a number."""
    try:
        return float(item.attributes["width_in"])
    except (KeyError, ValueError):
        return None


def _age(item: Item) -> float | None:
    """Whole years since the manufacture year; `None` when the year is unknown (as in `quote`)."""
    if item.mfg_year is None:
        return None
    return float(max(0, date.today().year - item.mfg_year))


def _check_sources(paths: list[Path], repo: QuoteRepository) -> None:
    """The same refusal as `quote`: every named source id must be reserved or recorded."""
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
