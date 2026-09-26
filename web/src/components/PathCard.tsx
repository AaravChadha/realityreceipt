// One way to get the item: its three headline numbers, its carbon, its flags
// as plain sentences, and the cost lines behind them (PLAN.md tasks 2.9, 2.9.1).

import { useId, useState } from 'react'
import type { CostLine, Path } from '../contracts'
import { FLAG_SENTENCES, NOT_ESTIMATED, PERIOD_SUFFIX, SOURCE_LABELS, flagSentence, money, range, rangeNote } from '../format'

// Shown elsewhere: the incomplete-costs note under the numbers, the sample banner on the receipt.
const NOT_IN_FLAG_LIST = new Set(['costs_not_estimated', 'fixture'])

function Figure({
  label,
  value,
  prefix,
  note,
}: {
  label: string
  value: string
  prefix?: string
  note?: string | null
}) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">{label}</dt>
      <dd className="text-3xl font-bold leading-tight tabular-nums text-stone-900 dark:text-stone-100">
        {prefix && <span className="text-base font-semibold">{prefix} </span>}
        {value}
      </dd>
      {note && <dd className="text-sm text-stone-600 dark:text-stone-400">{note}</dd>}
    </div>
  )
}

function LineButton({ line, onLineTap }: { line: CostLine; onLineTap?: (line: CostLine) => void }) {
  return (
    <button
      type="button"
      onClick={() => onLineTap?.(line)}
      className="flex w-full items-center justify-between gap-3 py-2 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-stone-900 dark:focus-visible:outline-stone-100"
    >
      <span className="min-w-0">
        <span className="block text-sm text-stone-900 dark:text-stone-100">{line.label}</span>
        <span className="block text-xs text-stone-600 dark:text-stone-400">{SOURCE_LABELS[line.source_type]}</span>
      </span>
      {line.source_type === 'not_estimated' ? (
        <span className="h-6 w-20 shrink-0 rounded border border-dashed border-stone-400 dark:border-stone-600">
          <span className="sr-only">{NOT_ESTIMATED}</span>
        </span>
      ) : (
        <span className="shrink-0 text-sm font-semibold tabular-nums text-stone-900 dark:text-stone-100">
          {range(line.amount_low, line.amount_high)}
          {PERIOD_SUFFIX[line.period]}
        </span>
      )}
    </button>
  )
}

export function PathCard({ path, onLineTap }: { path: Path; onLineTap?: (line: CostLine) => void }) {
  const [open, setOpen] = useState(false)
  const headingId = useId()
  const linesId = useId()
  const incomplete = path.flags.includes('costs_not_estimated')
  const sentences = [...new Set(path.flags.filter((f) => !NOT_IN_FLAG_LIST.has(f)))]
    .map(flagSentence)
    .filter((s) => s !== null)
  return (
    <article
      aria-labelledby={headingId}
      className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm dark:border-stone-800 dark:bg-stone-900"
    >
      <h3 id={headingId} className="text-lg font-semibold leading-snug text-stone-900 dark:text-stone-100">
        {path.name}
      </h3>
      <dl className="mt-3 space-y-3">
        <Figure
          label="Pay today"
          value={money(path.pay_today)}
          prefix={path.payment_method === 'pal' ? 'up to' : undefined}
        />
        <Figure
          label="Total over 3 years"
          value={range(path.total_3yr_low, path.total_3yr_high)}
          note={rangeNote(path.total_3yr_low, path.total_3yr_high)}
        />
        <Figure
          label="Cost per year of use"
          value={range(path.cost_per_year_low, path.cost_per_year_high)}
          note={rangeNote(path.cost_per_year_low, path.cost_per_year_high)}
        />
      </dl>
      {incomplete && (
        <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900 dark:bg-amber-950 dark:text-amber-200">
          {FLAG_SENTENCES.costs_not_estimated}
        </p>
      )}
      {path.carbon_kg !== null && (
        <p className="mt-3 text-sm text-emerald-900 dark:text-emerald-300">
          Carbon over 3 years:{' '}
          <span className="font-semibold tabular-nums">{Math.round(path.carbon_kg).toLocaleString('en-US')} kg CO2e</span>
        </p>
      )}
      {sentences.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm text-stone-700 dark:text-stone-300">
          {sentences.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      )}
      <button
        type="button"
        aria-expanded={open}
        aria-controls={linesId}
        onClick={() => setOpen((o) => !o)}
        className="mt-3 min-h-11 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm font-semibold text-stone-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-stone-900 dark:border-stone-700 dark:text-stone-100 dark:focus-visible:outline-stone-100"
      >
        What's in this number
      </button>
      {open && (
        <ul id={linesId} className="mt-2 divide-y divide-stone-200 dark:divide-stone-800">
          {path.lines.map((line, i) => (
            <li key={`${i}-${line.label}`}>
              <LineButton line={line} onLineTap={onLineTap} />
            </li>
          ))}
        </ul>
      )}
    </article>
  )
}
