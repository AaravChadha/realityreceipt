// Shop (PLAN.md task 4.4). A request in plain words goes to /shop/parse; the filters
// read from it come back as editable chips (the visible AI step), and only after the
// person checks them does /shop/rank run. Offers link out to the retailer: no checkout here.
import { ArrowUpRight, CircleAlert, Info, ListOrdered, LoaderCircle, SlidersHorizontal, Sparkles } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Textarea } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { parseShopRequest, rankShopOffers } from '../api'
import type { Condition, RankedOffer, ShopFilters } from '../contracts'
import { CONDITIONS } from '../contracts'
import { flagSentence, money, range } from '../format'

const CONDITION_LABELS: Record<Condition, string> = {
  new: 'New',
  used_as_is: 'Used, as-is',
  refurbished: 'Refurbished',
}

// The chips hold text while being edited; numbers are read back only when ranking.
interface Chips {
  budget: string
  days: string
  width: string
  conditions: Condition[]
}

const toText = (n: number | null | undefined) => (n === null || n === undefined ? '' : String(n))

function toChips(f: ShopFilters): Chips {
  return {
    budget: toText(f.budget_today),
    days: toText(f.need_within_days),
    width: toText(f.max_width_in),
    conditions: f.conditions ?? [],
  }
}

type ChipName = 'budget' | 'days' | 'width'
type ChipErrors = Partial<Record<ChipName, string>>

const CHIP_ERRORS: Record<ChipName, string> = {
  budget: 'Spend must be a number, like 300.',
  days: 'Days must be a whole number, like 7.',
  width: 'Width must be a number, like 28.',
}

// '' is a cleared chip: no filter. Text that is not a number >= 0 is an error, never a
// dropped filter, so the person sees it and fixes it.
function toNumber(raw: string, wholeOnly = false): number | null | 'bad' {
  const s = raw.replace(/[$,\s]/g, '')
  if (s === '') return null
  if (!(wholeOnly ? /^\d+$/ : /^\d+(\.\d+)?$/).test(s)) return 'bad'
  return Number(s)
}

// The filters to rank with, or the chips that could not be read.
function toFilters(parsed: ShopFilters, c: Chips): { filters: ShopFilters } | { errors: ChipErrors } {
  const budget = toNumber(c.budget)
  const days = toNumber(c.days, true)
  const width = toNumber(c.width)
  const errors: ChipErrors = {}
  if (budget === 'bad') errors.budget = CHIP_ERRORS.budget
  if (days === 'bad') errors.days = CHIP_ERRORS.days
  if (width === 'bad') errors.width = CHIP_ERRORS.width
  if (budget === 'bad' || days === 'bad' || width === 'bad') return { errors }
  return {
    filters: {
      category: parsed.category ?? null,
      budget_today: budget,
      need_within_days: days,
      max_width_in: width,
      conditions: c.conditions,
    },
  }
}

// Retailer cache ids read "bb-gte18dtnrww"; the part after the store prefix is the model number.
function modelLabel(itemId: string): string {
  const dash = itemId.indexOf('-')
  return (dash >= 0 ? itemId.slice(dash + 1) : itemId).toUpperCase()
}

