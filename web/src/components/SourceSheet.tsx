import { motion, useReducedMotion } from 'framer-motion'
import { useEffect, useId, useRef, type KeyboardEvent } from 'react'
import type { CostLine, Source } from '../contracts'
import { PERIOD_SUFFIX, SOURCE_LABELS, rangeNote } from '../format'

// Semantic roles over Tailwind's stone and blue palettes. The project has no token file
// yet, so the sheet's markup uses only these names, never a colour of its own.
const ui = {
  surface: 'bg-white dark:bg-stone-900',
  text: 'text-stone-900 dark:text-stone-50',
  muted: 'text-stone-600 dark:text-stone-300',
  border: 'border-stone-200 dark:border-stone-700',
  divider: 'divide-stone-200 dark:divide-stone-700',
  link: 'text-blue-700 underline underline-offset-2 hover:text-blue-900 dark:text-blue-300 dark:hover:text-blue-200',
  focus:
    'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:focus-visible:outline-blue-300',
}

// Reserved source ids (PLAN.md "Fixed interfaces"): never in GET /sources.
const RESERVED_SOURCES: Record<string, string> = {
  user: 'You entered this',
  user_listing: 'From the listing you entered',
  user_lease: 'From your lease',
}

// The sheet is the detail view, so it shows cents; the receipt card rounds to whole
// dollars with format.ts's `money`. Labels, suffixes and range notes come from format.ts.
const cents = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
const day = new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeZone: 'UTC' })

function amountText(line: CostLine): { text: string; note: string | null } {
  const { amount_low: low, amount_high: high } = line
  const per = PERIOD_SUFFIX[line.period]
  const note = rangeNote(low, high)
  if (line.source_type === 'not_estimated') return { text: 'Not estimated', note: null }
  if (low !== null && high !== null) {
    return { text: low === high ? `${cents.format(low)}${per}` : `${cents.format(low)} to ${cents.format(high)}${per}`, note }
  }
  if (low !== null) return { text: `${cents.format(low)} or more${per}`, note }
  if (high !== null) return { text: `up to ${cents.format(high)}${per}`, note }
  return { text: 'Not estimated', note: null }
}

