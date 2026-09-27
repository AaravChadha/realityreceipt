// Manual entry (PLAN.md tasks 2.8 and 2.8.1) plus scan, upload and lease correction (task 3.10).
// Two optional unit sections, because the fridge you own and a used one you found are
// different units. A scan pre-fills those same fields; the user confirms before quoting.
// No personal or income questions.
import { useReducedMotion } from 'framer-motion'
import {
  Camera,
  CircleAlert,
  CircleCheck,
  FileText,
  LoaderCircle,
  ReceiptText,
  Refrigerator,
  Tag,
  TriangleAlert,
  Upload,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useRef, useState, type ChangeEvent, type FormEvent, type InputHTMLAttributes, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { checkItem, quote, scan, sources } from '../api'
import { Receipt } from '../components/Receipt'
import { SourceSheet } from '../components/SourceSheet'
import type {
  CostLine,
  EarlyPurchaseRule,
  Item,
  Lease,
  Offer,
  Path,
  QuoteRequest,
  ScanKind,
  ScanResult,
  Source,
} from '../contracts'

const CATEGORY = 'refrigerator'

// The earliest manufacture year accepted, the same bound as task 1.6 puts on Item.mfg_year.
const FIRST_YEAR = 1940

type ListingCondition = 'new' | 'used_as_is' | 'refurbished'

// Price tag is out of the picker tonight: a scanned tag is not what the quote prices (PLAN.md 3.10).
const SCAN_KIND_OPTIONS: { value: ScanKind; label: string }[] = [
  { value: 'label', label: 'Label' },
  { value: 'lease', label: 'Lease' },
  { value: 'listing', label: 'Listing' },
]

const EARLY_PURCHASE_OPTIONS: { value: EarlyPurchaseRule; label: string }[] = [
  { value: 'none', label: 'No early purchase' },
  { value: 'pct_of_remaining', label: 'A share of the remaining payments' },
  { value: 'cash_price_minus_pct_paid', label: 'Cash price minus a share already paid' },
]

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
  leaseBrand: string
  leaseModel: string
  leaseWeekly: string
  leaseTerm: string
  leaseCash: string
  leaseFees: string
  leaseRule: EarlyPurchaseRule
  leasePct: string
  leaseEarlyText: string
  leaseMissed: string
  leasePaid: string
  leaseTotal: string
  budget: string
}

type FieldName = keyof Fields
type Errors = Partial<Record<FieldName, string>>
// usedCondition and leaseRule are selects, so a scanned string cannot be written there.
type TextField = Exclude<FieldName, 'usedCondition' | 'leaseRule'>

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
  leaseBrand: '',
  leaseModel: '',
  leaseWeekly: '',
  leaseTerm: '',
  leaseCash: '',
  leaseFees: '',
  leaseRule: 'none',
  leasePct: '',
  leaseEarlyText: '',
  leaseMissed: '',
  leasePaid: '',
  leaseTotal: '',
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
const LEASE_TOUCHED: FieldName[] = [
  'leaseBrand',
  'leaseModel',
  'leaseWeekly',
  'leaseTerm',
  'leaseCash',
  'leaseFees',
  'leasePct',
  'leaseEarlyText',
  'leaseMissed',
  'leasePaid',
  'leaseTotal',
]

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
  lease: Lease | null
  leased: Item | null
}

// A value is present when the scan returned that key and it is not null. Null means it was not printed.
function presentText(raw: ScanResult['fields'], key: string): string | undefined {
  if (!Object.prototype.hasOwnProperty.call(raw, key)) return undefined
  const value = raw[key]
  if (value === null || value === undefined) return undefined
  return String(value)
}

// A percent printed on the lease (50, or 33.3) becomes the fraction the quote stores.
function percentFraction(raw: string): string | undefined {
  const n = Number(raw)
  if (!Number.isFinite(n)) return undefined
  return (n / 100).toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
}

