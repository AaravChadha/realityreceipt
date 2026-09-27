"""Committed data in `api/app/data/`, loaded into memory (PLAN.md task 2.1).

`sources.json` and `rates.json` are required. Every other file is optional
until the task that adds it lands (2.2 profile and ENERGY STAR CSV, 2.2.2 DOE
historical ratings, 2.3 retailer cache, 3.5 DOE standards, 3.6 BNPL terms); a missing file gives an
empty answer (`None`, `[]`, or `KeyError` for `profile`), never a guess.
"""

import csv
import datetime
import functools
import gzip
import json
import math
import pathlib
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from typing import IO

from pydantic import TypeAdapter

from app.models import BnplTerms, CategoryProfile, Item, ModelEnergy, Offer, RateValue, Source

DATA_DIR = pathlib.Path(__file__).resolve().parent / "data"

RATE_KEYS = (
    "ga_power_marginal_per_kwh",
    "egrid_ga_kg_per_kwh",
    "g19_card_apr_assessed",
    "pal_rate_cap",
    "pal_fee_cap",
    "pal_max_amount",
)

MAX_CANDIDATES = 5
MIN_PREFIX = 3
WILDCARDS = "*#"

# Brand names that mean the same maker, after `_brand_key`. Kept small on purpose:
# a sub-brand is not an alias, because a rated figure must come from the same brand.
# An EnergyGuide can print the maker instead of the brand ("Electrolux Home Products Inc."
# on a Frigidaire label).
_BRAND_ALIASES = {"geappliances": "ge", "electroluxhomeproductsinc": "electrolux"}

# Two brands of one maker, asked only when the brand as given has no matching row: the
# datasets list some Electrolux-made models under both names at different kWh, so they are
# never merged. A retailer's house brand (Kenmore) is not a maker and is never here.
_SAME_MAKER = {"electrolux": "frigidaire", "frigidaire": "electrolux"}


def normalize_model(s: str) -> str:
    """Uppercase; drop spaces, `-`, `/` and `.`."""
    return re.sub(r"[\s\-/.]", "", s).upper()


@functools.lru_cache(maxsize=None)
def _brand_key(s: str) -> str:
    """Casefold, fold accents, drop everything but letters and digits, then apply the alias list."""
    folded = "".join(c for c in unicodedata.normalize("NFKD", s.casefold()) if not unicodedata.combining(c))
    key = re.sub(r"[^0-9a-z]", "", folded)
    return _BRAND_ALIASES.get(key, key)


def _wildcard_count(normalized: str) -> int:
    return sum(normalized.count(c) for c in WILDCARDS)


@functools.lru_cache(maxsize=None)
def _model_pattern(normalized: str) -> re.Pattern[str]:
    """Each `*` or `#` in a dataset model number stands for one optional letter or digit."""
    return re.compile("".join("[A-Z0-9]?" if c in WILDCARDS else re.escape(c) for c in normalized))


@dataclass(frozen=True)
class _EnergyRow:
    brand: str
    model_number: str
    model_normalized: str
    annual_kwh: float
    year: int | None = None
    brand_key: str = field(init=False, compare=False)
    wildcards: int = field(init=False, compare=False)
    prefix: str = field(init=False, compare=False)  # the fixed characters before the first wildcard

    def __post_init__(self) -> None:
        object.__setattr__(self, "brand_key", _brand_key(self.brand))
        object.__setattr__(self, "wildcards", _wildcard_count(self.model_normalized))
        object.__setattr__(self, "prefix", re.split(r"[*#]", self.model_normalized, maxsplit=1)[0])


def _select(rows: list[_EnergyRow], key: str) -> list[_EnergyRow]:
    """The rows whose model number stands for the normalized query `key`.

    A query without wildcards matches a row whose pattern can produce it. A query with wildcards
    (a label family such as `MB*2562***`) matches a row with the identical pattern; if there is
    none, it matches rows that start with the family's fixed core (`MB*2562`) and add no more
    characters than the family has trailing wildcards (`MB*2562HE*` adds three).
    """
    if _wildcard_count(key):
        same = [r for r in rows if r.model_normalized == key]
        if same:
            return same
        core = key.rstrip(WILDCARDS)
        room = len(key) - len(core)
        return [r for r in rows if r.model_normalized.startswith(core) and len(r.model_normalized) - len(core) <= room]
    return [
        r
        for r in rows
        if key.startswith(r.prefix)
        and (r.model_normalized == key if not r.wildcards else _model_pattern(r.model_normalized).fullmatch(key))
    ]


