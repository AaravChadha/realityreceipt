// The receipt: every path in API order, one column, phone first (PLAN.md tasks
// 2.9, 2.9.1, 3.11). No width, padding or background of its own: it sits inside the
// app shell and follows its light and dark colors. Paths print in once; that
// motion is off when the user prefers reduced motion.

import { motion, useReducedMotion } from 'framer-motion'
import type { CostLine, Path } from '../contracts'
import { FLAG_SENTENCES } from '../format'
import { PathCard } from './PathCard'

export function overSpend(path: Path, budgetToday: number | null | undefined): boolean {
  if (path.flags.includes('over_budget_today')) return true
  return budgetToday != null && path.pay_today > budgetToday
}

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
  return (
    <section aria-labelledby="receipt-heading">
      {sample && (
        <p className="sticky top-0 z-10 rounded-lg border border-amber-300 bg-amber-100 px-4 py-2 text-center text-sm font-semibold text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          {FLAG_SENTENCES.fixture}
        </p>
      )}
      <h2 id="receipt-heading" className="pt-4 text-xl font-bold">
        Your receipt
      </h2>
      {paths.length === 0 ? (
        <p className="mt-2 text-sm text-stone-600 dark:text-stone-400">No paths to compare yet.</p>
      ) : (
        <ol className="mt-3 space-y-4">
          {paths.map((path, i) => (
            <motion.li
              key={`${i}-${path.name}`}
              initial={reduceMotion ? false : { y: 16, clipPath: 'inset(0 0 100% 0)' }}
              animate={{ y: 0, clipPath: 'inset(0 0 0% 0)' }}
              transition={reduceMotion ? { duration: 0 } : { duration: 0.45, delay: i * 0.06, ease: 'easeOut' }}
            >
              <PathCard path={path} onLineTap={onLineTap} overBudget={overSpend(path, budgetToday)} />
            </motion.li>
          ))}
        </ol>
      )}
    </section>
  )
}
