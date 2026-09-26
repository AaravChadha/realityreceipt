// How the receipt writes money (PLAN.md task 2.9). Headline numbers are whole
// dollars; the exact cents stay in each line's formula.

import type { Period, SourceType } from './contracts'

export const NOT_ESTIMATED = 'not estimated'

const dollars = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
})

/** Whole dollars, e.g. "$1,233"; null is "not estimated". */
export function money(n: number | null): string {
  if (n === null) return NOT_ESTIMATED
  const whole = Math.round(n)
  return dollars.format(whole === 0 ? 0 : whole)
}

/** "$A to $B"; one amount when both ends round the same; "$A or more" or "up to $B" when one end is missing. */
export function range(low: number | null, high: number | null): string {
  if (low === null && high === null) return NOT_ESTIMATED
  if (high === null) return `${money(low)} or more`
  if (low === null) return `up to ${money(high)}`
  const a = money(low)
  const b = money(high)
  return a === b ? a : `${a} to ${b}`
}

/** The small note under a range with one end missing, else null. */
export function rangeNote(low: number | null, high: number | null): string | null {
  if (low !== null && high === null) return 'upper end not estimated'
  if (low === null && high !== null) return 'lower end not estimated'
  return null
}

export const SOURCE_LABELS: Record<SourceType, string> = {
  rated: 'Rated',
  published: 'Published',
  user_entered: 'You entered',
  not_estimated: 'Not estimated',
}

export const PERIOD_SUFFIX: Record<Period, string> = {
  once: '',
  month: ' a month',
  year: ' a year',
  window: '',
}

/** One plain sentence per flag pinned in PLAN.md "Fixed interfaces" (task 2.9.1). */
export const FLAG_SENTENCES = {
  costs_not_estimated: 'Some costs are not estimated, so the real total may be higher.',
  past_typical_life: 'This unit is at or past its typical life.',
  test_procedure_changed:
    'The energy test changed around 2014, so ratings from before and after it are not directly comparable.',
  year_from_serial_low_confidence: 'The year made comes from the serial number and may not be exact.',
  pal_caps_not_an_offer: 'These figures use the federal limits on credit union PALs, not an offer from a lender.',
  bnpl_terms_not_an_offer: "These figures use one provider's published terms, not an offer.",
  over_budget_today: 'This costs more today than the amount you said you can spend.',
  delivery_unknown: 'The delivery time for this offer is not known.',
  width_unknown: 'The width of this unit is not known.',
  fixture: 'Sample data, not a real quote',
} as const

/** The sentence for a pinned flag; null for any other flag, which is not shown. */
export function flagSentence(flag: string): string | null {
  return Object.hasOwn(FLAG_SENTENCES, flag) ? FLAG_SENTENCES[flag as keyof typeof FLAG_SENTENCES] : null
}
