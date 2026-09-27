// Shop (PLAN.md task 4.4). A request in plain words goes to /shop/parse; the filters
// read from it come back as editable chips (the visible AI step), and only after the
// person checks them does /shop/rank run. Offers link out to the retailer: no checkout here.
import { useState, type FormEvent } from 'react'
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

// '' or anything that is not a number >= 0 -> null, so a half-typed chip drops that filter.
function toNumber(raw: string, wholeOnly = false): number | null {
  const s = raw.replace(/[$,\s]/g, '')
  if (!(wholeOnly ? /^\d+$/ : /^\d+(\.\d+)?$/).test(s)) return null
  return Number(s)
}

function toFilters(parsed: ShopFilters, c: Chips): ShopFilters {
  return {
    category: parsed.category ?? null,
    budget_today: toNumber(c.budget),
    need_within_days: toNumber(c.days, true),
    max_width_in: toNumber(c.width),
    conditions: c.conditions,
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
}: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  prefix?: string
  suffix?: string
  inputMode: 'decimal' | 'numeric'
}) {
  return (
    <div className="flex min-h-11 items-center gap-1.5 rounded-full border border-emerald-300 bg-emerald-50 px-3 py-1 dark:border-emerald-800 dark:bg-emerald-950">
      <label htmlFor={id} className="text-sm font-medium text-emerald-900 dark:text-emerald-200">
        {label}
      </label>
      {prefix && <span aria-hidden="true" className="text-sm text-stone-600 dark:text-stone-400">{prefix}</span>}
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        inputMode={inputMode}
        autoComplete="off"
        placeholder="any"
        className="w-16 rounded border border-stone-300 bg-white px-1.5 py-0.5 text-base tabular-nums text-stone-900 focus:outline-2 focus:outline-offset-1 focus:outline-emerald-600 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-100"
      />
      {suffix && <span className="text-sm text-stone-600 dark:text-stone-400">{suffix}</span>}
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
        className="rounded-xl border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900/40"
      >
        <h3 id={headingId} className="text-base font-semibold">
          {place}. {modelLabel(offer.item_id)}
        </h3>
        <p className="text-sm text-stone-600 dark:text-stone-400">{path.name}</p>
        <dl className="mt-3 grid grid-cols-2 gap-3">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">Price</dt>
            <dd className="text-2xl font-bold tabular-nums">{money(offer.price)}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
              Cost per year
            </dt>
            <dd className="text-2xl font-bold tabular-nums">{range(path.cost_per_year_low, path.cost_per_year_high)}</dd>
          </div>
        </dl>
        {sentences.length > 0 && (
          <ul className="mt-3 space-y-1 text-sm text-stone-700 dark:text-stone-300">
            {sentences.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        )}
        {offer.url && (
          <a
            href={offer.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 inline-flex min-h-11 items-center rounded-lg border border-emerald-700 px-4 text-sm font-semibold text-emerald-800 hover:bg-emerald-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 dark:border-emerald-500 dark:text-emerald-300 dark:hover:bg-emerald-950"
          >
            View at retailer
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        )}
      </article>
    </li>
  )
}

const buttonClass =
  'min-h-12 w-full rounded-lg bg-emerald-700 px-4 py-3 text-base font-semibold text-white hover:bg-emerald-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 disabled:opacity-60'
const hintClass = 'text-sm text-stone-600 dark:text-stone-400'

type Status = 'idle' | 'loading' | 'done' | 'error'

export default function Shop() {
  const [text, setText] = useState('')
  const [parsed, setParsed] = useState<ShopFilters | null>(null)
  const [chips, setChips] = useState<Chips>(toChips({}))
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
      setParseStatus('done')
    } catch (err) {
      setFailure(message(err))
      setParseStatus('error')
    }
  }

  async function onRank() {
    if (parsed === null) return
    setRankStatus('loading')
    try {
      setOffers(await rankShopOffers({ filters: toFilters(parsed, chips) }))
      setRankStatus('done')
    } catch (err) {
      setFailure(message(err))
      setRankStatus('error')
    }
  }

  const setChip = (name: 'budget' | 'days' | 'width') => (v: string) => setChips((c) => ({ ...c, [name]: v }))
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
      <form noValidate onSubmit={onParse} className="space-y-3">
        <label htmlFor="shop-request" className="block text-base font-semibold">
          What are you looking for?
        </label>
        <p id="shop-request-hint" className={hintClass}>
          In your own words, for example: About $300, small space, need it this week.
        </p>
        <textarea
          id="shop-request"
          aria-describedby="shop-request-hint"
          rows={3}
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="block w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-base text-stone-900 focus:outline-2 focus:outline-offset-1 focus:outline-emerald-600 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-100"
        />
        <button type="submit" disabled={parseStatus === 'loading' || text.trim() === ''} className={buttonClass}>
          {parseStatus === 'loading' ? 'Reading your request...' : 'Read my request'}
        </button>
      </form>

      {parseStatus === 'error' && (
        <p role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          Could not read the request: {failure}
        </p>
      )}

      {parseStatus === 'done' && (
        <section aria-labelledby="filters-heading" className="space-y-3">
          <h2 id="filters-heading" className="text-lg font-semibold">
            What we read from it
          </h2>
          <p className={hintClass}>
            {nothingRead
              ? 'No filters were read from that. Set any you want below, or leave them blank to see every offer.'
              : 'Check these before ranking. Change any value, or clear it to drop that filter.'}
          </p>
          <div className="flex flex-wrap gap-2">
            <Chip id="chip-budget" label="Spend today up to" prefix="$" value={chips.budget} onChange={setChip('budget')} inputMode="decimal" />
            <Chip id="chip-days" label="Need it within" suffix="days" value={chips.days} onChange={setChip('days')} inputMode="numeric" />
            <Chip id="chip-width" label="Width up to" suffix="in" value={chips.width} onChange={setChip('width')} inputMode="decimal" />
          </div>
          <div role="group" aria-label="Condition" className="flex flex-wrap gap-2">
            {CONDITIONS.map((cond) => {
              const on = chips.conditions.includes(cond)
              return (
                <button
                  key={cond}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggle(cond)}
                  className={`min-h-11 rounded-full border px-4 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${
                    on
                      ? 'border-emerald-700 bg-emerald-700 text-white'
                      : 'border-stone-300 bg-white text-stone-800 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-200'
                  }`}
                >
                  {CONDITION_LABELS[cond]}
                </button>
              )
            })}
          </div>
          <p className={hintClass}>With no condition picked, new and used offers are both shown.</p>
          <button type="button" onClick={onRank} disabled={rankStatus === 'loading'} className={buttonClass}>
            {rankStatus === 'loading' ? 'Ranking offers...' : 'Rank offers by cost per year'}
          </button>
        </section>
      )}

      {rankStatus === 'error' && (
        <p role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          Could not rank offers: {failure}
        </p>
      )}

      {rankStatus === 'done' && (
        <section aria-labelledby="offers-heading">
          <h2 id="offers-heading" className="text-lg font-semibold">
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
