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