def _read_energy_rows(f: IO[str]) -> list[_EnergyRow]:
    """Rows of `brand,model_number,model_normalized,annual_kwh` and, for DOE, `year`."""
    return [
        _EnergyRow(
            brand=row["brand"],
            model_number=row["model_number"],
            model_normalized=row["model_normalized"] or normalize_model(row["model_number"]),
            annual_kwh=float(row["annual_kwh"]),
            year=int(row["year"]) if row.get("year") else None,
        )
        for row in csv.DictReader(f)
    ]


def _matching_rows(rows: list[_EnergyRow], brand: str, model: str) -> list[_EnergyRow]:
    """Rows of the same brand that stand for `model`, fewest wildcards only; when the brand has
    none, the rows of the other brand of the same maker (`_SAME_MAKER`)."""
    brand_key = _brand_key(brand)
    key = normalize_model(model)
    for candidate in (brand_key, _SAME_MAKER.get(brand_key)):
        hits = _select([r for r in rows if r.brand_key == candidate], key) if candidate else []
        if hits:
            fewest = min(r.wildcards for r in hits)
            return [r for r in hits if r.wildcards == fewest]
    return []


@dataclass(frozen=True)
class _Standard:
    """One DOE standard period: max kWh/yr = kwh_per_cuft * volume + kwh_base.

    `to_date` is the last day the period applies to units made then, or None
    while it is still in force.
    """

    product_class: str
    from_date: datetime.date
    to_date: datetime.date | None
    kwh_per_cuft: float
    kwh_base: float
    source_id: str