// A scan, valid or not, fills the same fields the user can type from ScanResult.fields.
// item, offer and lease are null whenever the scan is invalid, so they are not read.
// The kind's own fields are cleared first, so a value the new image did not read does not stay.
function applyScan(fields: Fields, result: ScanResult): Fields {
  const next = { ...fields }
  const raw = result.fields ?? {}
  const put = (name: TextField, key: string) => {
    const value = presentText(raw, key)
    if (value !== undefined) next[name] = value
  }
  const clear = (names: TextField[]) => {
    for (const name of names) next[name] = ''
  }

  if (result.kind === 'label') {
    clear(['nowBrand', 'nowModel', 'nowSerial', 'nowYear', 'nowProductClass', 'nowVolume', 'nowKwh'])
    put('nowBrand', 'brand')
    put('nowModel', 'model')
    put('nowSerial', 'serial')
    put('nowYear', 'mfg_year')
    put('nowProductClass', 'product_class')
    put('nowVolume', 'volume_cuft')
    put('nowKwh', 'label_kwh_per_year')
    // A label for a different fridge replaces the one the repair quote was for (task 3.10.1).
    const same = (a: string, b: string) => a.trim().toUpperCase() === b.trim().toUpperCase()
    const replaced = (['nowBrand', 'nowModel'] as const).some((name) => fields[name].trim() !== '' && !same(fields[name], next[name]))
    if (replaced) next.nowRepair = ''
  }

  if (result.kind === 'listing') {
    clear(['usedBrand', 'usedModel', 'usedYear', 'usedPrice', 'usedWarranty'])
    next.usedCondition = 'used_as_is'
    put('usedBrand', 'brand')
    put('usedModel', 'model')
    put('usedYear', 'mfg_year')
    put('usedPrice', 'price')
    const condition = presentText(raw, 'condition')
    if (condition === 'new' || condition === 'used_as_is' || condition === 'refurbished') next.usedCondition = condition
  }

  if (result.kind === 'lease') {
    clear([
      'leaseBrand',
      'leaseModel',
      'leaseWeekly',
      'leaseTerm',
      'leaseCash',
      'leaseFees',
      'leasePct',
      'leaseEarlyText',
      'leaseMissed',
      'leasePaid',
      'leaseTotal',
    ])
    next.leaseRule = 'none'
    put('leaseBrand', 'brand')
    put('leaseModel', 'model')
    put('leaseWeekly', 'weekly_payment')
    put('leaseTerm', 'term_weeks')
    put('leaseCash', 'cash_price')
    // A missing fee, or one the scan marks not printed, stays blank. 0 is a real entry.
    const feeRaw = presentText(raw, 'fees')
    if (feeRaw !== undefined && feeRaw.trim().toLowerCase() !== 'not printed') {
      const fee = Number(feeRaw.replace(/[$,\s]/g, ''))
      if (Number.isFinite(fee)) next.leaseFees = String(fee)
    }
    put('leaseEarlyText', 'early_purchase_text')
    put('leaseMissed', 'missed_payment_rule')
    put('leasePaid', 'payment_today')
    put('leaseTotal', 'total_of_payments')
    const rule = presentText(raw, 'early_purchase_rule')
    if (rule === 'none' || rule === 'pct_of_remaining' || rule === 'cash_price_minus_pct_paid') next.leaseRule = rule
    const percent = presentText(raw, 'early_purchase_percent')
    if (percent !== undefined) {
      const fraction = percentFraction(percent)
      if (fraction !== undefined) next.leasePct = fraction
    }
  }
  return next
}

// A 422 can carry several messages joined by "; ", and FastAPI starts a model check's message
// with "Value error, ", which is dropped so the user reads only the message (task 3.10.1).
function apiMessages(text: string): string[] {
  return text
    .split('; ')
    .map((m) => m.trim().replace(/^Value error, /, ''))
    .filter(Boolean)
}

