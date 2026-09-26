// One way to get the item: its three headline numbers, its carbon, and the
// cost lines behind them (PLAN.md task 2.9).

import { useId, useState } from 'react'
import type { CostLine, Path } from '../contracts'
import { NOT_ESTIMATED, PERIOD_SUFFIX, SOURCE_LABELS, money, range, rangeNote } from '../format'

function Figure({ label, value, note }: { label: string; value: string; note?: string | null }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-neutral-600">{label}</dt>
      <dd className="text-3xl font-bold leading-tight tabular-nums text-neutral-900">{value}</dd>
      {note && <dd className="text-sm text-neutral-600">{note}</dd>}
    </div>
  )
}

function LineButton({ line, onLineTap }: { line: CostLine; onLineTap?: (line: CostLine) => void }) {
  return (
    <button
      type="button"
      onClick={() => onLineTap?.(line)}
      className="flex w-full items-center justify-between gap-3 py-2 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-900"
    >
      <span className="min-w-0">
        <span className="block text-sm text-neutral-900">{line.label}</span>
        <span className="block text-xs text-neutral-600">{SOURCE_LABELS[line.source_type]}</span>
      </span>
      {line.source_type === 'not_estimated' ? (
        <span className="h-6 w-20 shrink-0 rounded border border-dashed border-neutral-400">
          <span className="sr-only">{NOT_ESTIMATED}</span>
        </span>
      ) : (
        <span className="shrink-0 text-sm font-semibold tabular-nums text-neutral-900">
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
  return (
    <article aria-labelledby={headingId} className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm">
      <h3 id={headingId} className="text-lg font-semibold leading-snug text-neutral-900">
        {path.name}
      </h3>
      <dl className="mt-3 space-y-3">
        <Figure label="Pay today" value={money(path.pay_today)} />
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
      {path.carbon_kg !== null && (
        <p className="mt-3 text-sm text-emerald-900">
          Carbon over 3 years:{' '}
          <span className="font-semibold tabular-nums">{Math.round(path.carbon_kg).toLocaleString('en-US')} kg CO2</span>
        </p>
      )}
      <button
        type="button"
        aria-expanded={open}
        aria-controls={linesId}
        onClick={() => setOpen((o) => !o)}
        className="mt-3 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm font-semibold text-neutral-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-900"
      >
        What's in this number
      </button>
      {open && (
        <ul id={linesId} className="mt-2 divide-y divide-neutral-200">
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
