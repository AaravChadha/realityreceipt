// The receipt: every path in API order, one column, phone first (PLAN.md tasks
// 2.9, 2.9.1, 3.11). No width of its own: it sits inside the app shell and follows
// its light and dark colors, drawn as a printed slip with torn edges (task 4.10).
// Paths print in once; that motion is off when the user prefers reduced motion.

import { motion, useReducedMotion } from 'framer-motion'
import { FlaskConical } from 'lucide-react'
import type { CostLine, Path } from '../contracts'
import { FLAG_SENTENCES } from '../format'
import { PathCard } from './PathCard'

export function overSpend(path: Path, budgetToday: number | null | undefined): boolean {
  if (path.flags.includes('over_budget_today')) return true
  return budgetToday != null && path.pay_today > budgetToday
}

/**
 * The index of the path whose whole 3-year range is below every other path's, or -1.
 * Overlapping ranges, a missing end or a path with costs not estimated name no winner,
 * so the badge only ever states what the receipt itself shows (spec §6).
 */
export function lowestTotal(paths: Path[]): number {
  if (paths.length < 2) return -1
  const best = paths.reduce((b, p, i) => (p.total_3yr_high < paths[b].total_3yr_high ? i : b), 0)
  const winner = paths[best]
  if (winner.flags.includes('costs_not_estimated')) return -1
  const clear = paths.every((p, i) => i === best || winner.total_3yr_high < p.total_3yr_low)
  return clear ? best : -1
}

const printed = new Intl.DateTimeFormat('en-US', { dateStyle: 'medium' })

export function Receipt({
  paths,
  onLineTap,
  budgetToday = null,
}: {
  paths: Path[]
  onLineTap?: (line: CostLine) => void
  /** What the user can spend today. A path whose pay today is above this is dimmed, never hidden. */
  budgetToday?: number | null
}) {
  const reduceMotion = useReducedMotion()
  const sample = paths.some((p) => p.flags.includes('fixture'))
  const lowest = lowestTotal(paths)
  return (
    <section aria-labelledby="receipt-heading" className="drop-shadow-md">
      {sample && (
        <p className="sticky top-2 z-10 mb-3 flex items-center justify-center gap-2 rounded-full border border-amber-300 bg-amber-100 px-4 py-2 text-center text-sm font-semibold text-amber-900 shadow-sm dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          <FlaskConical aria-hidden="true" className="size-4 shrink-0" />
          {FLAG_SENTENCES.fixture}
        </p>
      )}
      <div className="receipt-edge bg-paper text-ink">
        <header className="px-5 pt-2 pb-4 text-center">
          <p aria-hidden="true" className="font-mono text-xs font-semibold tracking-[0.3em] text-muted-foreground uppercase">
            RealityReceipt
          </p>
          <h2 id="receipt-heading" className="mt-1 text-2xl font-bold tracking-tight">
            Your receipt
          </h2>
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            {printed.format(new Date())} · {paths.length} {paths.length === 1 ? 'way' : 'ways'} to get it
          </p>
          <p className="mt-2 text-xs text-muted-foreground">Tap any line to see its source and formula.</p>
        </header>
        <div aria-hidden="true" className="mx-5 border-t-2 border-dashed border-border" />
        {paths.length === 0 ? (
          <p className="px-5 py-6 text-center text-sm text-muted-foreground">No paths to compare yet.</p>
        ) : (
          <ol className="divide-y-2 divide-dashed divide-border">
            {paths.map((path, i) => (
              <motion.li
                key={`${i}-${path.name}`}
                initial={reduceMotion ? false : { y: 16, clipPath: 'inset(0 0 100% 0)' }}
                animate={{ y: 0, clipPath: 'inset(0 0 0% 0)' }}
                transition={reduceMotion ? { duration: 0 } : { duration: 0.45, delay: i * 0.06, ease: 'easeOut' }}
              >
                <PathCard path={path} onLineTap={onLineTap} overBudget={overSpend(path, budgetToday)} lowest={i === lowest} />
              </motion.li>
            ))}
          </ol>
        )}
        <div aria-hidden="true" className="mx-5 border-t-2 border-dashed border-border" />
        <p className="px-5 pt-4 pb-1 text-center font-mono text-[0.7rem] tracking-widest text-muted-foreground uppercase">
          Every number is sourced · Thank you
        </p>
      </div>
    </section>
  )
}