@dataclass
class Repository:
    _sources: dict[str, Source]
    _rates: dict[str, RateValue]
    _profiles: dict[str, CategoryProfile] = field(default_factory=dict)
    _energy: list[_EnergyRow] = field(default_factory=list)  # ENERGY STAR
    _doe: list[_EnergyRow] = field(default_factory=list)  # DOE historical ratings
    _standards: list[_Standard] = field(default_factory=list)
    _items: dict[str, Item] = field(default_factory=dict)
    _offers: list[Offer] = field(default_factory=list)
    _bnpl: BnplTerms | None = None

    @classmethod
    def load(cls, data_dir: pathlib.Path = DATA_DIR) -> "Repository":
        sources = TypeAdapter(list[Source]).validate_json((data_dir / "sources.json").read_text(encoding="utf-8"))
        raw_rates = json.loads((data_dir / "rates.json").read_text(encoding="utf-8"))
        repo = cls(
            _sources={s.id: s for s in sources},
            _rates={k: RateValue(value=v["value"], source_id=v["source_id"]) for k, v in raw_rates.items()},
        )

        profile_file = data_dir / "refrigerator.json"
        if profile_file.exists():
            profile = CategoryProfile.model_validate_json(profile_file.read_text(encoding="utf-8"))
            repo._profiles[profile.category] = profile

        energy_file = data_dir / "energystar_refrigerators.csv"
        if energy_file.exists():
            with energy_file.open(newline="", encoding="utf-8") as f:
                repo._energy = _read_energy_rows(f)

        doe_file = data_dir / "doe_wap_refrigerators.csv.gz"
        if doe_file.exists():
            with gzip.open(doe_file, "rt", newline="", encoding="utf-8") as f:
                repo._doe = _read_energy_rows(f)

        standards_file = data_dir / "doe_standards_refrigerators.json"
        if standards_file.exists():
            raw = json.loads(standards_file.read_text(encoding="utf-8"))
            repo._standards = [
                _Standard(
                    product_class=product_class,
                    from_date=datetime.date.fromisoformat(p["manufactured_from"]),
                    to_date=datetime.date.fromisoformat(p["manufactured_to"]) if p["manufactured_to"] else None,
                    kwh_per_cuft=p["slope"],
                    kwh_base=p["intercept"],
                    source_id=raw["source_id"],
                )
                for product_class, entry in raw["classes"].items()
                for p in entry["periods"]
            ]

        cache_file = data_dir / "retailer_cache.json"
        if cache_file.exists():
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
            repo._items = {i.id: i for i in TypeAdapter(list[Item]).validate_python(cache["items"])}
            repo._offers = TypeAdapter(list[Offer]).validate_python(cache["offers"])

        bnpl_file = data_dir / "bnpl.json"
        if bnpl_file.exists():
            repo._bnpl = BnplTerms.model_validate(json.loads(bnpl_file.read_text(encoding="utf-8"))["terms"])

        return repo

    def sources(self) -> list[Source]:
        return list(self._sources.values())

    def source(self, id: str) -> Source:
        return self._sources[id]

    def rate(self, key: str) -> RateValue:
        return self._rates[key]

    def profile(self, category: str) -> CategoryProfile:
        return self._profiles[category]

    def model_energy(self, brand: str, model: str) -> ModelEnergy | None:
        """The rated kWh for `brand` and `model`, or None.

        `*` and `#` in a dataset model number each match one optional letter or digit. The brand
        must match (`GE Appliances` counts as `GE`); another brand's row is never returned. The
        row with the fewest wildcards wins; if the rows left disagree on kWh the answer is None,
        and `model_candidates` lists them. ENERGY STAR is asked first; DOE's historical ratings
        are used only when ENERGY STAR has no matching row, so an ambiguous ENERGY STAR model
        stays `None` rather than falling back to an older figure.
        """
        for rows, source_id in (
            (self._energy, "energystar_refrigerators"),
            (self._doe, "doe_wap_refrigerators"),
        ):
            hits = _matching_rows(rows, brand, model)
            if hits:
                if len({r.annual_kwh for r in hits}) > 1:
                    return None
                return ModelEnergy(kwh_per_year=hits[0].annual_kwh, source_type="rated", source_id=source_id)
        return None

    def model_year(self, brand: str, model: str) -> int | None:
        """The latest year DOE's historical database lists `brand` and `model`, or None.

        A model is often listed for several years (the Maytag family on the demo card:
        2005 to 2009), so this is the last year it was listed: the unit was made no later than
        that, which never overstates its age. It uses the same brand and wildcard matching as
        `model_energy` and does not depend on the kWh agreeing across years.
        """
        years = [r.year for r in _matching_rows(self._doe, brand, model) if r.year is not None]
        return max(years) if years else None

    def model_candidates(self, model: str) -> list[str]:
        """Up to 5 model numbers for `model`: pattern matches first, then the longest shared prefix (3+ characters)."""
        key = normalize_model(model)
        rows = self._energy + self._doe
        found = sorted(_select(rows, key), key=lambda r: (r.wildcards, r.model_number))
        out = list(dict.fromkeys(r.model_number for r in found))
        for n in range(len(key), MIN_PREFIX - 1, -1):
            if len(out) >= MAX_CANDIDATES:
                break
            hits = sorted({r.model_number for r in rows if r.model_normalized.startswith(key[:n])})
            if hits:
                out += [h for h in hits if h not in out]
                break
        return out[:MAX_CANDIDATES]

    def standard_ceiling(self, mfg_year: int, product_class: str, volume_cuft: float) -> ModelEnergy | None:
        """The DOE maximum kWh/yr for a unit made in `mfg_year`: an upper bound when new, not a measurement.

        `volume_cuft` must be the DOE adjusted volume, which for a refrigerator-freezer is
        larger than the label's total volume; a label volume understates the ceiling.
        Standards change on 2001-07-01 and 2014-09-15, and only the year is known, so in
        those years the higher of the two applicable ceilings is returned. Each standard is
        rounded to the nearest kWh, halves up, as 10 CFR 430.32(a) directs. A year before
        the first standard, an unknown class, or a volume that is not positive gives None.
        """
        if volume_cuft <= 0:
            return None
        first, last = datetime.date(mfg_year, 1, 1), datetime.date(mfg_year, 12, 31)
        klass = product_class.strip().upper()
        hits = [
            s
            for s in self._standards
            if s.product_class == klass and s.from_date <= last and (s.to_date is None or first <= s.to_date)
        ]
        if not hits:
            return None
        top = max(hits, key=lambda s: s.kwh_per_cuft * volume_cuft + s.kwh_base)
        return ModelEnergy(
            kwh_per_year=float(math.floor(top.kwh_per_cuft * volume_cuft + top.kwh_base + 0.5)),
            source_type="published",
            source_id=top.source_id,
        )

    def new_offers(self, category: str) -> list[Offer]:
        return [
            o
            for o in self._offers
            if o.item_id in self._items
            and self._items[o.item_id].category == category
            and self._items[o.item_id].condition == "new"
        ]

    def item(self, id: str) -> Item | None:
        """The `Item` stored beside the retailer cache's offers; `None` if `id` is absent."""
        return self._items.get(id)

    def bnpl_terms(self) -> BnplTerms | None:
        return self._bnpl
