// One way to get the item: its three headline numbers, its carbon, its flags
// as plain sentences, and the cost lines behind them (PLAN.md tasks 2.9, 2.9.1, 3.11).
// Styled as one section of a printed receipt (task 4.10).

import { ChevronDown, Info, Leaf, TrendingDown, TriangleAlert, Wallet } from 'lucide-react'
import { useId, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { CostLine, Path, PathGroup, SourceType } from '../contracts'
import { FLAG_SENTENCES, NOT_ESTIMATED, PERIOD_SUFFIX, SOURCE_LABELS, flagSentence, money, range, rangeNote } from '../format'

// Shown elsewhere: the incomplete-costs note under the numbers, the sample banner on the receipt.
const NOT_IN_FLAG_LIST = new Set(['costs_not_estimated', 'fixture'])

const GROUP_LABELS: Record<PathGroup, string> = {
  keep: 'Keep',
  repair: 'Repair',
  used_as_is: 'Used',
  refurbished: 'Refurbished',
  new: 'New',
  rent_to_own: 'Rent-to-own',
}

const SOURCE_BADGE: Record<SourceType, 'success' | 'secondary' | 'outline'> = {
  rated: 'success',
  published: 'secondary',
  user_entered: 'outline',
  not_estimated: 'outline',
}

function Figure({
  label,
  value,
  prefix,
  note,
  big = false,
}: {
  label: string
  value: string
  prefix?: string
  note?: string | null
  big?: boolean
}) {
  return (
    <div className="min-w-0">
      <dt className="font-mono text-[0.7rem] font-semibold tracking-widest text-muted-foreground uppercase">{label}</dt>
      <dd className={cn('font-mono leading-tight font-bold tabular-nums text-ink', big ? 'text-4xl' : 'text-xl wrap-break-word')}>
        {prefix && <span className="font-sans text-sm font-semibold text-muted-foreground">{prefix} </span>}
        {value}
      </dd>
      {note && <dd className="text-xs text-muted-foreground">{note}</dd>}
    </div>
  )
}

function LineButton({ line, onLineTap }: { line: CostLine; onLineTap?: (line: CostLine) => void }) {
  return (
    <button
      type="button"
      onClick={() => onLineTap?.(line)}
      className="group flex min-h-11 w-full items-center gap-2 rounded-md px-1 py-2 text-left outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50"
    >
      <span className="min-w-0">
        <span className="block text-sm text-ink underline decoration-border decoration-dotted underline-offset-4 group-hover:decoration-primary">
          {line.label}
        </span>
        <Badge variant={SOURCE_BADGE[line.source_type]} className="mt-1">
          {SOURCE_LABELS[line.source_type]}
        </Badge>
      </span>
      <span aria-hidden="true" className="leader" />
      {line.source_type === 'not_estimated' ? (
        <span className="h-6 w-20 shrink-0 rounded border border-dashed border-muted-foreground/50">
          <span className="sr-only">{NOT_ESTIMATED}</span>
        </span>
      ) : (
        <span className="shrink-0 text-right font-mono text-sm font-semibold tabular-nums text-ink">
          {range(line.amount_low, line.amount_high)}
          {PERIOD_SUFFIX[line.period]}
        </span>
      )}
    </button>
  )
}

export const OVER_SPEND = 'More than you can spend today'

export function PathCard({
  path,
  onLineTap,
  overBudget = false,
  lowest = false,
}: {
  path: Path
  onLineTap?: (line: CostLine) => void
  overBudget?: boolean
  /** This path's whole 3-year range sits below every other path's on the same receipt. */
  lowest?: boolean
}) {
  const [open, setOpen] = useState(false)
  const headingId = useId()
  const linesId = useId()
  const incomplete = path.flags.includes('costs_not_estimated')
  const sentences = [...new Set(path.flags.filter((f) => !NOT_IN_FLAG_LIST.has(f)))]
    .map(flagSentence)
    .filter((s) => s !== null)
  return (
    <article aria-labelledby={headingId} className={cn('px-5 py-5 transition-opacity', overBudget && 'opacity-60')}>
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge variant="outline" className="font-mono tracking-wider uppercase">
          {GROUP_LABELS[path.group]}
        </Badge>
        {lowest && (
          <Badge variant="success">
            <TrendingDown aria-hidden="true" />
            Lowest 3-year total here
          </Badge>
        )}
        {overBudget && (
          <Badge variant="warning">
            <Wallet aria-hidden="true" />
            {OVER_SPEND}
          </Badge>
        )}
      </div>
      <h3 id={headingId} className="mt-2 text-lg leading-snug font-semibold text-ink">
        {path.name}
      </h3>
      <dl className="mt-3 space-y-3">
        <Figure
          label="Pay today"
          value={money(path.pay_today)}
          prefix={path.payment_method === 'pal' ? 'up to' : undefined}
          big
        />
        <div className="grid grid-cols-2 gap-3 rounded-xl bg-muted/60 p-3">
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
        </div>
      </dl>
      {incomplete && (
        <p className="mt-3 flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {FLAG_SENTENCES.costs_not_estimated}
        </p>
      )}
      {path.carbon_kg !== null && (
        <p className="mt-3 flex items-center gap-1.5 text-sm text-emerald-800 dark:text-emerald-300">
          <Leaf aria-hidden="true" className="size-4 shrink-0" />
          <span>
            Carbon over 3 years:{' '}
            <span className="font-mono font-semibold tabular-nums">{Math.round(path.carbon_kg).toLocaleString('en-US')} kg CO2e</span>
          </span>
        </p>
      )}
      {sentences.length > 0 && (
        <ul className="mt-3 space-y-1.5 text-sm text-muted-foreground">
          {sentences.map((s) => (
            <li key={s} className="flex items-start gap-1.5">
              <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              {s}
            </li>
          ))}
        </ul>
      )}
      <Button
        type="button"
        variant="outline"
        aria-expanded={open}
        aria-controls={linesId}
        onClick={() => setOpen((o) => !o)}
        className="mt-4 min-h-11 w-full justify-between"
      >
        What's in this number
        <ChevronDown aria-hidden="true" className={cn('transition-transform', open && 'rotate-180')} />
      </Button>
      {open && (
        <ul id={linesId} className="mt-2 divide-y divide-dashed divide-border animate-in fade-in slide-in-from-top-1">
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