function Chip({
  id,
  label,
  value,
  onChange,
  prefix,
  suffix,
  inputMode,
  error,
}: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  prefix?: string
  suffix?: string
  inputMode: 'decimal' | 'numeric'
  error?: string
}) {
  const errorId = `${id}-error`
  return (
    <div>
      <div
        className={cn(
          'flex min-h-11 items-center gap-1.5 rounded-full border px-3 py-1 transition-colors focus-within:ring-[3px] focus-within:ring-ring/40',
          error ? 'border-destructive/50 bg-destructive/10' : 'border-primary/30 bg-primary/10',
        )}
      >
        <label htmlFor={id} className="text-sm font-medium text-foreground">
          {label}
        </label>
        {prefix && <span aria-hidden="true" className="font-mono text-sm text-muted-foreground">{prefix}</span>}
        <input
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          inputMode={inputMode}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          autoComplete="off"
          placeholder="any"
          className="w-16 rounded-md border border-input bg-card px-1.5 py-0.5 font-mono text-base tabular-nums text-foreground outline-none placeholder:text-muted-foreground focus-visible:border-ring"
        />
        {suffix && <span className="text-sm text-muted-foreground">{suffix}</span>}
      </div>
      {error && (
        <p id={errorId} role="alert" className="mt-1 px-3 text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}

function OfferCard({ ranked, place }: { ranked: RankedOffer; place: number }) {
  const { offer, path } = ranked
  const headingId = `offer-${place}`
  const sentences = [...new Set(path.flags)].map(flagSentence).filter((s): s is string => s !== null)
  return (
    <li>
      <article
        aria-labelledby={headingId}
        className={cn(
          'rounded-2xl border bg-card p-4 shadow-sm',
          place === 1 ? 'border-primary/50 ring-1 ring-primary/20' : 'border-border',
        )}
      >
        <h3 id={headingId} className="font-mono text-base font-semibold tracking-tight">
          {place}. {modelLabel(offer.item_id)}
        </h3>
        <p className="text-sm text-muted-foreground">{path.name}</p>
        <dl className="mt-3 grid grid-cols-2 gap-3 rounded-xl bg-muted/60 p-3">
          <div className="min-w-0">
            <dt className="font-mono text-[0.7rem] font-semibold tracking-widest text-muted-foreground uppercase">Price</dt>
            <dd className="font-mono text-xl font-bold tabular-nums">{money(offer.price)}</dd>
          </div>
          <div className="min-w-0">
            <dt className="font-mono text-[0.7rem] font-semibold tracking-widest text-muted-foreground uppercase">
              Cost per year
            </dt>
            <dd className="font-mono text-xl font-bold tabular-nums wrap-break-word">{range(path.cost_per_year_low, path.cost_per_year_high)}</dd>
          </div>
        </dl>
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
        {offer.url && (
          <Button asChild variant={place === 1 ? 'default' : 'outline'} className="mt-4 w-full">
            <a href={offer.url} target="_blank" rel="noopener noreferrer">
              View at retailer
              <ArrowUpRight aria-hidden="true" />
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
          </Button>
        )}
      </article>
    </li>
  )
}

const hintClass = 'text-sm text-muted-foreground'
const failureClass =
  'flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive'

type Status = 'idle' | 'loading' | 'done' | 'error'

export default function Shop() {
  const [text, setText] = useState('')
  const [parsed, setParsed] = useState<ShopFilters | null>(null)
  const [chips, setChips] = useState<Chips>(toChips({}))
  const [chipErrors, setChipErrors] = useState<ChipErrors>({})
  const [parseStatus, setParseStatus] = useState<Status>('idle')
  const [rankStatus, setRankStatus] = useState<Status>('idle')
  const [offers, setOffers] = useState<RankedOffer[]>([])
  const [failure, setFailure] = useState('')

  const message = (err: unknown) => (err instanceof Error ? err.message : String(err))

  async function onParse(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (text.trim() === '') return
    setParseStatus('loading')
    setRankStatus('idle')
    setOffers([])
    try {
      const filters = await parseShopRequest(text.trim())
      setParsed(filters)
      setChips(toChips(filters))
      setChipErrors({})
      setParseStatus('done')
    } catch (err) {
      setFailure(message(err))
      setParseStatus('error')
    }
  }

  async function onRank() {
    if (parsed === null) return
    const read = toFilters(parsed, chips)
    if ('errors' in read) {
      setChipErrors(read.errors)
      setRankStatus('idle')
      setOffers([])
      return
    }
    setChipErrors({})
    setRankStatus('loading')
    try {
      setOffers(await rankShopOffers({ filters: read.filters }))
      setRankStatus('done')
    } catch (err) {
      setFailure(message(err))
      setRankStatus('error')
    }
  }

  const setChip = (name: ChipName) => (v: string) => {
    setChips((c) => ({ ...c, [name]: v }))
    setChipErrors(({ [name]: _cleared, ...rest }) => rest)
  }
  const toggle = (cond: Condition) =>
    setChips((c) => ({
      ...c,
      conditions: c.conditions.includes(cond) ? c.conditions.filter((x) => x !== cond) : [...c.conditions, cond],
    }))

  const nothingRead =
    parsed !== null &&
    parsed.budget_today == null &&
    parsed.need_within_days == null &&
    parsed.max_width_in == null &&
    (parsed.conditions ?? []).length === 0

  return (
    <div className="space-y-6">
      <Card className="p-4">
      <form noValidate onSubmit={onParse} className="space-y-3">
        <label htmlFor="shop-request" className="flex items-center gap-2.5 text-base font-semibold">
          <span aria-hidden="true" className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
            <Sparkles className="size-4" />
          </span>
          What are you looking for?
        </label>
        <p id="shop-request-hint" className={hintClass}>
          In your own words, for example: About $300, small space, need it this week.
        </p>
        <Textarea
          id="shop-request"
          aria-describedby="shop-request-hint"
          rows={3}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <Button type="submit" size="lg" className="w-full" disabled={parseStatus === 'loading' || text.trim() === ''}>
          {parseStatus === 'loading' ? <LoaderCircle aria-hidden="true" className="animate-spin" /> : <Sparkles aria-hidden="true" />}
          {parseStatus === 'loading' ? 'Reading your request...' : 'Read my request'}
        </Button>
      </form>
      </Card>

      {parseStatus === 'error' && (
        <p role="alert" className={failureClass}>
          <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span>Could not read the request: {failure}</span>
        </p>
      )}

      {parseStatus === 'done' && (
        <section aria-labelledby="filters-heading" className="space-y-3 rounded-2xl border border-border bg-card p-4 shadow-sm animate-in fade-in slide-in-from-bottom-2">
          <h2 id="filters-heading" className="flex items-center gap-2 text-lg font-semibold">
            <SlidersHorizontal aria-hidden="true" className="size-4 text-primary" />
            What we read from it
          </h2>
          <p className={hintClass}>
            {nothingRead
              ? 'No filters were read from that. Set any you want below, or leave them blank to see every offer.'
              : 'Check these before ranking. Change any value, or clear it to drop that filter.'}
          </p>
          <div className="flex flex-wrap gap-2">
            <Chip id="chip-budget" label="Spend today up to" prefix="$" value={chips.budget} onChange={setChip('budget')} inputMode="decimal" error={chipErrors.budget} />
            <Chip id="chip-days" label="Need it within" suffix="days" value={chips.days} onChange={setChip('days')} inputMode="numeric" error={chipErrors.days} />
            <Chip id="chip-width" label="Width up to" suffix="in" value={chips.width} onChange={setChip('width')} inputMode="decimal" error={chipErrors.width} />
          </div>
          <div role="group" aria-label="Condition" className="flex flex-wrap gap-2">
            {CONDITIONS.map((cond) => {
              const on = chips.conditions.includes(cond)
              return (
                <Button
                  key={cond}
                  type="button"
                  variant={on ? 'default' : 'outline'}
                  aria-pressed={on}
                  onClick={() => toggle(cond)}
                  className="rounded-full"
                >
                  {CONDITION_LABELS[cond]}
                </Button>
              )
            })}
          </div>
          <p className={hintClass}>With no condition picked, new and used offers are both shown.</p>
          <Button type="button" size="lg" className="w-full" onClick={onRank} disabled={rankStatus === 'loading'}>
            {rankStatus === 'loading' ? <LoaderCircle aria-hidden="true" className="animate-spin" /> : <ListOrdered aria-hidden="true" />}
            {rankStatus === 'loading' ? 'Ranking offers...' : 'Rank offers by cost per year'}
          </Button>
        </section>
      )}

      {rankStatus === 'error' && (
        <p role="alert" className={failureClass}>
          <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span>Could not rank offers: {failure}</span>
        </p>
      )}

      {rankStatus === 'done' && (
        <section aria-labelledby="offers-heading">
          <h2 id="offers-heading" className="flex items-center gap-2 text-lg font-semibold">
            <ListOrdered aria-hidden="true" className="size-4 text-primary" />
            Offers ranked by cost per year
          </h2>
          {offers.length === 0 ? (
            <p className={`mt-2 ${hintClass}`}>No offers match these filters yet. Try clearing a filter.</p>
          ) : (
            <ol className="mt-3 space-y-4">
              {offers.map((r, i) => (
                <OfferCard key={`${r.offer.source_id}-${r.offer.item_id}-${i}`} ranked={r} place={i + 1} />
              ))}
            </ol>
          )}
          <p className={`mt-3 ${hintClass}`}>Buying happens on the seller's site, not here.</p>
        </section>
      )}
    </div>
  )
}
