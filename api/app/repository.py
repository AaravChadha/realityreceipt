"""Committed data in `api/app/data/`, loaded into memory (PLAN.md task 2.1).

`sources.json` and `rates.json` are required. Every other file is optional
until the task that adds it lands (2.2 profile and ENERGY STAR CSV, 2.3
retailer cache, 3.5 DOE standards, 3.6 BNPL terms); a missing file gives an
empty answer (`None`, `[]`, or `KeyError` for `profile`), never a guess.
"""

import csv
import datetime
import json
import math
import pathlib
import re
from dataclasses import dataclass, field

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


def normalize_model(s: str) -> str:
    """Uppercase; drop spaces, `-`, `/` and `.`."""
    return re.sub(r"[\s\-/.]", "", s).upper()


@dataclass(frozen=True)
class _EnergyRow:
    brand: str
    model_number: str
    model_normalized: str
    annual_kwh: float


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
    _energy: list[_EnergyRow] = field(default_factory=list)
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
                repo._energy = [
                    _EnergyRow(
                        brand=row["brand"],
                        model_number=row["model_number"],
                        model_normalized=row["model_normalized"] or normalize_model(row["model_number"]),
                        annual_kwh=float(row["annual_kwh"]),
                    )
                    for row in csv.DictReader(f)
                ]

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
        """Exact normalized model match only; a row with the same brand wins a tie."""
        key = normalize_model(model)
        matches = [r for r in self._energy if r.model_normalized == key]
        if not matches:
            return None
        same_brand = [r for r in matches if r.brand.casefold() == brand.strip().casefold()]
        row = (same_brand or matches)[0]
        return ModelEnergy(kwh_per_year=row.annual_kwh, source_type="rated", source_id="energystar_refrigerators")

    def model_candidates(self, model: str) -> list[str]:
        """Up to 5 model numbers sharing the longest prefix (at least 3 characters) with `model`."""
        key = normalize_model(model)
        for n in range(len(key), MIN_PREFIX - 1, -1):
            hits = sorted({r.model_number for r in self._energy if r.model_normalized.startswith(key[:n])})
            if hits:
                return hits[:MAX_CANDIDATES]
        return []

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

    def bnpl_terms(self) -> BnplTerms | None:
        return self._bnpl
