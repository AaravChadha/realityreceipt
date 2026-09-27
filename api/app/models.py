"""Contracts shared by every track (PLAN.md task 1.1).

Changes go through the A1 owner with a message to the whole team first.
`Path` here is a receipt path, not a filesystem path: import `pathlib` under
another name in any module that needs both.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MONTHS = 36

SourceType = Literal["rated", "published", "user_entered", "not_estimated"]
CostKind = Literal["purchase", "financing", "running", "upkeep", "repair", "replacement", "end_of_life"]
Period = Literal["once", "month", "year", "window"]
Condition = Literal["new", "used_as_is", "refurbished"]
OfferSource = Literal["retailer_cache", "user_listing", "price_tag"]
SellerType = Literal["retailer", "private", "refurbisher", "rent_to_own"]
ScanKind = Literal["label", "price_tag", "lease", "listing"]
PathGroup = Literal["repair", "used_as_is", "refurbished", "new", "rent_to_own"]
PaymentMethod = Literal["cash", "card", "bnpl", "pal", "rto_full", "rto_buyout"]
YearConfidence = Literal["high", "low", "none"]
EarlyPurchaseRule = Literal["pct_of_remaining", "cash_price_minus_pct_paid", "none"]
Lang = Literal["en", "es"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Item(Contract):
    """One appliance.

    `attributes` keys in use (PLAN.md "Fixed interfaces"): `product_class` (CFR class code,
    e.g. "3"), `volume_cuft` (total volume printed on the label), `adjusted_volume_cuft`
    (DOE adjusted volume; only this feeds the standard ceiling), `width_in`, and
    `label_kwh_per_year` (kWh printed on the unit's own EnergyGuide label).
    """

    id: str
    category: str
    brand: str
    model: str
    serial: str | None = None
    mfg_year: int | None = None
    year_confidence: YearConfidence = "none"
    condition: Condition
    warranty_months: int | None = Field(default=None, ge=0)
    attributes: dict[str, str | float] = Field(default_factory=dict)

    @field_validator("mfg_year")
    @classmethod
    def _plausible_year(cls, year: int | None) -> int | None:
        if year is not None and not 1940 <= year <= date.today().year:
            raise ValueError(f"mfg_year must be between 1940 and {date.today().year}")
        return year


class Offer(Contract):
    item_id: str
    price: float = Field(ge=0)
    seller_type: SellerType
    source: OfferSource
    source_id: str
    url: str | None = None
    retrieved_at: date | None = None
    available_within_days: int | None = Field(default=None, ge=0)


class Lease(Contract):
    weekly_payment: float = Field(gt=0)
    term_weeks: int = Field(gt=0, le=260)
    cash_price: float = Field(ge=0)
    fees: float = Field(default=0, ge=0)
    early_purchase_rule: EarlyPurchaseRule = "none"
    early_purchase_pct: float | None = Field(default=None, ge=0, le=1)
    early_purchase_text: str = ""
    missed_payment_rule: str = ""
    source_id: str = "user_lease"
    # As printed on the lease (task 1.7). A promotion can make today's payment smaller than one
    # weekly payment, and a lease's own total can differ from weekly_payment * term_weeks by rounding;
    # when set, the engine uses these instead of deriving them (spec 3: prefer the lease's own numbers).
    payment_today: float | None = Field(default=None, ge=0)
    total_of_payments: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _pct_matches_rule(self) -> "Lease":
        if (self.early_purchase_rule == "none") != (self.early_purchase_pct is None):
            raise ValueError("early_purchase_pct is required exactly when early_purchase_rule is not 'none'")
        return self


class CostLine(Contract):
    """`source_type` and `source_id` describe the line's main input (for electricity, the kWh
    figure); `other_source_ids` lists the sources of the formula's other inputs (the rate)."""

    kind: CostKind
    label: str
    amount_low: float | None
    amount_high: float | None
    period: Period
    source_type: SourceType
    source_id: str | None
    formula: str
    other_source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _blank_exactly_when_not_estimated(self) -> "CostLine":
        blank = self.amount_low is None and self.amount_high is None
        if self.source_type == "not_estimated":
            if not blank:
                raise ValueError("a not_estimated line has no amounts")
            return self
        if self.amount_low is None or self.amount_high is None:
            raise ValueError("an estimated line needs both amount_low and amount_high")
        if self.amount_low > self.amount_high:
            raise ValueError("amount_low must not exceed amount_high")
        if not self.source_id:
            raise ValueError("an estimated line needs a source_id")
        return self


