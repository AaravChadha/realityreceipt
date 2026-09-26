// Hand-written mirror of api/app/models.py (PLAN.md task 1.4).
// Changes go through the A1 owner, together with models.py.
// Dates arrive as ISO strings ("2026-09-26").

export const MONTHS = 36

export const SOURCE_TYPES = ['rated', 'published', 'user_entered', 'not_estimated'] as const
export type SourceType = (typeof SOURCE_TYPES)[number]

export const COST_KINDS = ['purchase', 'financing', 'running', 'upkeep', 'repair', 'replacement', 'end_of_life'] as const
export type CostKind = (typeof COST_KINDS)[number]

export const PERIODS = ['once', 'month', 'year', 'window'] as const
export type Period = (typeof PERIODS)[number]

export const CONDITIONS = ['new', 'used_as_is', 'refurbished'] as const
export type Condition = (typeof CONDITIONS)[number]

export const OFFER_SOURCES = ['retailer_cache', 'user_listing', 'price_tag'] as const
export type OfferSource = (typeof OFFER_SOURCES)[number]

export const SELLER_TYPES = ['retailer', 'private', 'refurbisher', 'rent_to_own'] as const
export type SellerType = (typeof SELLER_TYPES)[number]

export const SCAN_KINDS = ['label', 'price_tag', 'lease', 'listing'] as const
export type ScanKind = (typeof SCAN_KINDS)[number]

export const PATH_GROUPS = ['repair', 'used_as_is', 'refurbished', 'new', 'rent_to_own'] as const
export type PathGroup = (typeof PATH_GROUPS)[number]

export const PAYMENT_METHODS = ['cash', 'card', 'bnpl', 'pal', 'rto_full', 'rto_buyout'] as const
export type PaymentMethod = (typeof PAYMENT_METHODS)[number]

export const YEAR_CONFIDENCES = ['high', 'low', 'none'] as const
export type YearConfidence = (typeof YEAR_CONFIDENCES)[number]

export const EARLY_PURCHASE_RULES = ['pct_of_remaining', 'cash_price_minus_pct_paid', 'none'] as const
export type EarlyPurchaseRule = (typeof EARLY_PURCHASE_RULES)[number]

export type Lang = 'en' | 'es'

export interface Item {
  id: string
  category: string
  brand: string
  model: string
  serial?: string | null
  mfg_year?: number | null
  year_confidence?: YearConfidence
  condition: Condition
  warranty_months?: number | null
  /**
   * Keys in use (PLAN.md "Fixed interfaces"): product_class (CFR class code, e.g. "3"),
   * volume_cuft (label total volume), adjusted_volume_cuft (DOE adjusted volume; only this
   * feeds the standard ceiling), width_in, label_kwh_per_year (kWh on the unit's EnergyGuide label).
   */
  attributes?: Record<string, string | number>
}

export interface Offer {
  item_id: string
  price: number
  seller_type: SellerType
  source: OfferSource
  source_id: string
  url?: string | null
  retrieved_at?: string | null
  available_within_days?: number | null
}

export interface Lease {
  weekly_payment: number
  term_weeks: number
  cash_price: number
  fees?: number
  early_purchase_rule?: EarlyPurchaseRule
  early_purchase_pct?: number | null
  early_purchase_text?: string
  missed_payment_rule?: string
  source_id?: string
  /** As printed; a promotion can make it less than one weekly payment. */
  payment_today?: number | null
  /** As printed; when set, the engine uses it instead of weekly_payment * term_weeks. */
  total_of_payments?: number | null
}

export interface CostLine {
  kind: CostKind
  label: string
  /** null exactly when source_type is "not_estimated". */
  amount_low: number | null
  amount_high: number | null
  period: Period
  source_type: SourceType
  /** The main input's source (for electricity, the kWh figure). */
  source_id: string | null
  formula: string
  /** Sources of the formula's other inputs (for electricity, the rate). */
  other_source_ids: string[]
}

export interface Path {
  name: string
  group: PathGroup
  payment_method: PaymentMethod | null
  pay_today: number
  total_3yr_low: number
  total_3yr_high: number
  cost_per_year_low: number | null
  cost_per_year_high: number | null
  expected_life_low: number | null
  expected_life_high: number | null
  /** 36 entries; index 0 is today. */
  monthly_low: number[]
  monthly_high: number[]
  carbon_kg: number | null
  /** Non-empty whenever carbon_kg is set: the kWh source and the grid emission rate source. */
  carbon_source_ids: string[]
  lines: CostLine[]
  flags: string[]
}

export const PATH_KEYS = [
  'name',
  'group',
  'payment_method',
  'pay_today',
  'total_3yr_low',
  'total_3yr_high',
  'cost_per_year_low',
  'cost_per_year_high',
  'expected_life_low',
  'expected_life_high',
  'monthly_low',
  'monthly_high',
  'carbon_kg',
  'carbon_source_ids',
  'lines',
  'flags',
] as const satisfies readonly (keyof Path)[]

export interface UpkeepItem {
  label: string
  cost_low: number
  cost_high: number
  every_months: number
  source_id: string
}

export interface RepairRange {
  label: string
  cost_low: number
  cost_high: number
  source_id: string
}

export interface LifespanRange {
  low_years: number
  high_years: number
  source_id: string
}

export interface CategoryProfile {
  category: string
  energy_dataset_refs: string[]
  usage_assumption: string
  upkeep_schedule: UpkeepItem[]
  repair_ranges: RepairRange[]
  lifespan_range: LifespanRange | null
  carbon_applicable: boolean
  end_of_life_notes?: string
}

export interface Source {
  id: string
  title: string
  publisher: string
  url: string
  retrieved_date: string
  notes?: string
}

export interface QuoteRequest {
  /** "The one you have"; enables the repair path. */
  current?: Item | null
  items?: Item[]
  offers?: Offer[]
  lease?: Lease | null
  repair_quote_low?: number | null
  repair_quote_high?: number | null
  budget_today?: number | null
  usage_adjust?: number | null
}

export interface ScanResult {
  kind: ScanKind
  valid: boolean
  errors: string[]
  /** Every value read from the image, valid or not: pre-fills the correction form. */
  fields: Record<string, string | number | boolean | null>
  /** item, offer and lease are set only when valid. */
  item: Item | null
  offer: Offer | null
  lease: Lease | null
}

export interface ShopFilters {
  category?: string | null
  budget_today?: number | null
  need_within_days?: number | null
  max_width_in?: number | null
  conditions?: Condition[]
}

export interface ShopParseRequest {
  text: string
}

export interface ShopRankRequest {
  filters: ShopFilters
  offers?: Offer[]
  items?: Item[]
}

export interface RankedOffer {
  offer: Offer
  path: Path
}

export interface VoiceRequest {
  paths: Path[]
  lang: Lang
}
