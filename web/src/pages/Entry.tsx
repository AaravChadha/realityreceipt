// Manual entry (PLAN.md tasks 2.8 and 2.8.1). Two optional sections, because the fridge
// you own and a used one you found are different units. No personal or income questions.
import { useReducedMotion } from 'framer-motion'
import { useEffect, useRef, useState, type FormEvent, type InputHTMLAttributes } from 'react'
import { checkItem, quote, sources } from '../api'
import { Receipt } from '../components/Receipt'
import { SourceSheet } from '../components/SourceSheet'
import type { CostLine, Item, Offer, Path, QuoteRequest, Source } from '../contracts'

const CATEGORY = 'refrigerator'

// The earliest manufacture year accepted, the same bound as task 1.6 puts on Item.mfg_year.
const FIRST_YEAR = 1940

type ListingCondition = 'used_as_is' | 'refurbished'

interface Fields {
  nowBrand: string
  nowModel: string
  nowSerial: string
  nowYear: string
  nowProductClass: string
  nowVolume: string
  nowKwh: string
  nowRepair: string
  usedBrand: string
  usedModel: string
  usedYear: string
  usedPrice: string
  usedCondition: ListingCondition
  usedWarranty: string
  budget: string
}

type FieldName = keyof Fields
type Errors = Partial<Record<FieldName, string>>

const EMPTY: Fields = {
  nowBrand: '',
  nowModel: '',
  nowSerial: '',
  nowYear: '',
  nowProductClass: '',
  nowVolume: '',
  nowKwh: '',
  nowRepair: '',
  usedBrand: '',
  usedModel: '',
  usedYear: '',
  usedPrice: '',
  usedCondition: 'used_as_is',
  usedWarranty: '',
  budget: '',
}

const NOW_FIELDS: FieldName[] = [
  'nowBrand',
  'nowModel',
  'nowSerial',
  'nowYear',
  'nowProductClass',
  'nowVolume',
  'nowKwh',
  'nowRepair',
]
const USED_FIELDS: FieldName[] = ['usedBrand', 'usedModel', 'usedYear', 'usedPrice', 'usedWarranty']

// '' -> null; '$1,200.50' -> 1200.5; anything that is not a number >= 0 -> NaN.
function parseAmount(raw: string, wholeOnly = false): number | null {
  const s = raw.replace(/[$,\s]/g, '')
  if (s === '') return null
  const ok = wholeOnly ? /^\d+$/.test(s) : /^\d+(\.\d+)?$/.test(s)
  return ok ? Number(s) : NaN
}

interface Draft {
  current: Item | null
  listing: { item: Item; price: number } | null
  repairQuote: number | null
  budget: number | null
}

// Turns the form into the units to check and quote, or field errors.
function readForm(f: Fields): { draft: Draft; errors: Errors } {
  const errors: Errors = {}
  const filled = (names: FieldName[]) => names.some((n) => String(f[n]).trim() !== '')
  const amount = (name: FieldName, message: string, wholeOnly = false) => {
    const n = parseAmount(String(f[name]), wholeOnly)
    if (Number.isNaN(n)) errors[name] = message
    return n
  }
  const need = (name: FieldName, message: string) => {
    if (String(f[name]).trim() === '') errors[name] = message
  }
  // '' -> null; four digits from FIRST_YEAR to this year -> the year; anything else is an error.
  const year = (name: FieldName) => {
    const s = String(f[name]).trim()
    if (s === '') return null
    const thisYear = new Date().getFullYear()
    const n = /^\d{4}$/.test(s) ? Number(s) : NaN
    if (n >= FIRST_YEAR && n <= thisYear) return n
    errors[name] = `Enter the year as four digits, from ${FIRST_YEAR} to ${thisYear}.`
    return null
  }

  let current: Item | null = null
  const repairQuote = amount('nowRepair', 'Enter the repair quote as a dollar amount.')
  if (filled(NOW_FIELDS)) {
    need('nowBrand', 'Enter the brand of your fridge.')
    need('nowModel', 'Enter the model number of your fridge.')
    const volume = amount('nowVolume', 'Enter the volume as a number, for example 18.2.')
    const kwhMessage = 'Enter the kWh per year as a number above 0, for example 586.'
    const kwh = amount('nowKwh', kwhMessage)
    if (kwh === 0) errors.nowKwh = kwhMessage
    const attributes: Record<string, string | number> = {}
    if (f.nowProductClass.trim()) attributes.product_class = f.nowProductClass.trim()
    if (volume !== null && !Number.isNaN(volume)) attributes.volume_cuft = volume
    // Pinned key (PLAN.md "Fixed interfaces"): the kWh printed on this unit's own EnergyGuide label.
    if (kwh !== null && !Number.isNaN(kwh)) attributes.label_kwh_per_year = kwh
    current = {
      id: 'current',
      category: CATEGORY,
      brand: f.nowBrand.trim(),
      model: f.nowModel.trim(),
      serial: f.nowSerial.trim() || null,
      mfg_year: year('nowYear'),
      condition: 'used_as_is',
      attributes,
    }
  }

  let listing: Draft['listing'] = null
  if (filled(USED_FIELDS)) {
    need('usedBrand', 'Enter the brand of the one you found.')
    need('usedModel', 'Enter the model number of the one you found.')
    const price = amount('usedPrice', 'Enter the listing price as a dollar amount.')
    if (price === null) errors.usedPrice = 'Enter the listing price.'
    const refurbished = f.usedCondition === 'refurbished'
    const warranty = refurbished ? amount('usedWarranty', 'Enter the warranty as a whole number of months.', true) : null
    listing = {
      item: {
        id: 'listing',
        category: CATEGORY,
        brand: f.usedBrand.trim(),
        model: f.usedModel.trim(),
        mfg_year: year('usedYear'),
        condition: f.usedCondition,
        warranty_months: warranty,
      },
      price: price ?? 0,
    }
  }

  const budget = amount('budget', 'Enter the amount as a dollar figure.')
  return { draft: { current, listing, repairQuote, budget }, errors }
}