class Path(Contract):
    name: str
    group: PathGroup
    payment_method: PaymentMethod | None
    pay_today: float
    total_3yr_low: float
    total_3yr_high: float
    cost_per_year_low: float | None
    cost_per_year_high: float | None
    expected_life_low: float | None
    expected_life_high: float | None
    monthly_low: list[float] = Field(min_length=MONTHS, max_length=MONTHS)
    monthly_high: list[float] = Field(min_length=MONTHS, max_length=MONTHS)
    carbon_kg: float | None
    carbon_source_ids: list[str] = Field(default_factory=list)
    lines: list[CostLine]
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _carbon_is_sourced(self) -> "Path":
        if self.carbon_kg is not None and not self.carbon_source_ids:
            raise ValueError("a carbon figure needs carbon_source_ids (the kWh source and the grid emission rate source)")
        return self


class _OrderedCost(Contract):
    cost_low: float = Field(ge=0)
    cost_high: float = Field(ge=0)

    @model_validator(mode="after")
    def _low_not_above_high(self) -> "_OrderedCost":
        if self.cost_low > self.cost_high:
            raise ValueError("cost_low must not exceed cost_high")
        return self


class UpkeepItem(_OrderedCost):
    label: str
    every_months: int = Field(gt=0)
    source_id: str


class RepairRange(_OrderedCost):
    label: str
    source_id: str


class LifespanRange(Contract):
    low_years: float = Field(gt=0)
    high_years: float = Field(gt=0)
    source_id: str

    @model_validator(mode="after")
    def _ordered(self) -> "LifespanRange":
        if self.low_years > self.high_years:
            raise ValueError("low_years must not exceed high_years")
        return self


class CategoryProfile(Contract):
    category: str
    energy_dataset_refs: list[str]
    usage_assumption: str
    upkeep_schedule: list[UpkeepItem]
    repair_ranges: list[RepairRange]
    lifespan_range: LifespanRange | None
    carbon_applicable: bool
    end_of_life_notes: str = ""


class Source(Contract):
    id: str
    title: str
    publisher: str
    url: str
    retrieved_date: date
    notes: str = ""


class Contribution(Contract):
    """What one engine module adds to a path: month 0 is today."""

    pay_today: float
    monthly_low: list[float] = Field(min_length=MONTHS, max_length=MONTHS)
    monthly_high: list[float] = Field(min_length=MONTHS, max_length=MONTHS)
    lines: list[CostLine]


class RateValue(Contract):
    value: float
    source_id: str


class ModelEnergy(Contract):
    kwh_per_year: float = Field(ge=0)
    source_type: SourceType
    source_id: str


class BnplTerms(Contract):
    provider: str
    installments: int = Field(gt=0)
    interval_weeks: int = Field(gt=0)
    apr: float = Field(ge=0)
    source_id: str


class SerialDecode(Contract):
    mfg_year: int | None
    year_confidence: YearConfidence
    source_id: str | None
    note: str


class QuoteRequest(Contract):
    """`current` is "the one you have" and enables the repair path."""

    current: Item | None = None
    items: list[Item] = Field(default_factory=list)
    offers: list[Offer] = Field(default_factory=list)
    lease: Lease | None = None
    repair_quote_low: float | None = Field(default=None, ge=0)
    repair_quote_high: float | None = Field(default=None, ge=0)
    budget_today: float | None = Field(default=None, ge=0)
    usage_adjust: float | None = Field(default=None, gt=0)


class ScanResult(Contract):
    """What a scan read (task 1.7). `fields` holds every value read from the image, valid or not,
    to pre-fill the correction form. `item`, `offer` and `lease` are set only when `valid`, so every
    object in a scan result is a complete, validated contract object."""

    kind: ScanKind
    valid: bool
    errors: list[str] = Field(default_factory=list)
    fields: dict[str, str | float | int | bool | None] = Field(default_factory=dict)
    item: Item | None = None
    offer: Offer | None = None
    lease: Lease | None = None

    @model_validator(mode="after")
    def _objects_only_when_valid(self) -> "ScanResult":
        if not self.valid and (self.item or self.offer or self.lease):
            raise ValueError("an invalid scan carries its values in fields, never as item, offer or lease")
        if self.valid and self.errors:
            raise ValueError("a valid scan has no errors")
        return self


class ShopFilters(Contract):
    category: str | None = None
    budget_today: float | None = Field(default=None, ge=0)
    need_within_days: int | None = Field(default=None, ge=0)
    max_width_in: float | None = Field(default=None, gt=0)
    conditions: list[Condition] = Field(default_factory=list)


class ShopParseRequest(Contract):
    text: str


class ShopRankRequest(Contract):
    filters: ShopFilters
    offers: list[Offer] = Field(default_factory=list)
    items: list[Item] = Field(default_factory=list)


class RankedOffer(Contract):
    offer: Offer
    path: Path


class VoiceRequest(Contract):
    paths: list[Path]
    lang: Lang