function asSentence(message: string): string {
  const s = message.charAt(0).toUpperCase() + message.slice(1)
  return /[.!?]$/.test(s) ? s : `${s}.`
}

function scanMessages(result: ScanResult): string[] {
  const messages = (result.errors ?? []).map((err) => err.trim()).filter(Boolean)
  if (!result.valid && messages.length === 0) return ['The scan could not read this image.']
  return messages
}

function leaseStarted(f: Fields): boolean {
  return LEASE_TOUCHED.some((name) => f[name].trim() !== '') || f.leaseRule !== 'none'
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

  let lease: Lease | null = null
  let leased: Item | null = null
  if (leaseStarted(f)) {
    const leaseBrand = f.leaseBrand.trim()
    const leaseModel = f.leaseModel.trim()
    need('leaseBrand', 'Enter the brand of the leased fridge.')
    need('leaseModel', 'Enter the model number of the leased fridge.')
    need('leaseWeekly', 'Enter the weekly payment.')
    need('leaseTerm', 'Enter the term in weeks.')
    need('leaseCash', 'Enter the cash price.')
    need('leaseFees', 'Enter the fees as a dollar amount, or 0 if there is none.')
    const weekly = amount('leaseWeekly', 'Enter the weekly payment as a dollar amount.')
    const term = amount('leaseTerm', 'Enter the term as a whole number of weeks.', true)
    const cash = amount('leaseCash', 'Enter the cash price as a dollar amount.')
    const fees = amount('leaseFees', 'Enter the fees as a dollar amount.')
    if (weekly !== null && !Number.isNaN(weekly) && weekly <= 0) errors.leaseWeekly = 'Enter a weekly payment above $0.'
    if (term !== null && !Number.isNaN(term) && (term <= 0 || term > 260)) {
      errors.leaseTerm = 'Enter the term as a whole number of weeks, up to 260.'
    }
    let pct: number | null = null
    if (f.leaseRule === 'none') {
      if (f.leasePct.trim() !== '') errors.leasePct = 'Clear the early purchase fraction when there is no early purchase rule.'
    } else {
      need('leasePct', 'Enter the early purchase fraction.')
      pct = amount('leasePct', 'Enter the early purchase fraction as a number from 0 to 1.')
      if (pct !== null && !Number.isNaN(pct) && (pct < 0 || pct > 1)) {
        errors.leasePct = 'Enter the early purchase fraction as a number from 0 to 1.'
      }
    }
    const paid = amount('leasePaid', 'Enter paid today as a dollar amount.')
    const total = amount('leaseTotal', 'Enter the total of all payments as a dollar amount.')
    const leaseErrors = LEASE_TOUCHED.some((name) => errors[name]) || errors.leaseRule
    if (!leaseErrors && weekly !== null && term !== null && cash !== null && fees !== null && !Number.isNaN(fees)) {
      lease = {
        weekly_payment: weekly,
        term_weeks: term,
        cash_price: cash,
        fees,
        early_purchase_rule: f.leaseRule,
        early_purchase_pct: f.leaseRule === 'none' ? null : pct,
        early_purchase_text: f.leaseEarlyText.trim(),
        missed_payment_rule: f.leaseMissed.trim(),
        source_id: 'user_lease',
      }
      if (paid !== null && !Number.isNaN(paid)) lease.payment_today = paid
      if (total !== null && !Number.isNaN(total)) lease.total_of_payments = total
      if (leaseBrand && leaseModel) {
        leased = {
          id: 'lease',
          category: CATEGORY,
          brand: leaseBrand,
          model: leaseModel,
          condition: 'new',
        }
      }
    }
  }

  const budget = amount('budget', 'Enter the amount as a dollar figure.')
  return { draft: { current, listing, repairQuote, budget, lease, leased }, errors }
}