function retrieved(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00Z`)
  return Number.isNaN(date.getTime()) ? isoDate : day.format(date)
}

function isWebUrl(url: string): boolean {
  try {
    return ['http:', 'https:'].includes(new URL(url).protocol)
  } catch {
    return false
  }
}

function SourceEntry({ id, source }: { id: string; source: Source | undefined }) {
  if (Object.hasOwn(RESERVED_SOURCES, id)) {
    return <li className="wrap-break-word">{RESERVED_SOURCES[id]}</li>
  }
  if (source === undefined) {
    return (
      <li>
        <p>Source details are not available right now.</p>
        <p className={`text-sm break-all ${ui.muted}`}>Reference: {id}</p>
      </li>
    )
  }
  return (
    <li>
      <p className="font-medium wrap-break-word">{source.title}</p>
      <p className={`text-sm wrap-break-word ${ui.muted}`}>{source.publisher}</p>
      <p className={`text-sm ${ui.muted}`}>Retrieved {retrieved(source.retrieved_date)}</p>
      {isWebUrl(source.url) ? (
        <a
          href={source.url}
          target="_blank"
          rel="noreferrer"
          className={`inline-flex min-h-11 items-center text-sm break-all ${ui.link} ${ui.focus}`}
        >
          {source.url}{' '}
          <span className="sr-only">(opens in a new tab)</span>
        </a>
      ) : (
        <p className={`text-sm break-all ${ui.muted}`}>{source.url}</p>
      )}
    </li>
  )
}

/**
 * The detail view for one cost line: its amount, formula, source label and sources.
 * Render it when a line is tapped and unmount it on `onClose`; focus moves into the
 * sheet, stays there until it closes (Escape, Close or the backdrop), then returns
 * to whatever had focus before.
 */
export function SourceSheet({ line, sources, onClose }: { line: CostLine; sources: Source[]; onClose: () => void }) {
  const titleId = useId()
  const panel = useRef<HTMLDivElement>(null)
  const closeRef = useRef(onClose)
  const reduceMotion = useReducedMotion()

  useEffect(() => {
    closeRef.current = onClose
  }, [onClose])

  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    panel.current?.focus()
    const onEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') closeRef.current()
    }
    document.addEventListener('keydown', onEscape)
    return () => {
      document.removeEventListener('keydown', onEscape)
      document.body.style.overflow = overflow
      opener?.focus()
    }
  }, [])

  // Keep Tab and Shift+Tab inside the sheet while it is open.
  function trapTab(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'Tab' || panel.current === null) return
    const focusable = [...panel.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled])')]
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    const active = document.activeElement
    if (event.shiftKey && (active === first || active === panel.current)) {
      event.preventDefault()
      last?.focus()
    } else if (!event.shiftKey && active === last) {
      event.preventDefault()
      first?.focus()
    }
  }

  const amount = amountText(line)
  const blank = line.source_type === 'not_estimated'
  const byId = new Map(sources.map((s) => [s.id, s]))
  const ids = [...new Set([line.source_id, ...line.other_source_ids])].filter((id): id is string => Boolean(id))

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-6">
      <motion.div
        aria-hidden="true"
        data-testid="source-sheet-backdrop"
        className="absolute inset-0 bg-stone-950/50"
        onClick={onClose}
        initial={{ opacity: reduceMotion ? 1 : 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: reduceMotion ? 0 : 0.15 }}
      />
      <motion.div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={trapTab}
        initial={{ y: reduceMotion ? 0 : '100%' }}
        animate={{ y: 0 }}
        transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 420, damping: 40 }}
        className={`relative max-h-[85dvh] w-full overflow-y-auto rounded-t-2xl border-t px-5 pt-3 pb-[max(1.25rem,env(safe-area-inset-bottom))] shadow-xl outline-none sm:max-w-lg sm:rounded-2xl sm:border ${ui.surface} ${ui.text} ${ui.border}`}
      >
        <div aria-hidden="true" className="mx-auto mb-3 h-1 w-10 rounded-full bg-stone-300 sm:hidden dark:bg-stone-600" />

        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className={`inline-block rounded-full border px-2.5 py-0.5 text-sm font-medium ${ui.border} ${ui.muted}`}>
              {SOURCE_LABELS[line.source_type]}
            </p>
            <h2 id={titleId} className="mt-2 text-xl leading-snug font-semibold wrap-break-word">
              {line.label}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className={`min-h-11 min-w-11 shrink-0 rounded-lg px-3 font-medium hover:bg-stone-100 active:bg-stone-200 dark:hover:bg-stone-800 dark:active:bg-stone-700 ${ui.muted} ${ui.focus}`}
          >
            Close
          </button>
        </div>

        <p className="mt-3 text-2xl font-semibold wrap-break-word">{amount.text}</p>
        {amount.note && <p className={`text-sm ${ui.muted}`}>{amount.note}</p>}

        <section className="mt-5">
          <h3 className="font-semibold">{blank ? 'Why it is left blank' : 'How it is worked out'}</h3>
          {blank && <p className="mt-1">Left blank on purpose rather than guessed.</p>}
          <p className={`mt-1 wrap-break-word ${blank ? ui.muted : ''}`}>{line.formula}</p>
        </section>

        {ids.length > 0 && (
          <section className="mt-5">
            <h3 className="font-semibold">{ids.length === 1 ? 'Source' : 'Sources'}</h3>
            <ul className={`mt-2 divide-y ${ui.divider} [&>li]:py-3`}>
              {ids.map((id) => (
                <SourceEntry key={id} id={id} source={byId.get(id)} />
              ))}
            </ul>
          </section>
        )}
      </motion.div>
    </div>
  )
}