// Each unit goes through /item first, so a typed unit is checked the same way as a
// scanned one, then everything goes to /quote.
async function quoteDraft(draft: Draft): Promise<Path[]> {
  const [current, listingItem] = await Promise.all([
    draft.current ? checkItem(draft.current) : null,
    draft.listing ? checkItem(draft.listing.item) : null,
  ])
  const offers: Offer[] =
    listingItem && draft.listing
      ? [
          {
            item_id: listingItem.id,
            price: draft.listing.price,
            seller_type: listingItem.condition === 'refurbished' ? 'refurbisher' : 'private',
            source: 'user_listing',
            source_id: 'user_listing',
          },
        ]
      : []
  const req: QuoteRequest = {
    current,
    items: listingItem ? [listingItem] : [],
    offers,
    repair_quote_low: current ? draft.repairQuote : null,
    repair_quote_high: current ? draft.repairQuote : null,
    budget_today: draft.budget,
  }
  return quote(req)
}

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  id: string
  label: string
  hint?: string
  error?: string
  prefix?: string
}

function Field({ id, label, hint, error, prefix, ...input }: FieldProps) {
  const describedBy = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(' ') || undefined
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      {hint && (
        <p id={`${id}-hint`} className="mt-0.5 text-sm text-stone-600 dark:text-stone-400">
          {hint}
        </p>
      )}
      <div className="relative mt-1">
        {prefix && (
          <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-stone-500">
            {prefix}
          </span>
        )}
        <input
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={`block min-h-11 w-full rounded-lg border bg-white py-2 pr-3 text-base text-stone-900 focus:outline-2 focus:outline-offset-1 focus:outline-emerald-600 dark:bg-stone-900 dark:text-stone-100 ${
            prefix ? 'pl-7' : 'pl-3'
          } ${error ? 'border-red-600 dark:border-red-400' : 'border-stone-300 dark:border-stone-700'}`}
          {...input}
        />
      </div>
      {error && (
        <p id={`${id}-error`} className="mt-1 text-sm text-red-700 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  )
}

const fieldsetClass = 'space-y-4 rounded-xl border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900/40'
const legendClass = 'px-1 text-base font-semibold'
const sectionHintClass = 'text-sm text-stone-600 dark:text-stone-400'

export default function Entry() {
  const [fields, setFields] = useState<Fields>(EMPTY)
  const [errors, setErrors] = useState<Errors>({})
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [paths, setPaths] = useState<Path[]>([])
  const [failure, setFailure] = useState('')
  const [openLine, setOpenLine] = useState<CostLine | null>(null)
  const [sourceList, setSourceList] = useState<Source[]>([])
  const sourcesAsked = useRef(false)
  const results = useRef<HTMLDivElement>(null)
  const reduceMotion = useReducedMotion()

  // Every receipt shares one source list: ask for it once, after the first receipt, and
  // again after a later one only if that ask failed. Until it arrives, the sheet says
  // the source details are not available.
  function loadSources() {
    if (sourcesAsked.current) return
    sourcesAsked.current = true
    sources().then(setSourceList, () => {
      sourcesAsked.current = false
    })
  }

  // After a quote, bring the results into view and move focus there, so keyboard and
  // screen reader users start at the receipt instead of the submit button.
  useEffect(() => {
    if (status !== 'done' || results.current === null) return
    results.current.focus({ preventScroll: true })
    results.current.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
  }, [status, reduceMotion])

  const set = (name: FieldName) => (e: { target: { value: string } }) =>
    setFields((prev) => ({ ...prev, [name]: e.target.value }))

  const text = (name: FieldName) => ({
    value: String(fields[name]),
    onChange: set(name),
    error: errors[name],
  })
  const typed = { autoComplete: 'off', autoCapitalize: 'characters', spellCheck: false }
  const decimal = { inputMode: 'decimal' as const, autoComplete: 'off' }
  const wholeNumber = { inputMode: 'numeric' as const, autoComplete: 'off' }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const { draft, errors: found } = readForm(fields)
    setErrors(found)
    if (Object.keys(found).length > 0) {
      setStatus((s) => (s === 'error' ? 'idle' : s))
      return
    }
    setStatus('loading')
    try {
      setPaths(await quoteDraft(draft))
      setStatus('done')
      loadSources()
    } catch (err) {
      setFailure(err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }

  const errorCount = Object.keys(errors).length

  return (
    <div className="space-y-6">
      <form noValidate onSubmit={onSubmit} className="space-y-5">
        <fieldset className={fieldsetClass}>
          <legend className={legendClass}>Your fridge now</legend>
          <p className={sectionHintClass}>Optional. Fill this in to see what repairing the one you have would cost.</p>
          <Field id="now-brand" label="Brand" {...text('nowBrand')} autoComplete="off" />
          <Field id="now-model" label="Model number" {...text('nowModel')} {...typed} />
          <Field id="now-serial" label="Serial number (optional)" {...text('nowSerial')} {...typed} />
          <Field id="now-year" label="Year made (optional)" {...text('nowYear')} {...wholeNumber} />
          <Field
            id="now-product-class"
            label="Product class (optional)"
            hint="As printed on the yellow energy label."
            {...text('nowProductClass')}
            autoComplete="off"
          />
          <Field id="now-volume" label="Volume in cubic feet (optional)" {...text('nowVolume')} {...decimal} />
          <Field id="now-kwh" label="kWh per year on the yellow label (optional)" {...text('nowKwh')} {...decimal} />
          <Field id="now-repair" label="Repair quote (optional)" prefix="$" {...text('nowRepair')} {...decimal} />
        </fieldset>

        <fieldset className={fieldsetClass}>
          <legend className={legendClass}>A used one you found</legend>
          <p className={sectionHintClass}>Optional. From a listing, a yard sale or a refurbisher.</p>
          <Field id="used-brand" label="Brand" {...text('usedBrand')} autoComplete="off" />
          <Field id="used-model" label="Model number" {...text('usedModel')} {...typed} />
          <Field id="used-year" label="Year made (optional)" {...text('usedYear')} {...wholeNumber} />
          <Field id="used-price" label="Listing price" prefix="$" {...text('usedPrice')} {...decimal} />
          <div>
            <label htmlFor="used-condition" className="block text-sm font-medium">
              Condition
            </label>
            <select
              id="used-condition"
              value={fields.usedCondition}
              onChange={set('usedCondition')}
              className="mt-1 block min-h-11 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-base text-stone-900 focus:outline-2 focus:outline-offset-1 focus:outline-emerald-600 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-100"
            >
              <option value="used_as_is">Used, as-is</option>
              <option value="refurbished">Refurbished</option>
            </select>
          </div>
          {fields.usedCondition === 'refurbished' && (
            <Field
              id="used-warranty"
              label="Warranty in months (optional)"
              {...text('usedWarranty')}
              inputMode="numeric"
              autoComplete="off"
            />
          )}
        </fieldset>

        <Field id="budget" label="I can spend up to this much today (optional)" prefix="$" {...text('budget')} {...decimal} />

        {errorCount > 0 && (
          <p role="alert" className="text-sm font-medium text-red-700 dark:text-red-400">
            {errorCount === 1 ? 'One field needs a fix.' : `${errorCount} fields need a fix.`}
          </p>
        )}

        <button
          type="submit"
          disabled={status === 'loading'}
          className="min-h-12 w-full rounded-lg bg-emerald-700 px-4 py-3 text-base font-semibold text-white hover:bg-emerald-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 disabled:opacity-60"
        >
          {status === 'loading' ? 'Working it out...' : 'Show every way to get it'}
        </button>
      </form>

      {status === 'error' && (
        <p role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          Could not get a receipt: {failure}
        </p>
      )}

      {status === 'done' && (
        <div ref={results} tabIndex={-1} className="scroll-mt-4 outline-none">
          {paths.length === 0 ? (
            <p className={sectionHintClass}>No paths came back for these details.</p>
          ) : (
            <Receipt paths={paths} onLineTap={setOpenLine} />
          )}
        </div>
      )}

      {openLine && <SourceSheet line={openLine} sources={sourceList} onClose={() => setOpenLine(null)} />}
    </div>
  )
}