// Each unit goes through /item first, so a typed unit is checked the same way as a
// scanned one, then everything goes to /quote.
async function quoteDraft(draft: Draft): Promise<Path[]> {
  const [current, listingItem, leasedItem] = await Promise.all([
    draft.current ? checkItem(draft.current) : null,
    draft.listing ? checkItem(draft.listing.item) : null,
    draft.leased ? checkItem(draft.leased) : null,
  ])
  const offers: Offer[] = []
  if (listingItem && draft.listing) {
    offers.push({
      item_id: listingItem.id,
      price: draft.listing.price,
      seller_type: listingItem.condition === 'refurbished' ? 'refurbisher' : 'private',
      source: 'user_listing',
      source_id: 'user_listing',
    })
  }
  // The leased fridge rides with the lease so the quote can attach its electricity.
  if (leasedItem && draft.lease) {
    offers.push({
      item_id: leasedItem.id,
      price: draft.lease.cash_price,
      seller_type: 'rent_to_own',
      source: 'user_listing',
      source_id: 'user_listing',
    })
  }
  const items = [listingItem, leasedItem].filter((item): item is Item => item !== null)
  const req: QuoteRequest = {
    current,
    items,
    offers,
    repair_quote_low: current ? draft.repairQuote : null,
    repair_quote_high: current ? draft.repairQuote : null,
    budget_today: draft.budget,
  }
  if (draft.lease) req.lease = draft.lease
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
      <Label htmlFor={id}>{label}</Label>
      {hint && (
        <p id={`${id}-hint`} className="mt-0.5 text-sm text-muted-foreground">
          {hint}
        </p>
      )}
      <div className="relative mt-1">
        {prefix && (
          <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 left-3 flex items-center font-mono text-muted-foreground">
            {prefix}
          </span>
        )}
        <Input
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={prefix ? 'pl-7' : undefined}
          {...input}
        />
      </div>
      {error && (
        <p id={`${id}-error`} className="mt-1 flex items-start gap-1 text-sm text-destructive">
          <CircleAlert aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          {error}
        </p>
      )}
    </div>
  )
}

// One optional part of the form: a card whose legend names the group for screen readers.
function Section({ title, hint, icon: Icon, children }: { title: string; hint: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <fieldset className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <legend className="float-left flex w-full items-center gap-2.5 text-base font-semibold">
        <span aria-hidden="true" className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
          <Icon className="size-4" />
        </span>
        {title}
      </legend>
      <div className="clear-both space-y-4 pt-2">
        <p className={sectionHintClass}>{hint}</p>
        {children}
      </div>
    </fieldset>
  )
}

const sectionHintClass = 'text-sm text-muted-foreground'
const alertClass = 'flex items-start gap-2 rounded-xl border p-3 text-sm'
const failureClass = `${alertClass} border-destructive/30 bg-destructive/10 text-destructive`
const warningClass = `${alertClass} border-amber-300 bg-amber-50 text-amber-950 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100`

export default function Entry() {
  const [fields, setFields] = useState<Fields>(EMPTY)
  const [errors, setErrors] = useState<Errors>({})
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [paths, setPaths] = useState<Path[]>([])
  const [budgetToday, setBudgetToday] = useState<number | null>(null)
  const [failure, setFailure] = useState('')
  const [kind, setKind] = useState<ScanKind>('label')
  const [scanStatus, setScanStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [scanErrors, setScanErrors] = useState<string[]>([])
  const [scanFailure, setScanFailure] = useState('')
  const [scanned, setScanned] = useState(false)
  const scanInput = useRef<HTMLInputElement>(null)
  const uploadInput = useRef<HTMLInputElement>(null)
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

  function onPicked(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (file) void onScan(file)
  }

  async function onScan(file: File) {
    setScanStatus('loading')
    setScanFailure('')
    setScanErrors([])
    try {
      const result = await scan(kind, file)
      setFields((prev) => applyScan(prev, result))
      setErrors({})
      setScanErrors(scanMessages(result))
      setScanned(true)
      setPaths([])
      setStatus('idle')
      setScanStatus('idle')
    } catch (err) {
      setScanFailure(err instanceof Error ? err.message : String(err))
      setScanStatus('error')
    }
  }

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
      setBudgetToday(draft.budget)
      setStatus('done')
      loadSources()
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err)
      const messages = apiMessages(text)
      // A printed payment today that does not fit the lease's total is fixed in the form, so it
      // shows beside "Paid today" (task 3.10.1); anything else stays in the alert below.
      const notFit = messages.find((m) => m.includes('does not fit'))
      const rest = messages.filter((m) => m !== notFit)
      if (notFit !== undefined) setErrors({ leasePaid: asSentence(notFit) })
      if (notFit === undefined || rest.length > 0) {
        setFailure(rest.join('; ') || text)
        setStatus('error')
      } else {
        setStatus('idle')
      }
    }
  }

  const errorCount = Object.keys(errors).length

  return (
    <div className="space-y-6 lg:grid lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] lg:items-start lg:gap-8 lg:space-y-0">
      <form noValidate onSubmit={onSubmit} className="space-y-5">
        <Section title="Scan or upload" icon={Camera} hint="A photo of a label, lease or listing. Correct anything it reads before the quote.">
          <div>
            <Label htmlFor="scan-kind">What are you scanning?</Label>
            <NativeSelect id="scan-kind" value={kind} onChange={(e) => setKind(e.target.value as ScanKind)}>
              {SCAN_KIND_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Button type="button" size="lg" disabled={scanStatus === 'loading'} onClick={() => scanInput.current?.click()}>
              <Camera aria-hidden="true" />
              Scan
            </Button>
            <Button
              type="button"
              size="lg"
              variant="outline"
              className="px-3 whitespace-normal"
              disabled={scanStatus === 'loading'}
              onClick={() => uploadInput.current?.click()}
            >
              <Upload aria-hidden="true" />
              Upload saved image
            </Button>
          </div>
          <input
            ref={scanInput}
            type="file"
            accept="image/*"
            capture="environment"
            tabIndex={-1}
            aria-hidden="true"
            className="sr-only"
            onChange={onPicked}
          />
          <input
            ref={uploadInput}
            type="file"
            accept="image/*"
            tabIndex={-1}
            aria-hidden="true"
            className="sr-only"
            onChange={onPicked}
          />
          {scanStatus === 'loading' && (
            <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
              <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
              Reading the image...
            </p>
          )}
          {scanStatus === 'error' && (
            <p role="alert" className={failureClass}>
              <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              <span>Could not read the image: {scanFailure}</span>
            </p>
          )}
          {scanErrors.length > 0 && (
            <div role="alert" className={warningClass}>
              <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              <div>
                <p className="font-medium">The scan needs a correction.</p>
                <ul className="mt-1 list-disc pl-5">
                  {scanErrors.map((err, i) => (
                    <li key={`${err}-${i}`}>{err}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
          {scanned && scanStatus === 'idle' && (
            <p className="flex items-center gap-2 text-sm font-medium text-primary">
              <CircleCheck aria-hidden="true" className="size-4 shrink-0" />
              Correct anything that looks wrong, then show every way to get it.
            </p>
          )}
        </Section>

        <Section title="Your fridge now" icon={Refrigerator} hint="Optional. Fill this in to see what repairing the one you have would cost.">
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
        </Section>

        <Section title="A used one you found" icon={Tag} hint="Optional. From a listing, a yard sale or a refurbisher.">
          <Field id="used-brand" label="Brand" {...text('usedBrand')} autoComplete="off" />
          <Field id="used-model" label="Model number" {...text('usedModel')} {...typed} />
          <Field id="used-year" label="Year made (optional)" {...text('usedYear')} {...wholeNumber} />
          <Field id="used-price" label="Listing price" prefix="$" {...text('usedPrice')} {...decimal} />
          <div>
            <Label htmlFor="used-condition">Condition</Label>
            <NativeSelect id="used-condition" value={fields.usedCondition} onChange={set('usedCondition')}>
              <option value="new">New</option>
              <option value="used_as_is">Used, as-is</option>
              <option value="refurbished">Refurbished</option>
            </NativeSelect>
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
        </Section>

        <Section title="A rent-to-own lease" icon={FileText} hint="Optional. The fridge on the lease, and every term. You confirm these details before any quote.">
          <Field id="lease-brand" label="Brand" {...text('leaseBrand')} autoComplete="off" />
          <Field id="lease-model" label="Model number" {...text('leaseModel')} {...typed} />
          <Field id="lease-weekly" label="Weekly payment" prefix="$" {...text('leaseWeekly')} {...decimal} />
          <Field id="lease-term" label="Term in weeks" {...text('leaseTerm')} inputMode="numeric" autoComplete="off" />
          <Field id="lease-cash" label="Cash price" prefix="$" {...text('leaseCash')} {...decimal} />
          <Field id="lease-fees" label="Fees ($0 if none)" prefix="$" {...text('leaseFees')} {...decimal} />
          <Field id="lease-paid" label="Paid today" prefix="$" {...text('leasePaid')} {...decimal} />
          <Field id="lease-total" label="Total of all payments, as printed" prefix="$" {...text('leaseTotal')} {...decimal} />
          <div>
            <Label htmlFor="lease-rule">Early purchase rule</Label>
            <NativeSelect id="lease-rule" value={fields.leaseRule} onChange={set('leaseRule')}>
              {EARLY_PURCHASE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </NativeSelect>
          </div>
          <Field
            id="lease-pct"
            label="Early purchase fraction"
            hint="A number from 0 to 1. For example, 0.5 is half. Leave this blank when there is no early purchase rule."
            {...text('leasePct')}
            {...decimal}
          />
          <Field id="lease-early-text" label="Early purchase terms" {...text('leaseEarlyText')} autoComplete="off" />
          <Field id="lease-missed" label="Missed payment rule" {...text('leaseMissed')} autoComplete="off" />
        </Section>

        <Card className="p-4">
          <Field id="budget" label="I can spend up to this much today (optional)" prefix="$" {...text('budget')} {...decimal} />
        </Card>

        {errorCount > 0 && (
          <p role="alert" className="flex items-center gap-1.5 text-sm font-medium text-destructive">
            <CircleAlert aria-hidden="true" className="size-4 shrink-0" />
            {errorCount === 1 ? 'One field needs a fix.' : `${errorCount} fields need a fix.`}
          </p>
        )}

        <Button type="submit" size="lg" className="w-full shadow-md" disabled={status === 'loading' || scanStatus === 'loading'}>
          {status === 'loading' ? <LoaderCircle aria-hidden="true" className="animate-spin" /> : <ReceiptText aria-hidden="true" />}
          {status === 'loading' ? 'Working it out...' : 'Show every way to get it'}
        </Button>
      </form>

      <div className="space-y-6">
        {status === 'error' && (
          <p role="alert" className={failureClass}>
            <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span>Could not get a receipt: {failure}</span>
          </p>
        )}

        {status === 'done' && (
          <div ref={results} tabIndex={-1} className="scroll-mt-4 outline-none">
            {paths.length === 0 ? (
              <p className={sectionHintClass}>No paths came back for these details.</p>
            ) : (
              <Receipt paths={paths} onLineTap={setOpenLine} budgetToday={budgetToday} />
            )}
          </div>
        )}

        {/* Wide screens only: the receipt's place is held open beside the form until it prints. */}
        {status !== 'done' && (
          <div
            aria-hidden="true"
            className="hidden flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-border p-10 text-center text-muted-foreground lg:flex"
          >
            <ReceiptText className="size-10" />
            <p className="font-mono text-xs tracking-widest uppercase">Your receipt prints here</p>
          </div>
        )}
      </div>

      {openLine && <SourceSheet line={openLine} sources={sourceList} onClose={() => setOpenLine(null)} />}
    </div>
  )
}
