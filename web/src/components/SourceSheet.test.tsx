import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import type { CostLine, Source } from '../contracts'
import { SourceSheet } from './SourceSheet'

afterEach(cleanup)

const SOURCES: Source[] = [
  {
    id: 'energystar_refrigerators',
    title: 'ENERGY STAR Certified Residential Refrigerators',
    publisher: 'U.S. EPA ENERGY STAR',
    url: 'https://data.energystar.gov/example',
    retrieved_date: '2026-09-26',
  },
  {
    id: 'ga_power_residential_tariff',
    title: 'Residential Service Schedule R',
    publisher: 'Georgia Power',
    url: 'https://www.georgiapower.com/example.pdf',
    retrieved_date: '2026-09-25',
  },
  {
    id: 'frb_g19',
    title: 'Consumer Credit G.19',
    publisher: 'Federal Reserve Board',
    url: 'https://www.federalreserve.gov/releases/g19/current/',
    retrieved_date: '2026-09-24',
  },
]

const line = (overrides: Partial<CostLine>): CostLine => ({
  kind: 'running',
  label: 'Electricity',
  amount_low: 57,
  amount_high: 57,
  period: 'year',
  source_type: 'rated',
  source_id: 'energystar_refrigerators',
  formula: '380 kWh a year x $0.15 per kWh',
  other_source_ids: ['ga_power_residential_tariff'],
  ...overrides,
})

const RATED = line({})
const PUBLISHED = line({
  kind: 'financing',
  label: 'Card interest',
  amount_low: 134.72,
  amount_high: 134.72,
  period: 'window',
  source_type: 'published',
  source_id: 'frb_g19',
  formula: '12 equal payments of $94.56 at 24.00% a year, $1,134.72 in all, less the $1,000.00 price',
  other_source_ids: [],
})
const USER_ENTERED = line({
  kind: 'purchase',
  label: 'Price today',
  amount_low: 250,
  amount_high: 250,
  period: 'once',
  source_type: 'user_entered',
  source_id: 'user_listing',
  formula: 'The price on the listing you entered',
  other_source_ids: [],
})
const NOT_ESTIMATED = line({
  label: 'Extra use from age',
  amount_low: null,
  amount_high: null,
  source_type: 'not_estimated',
  source_id: null,
  formula: 'No published figure for how much more an aging unit draws',
  other_source_ids: [],
})

const open = (costLine: CostLine, onClose = () => {}) => render(<SourceSheet line={costLine} sources={SOURCES} onClose={onClose} />)

test('one line of each source type shows its source label', () => {
  const cases: [CostLine, string][] = [
    [RATED, 'Rated'],
    [PUBLISHED, 'Published'],
    [USER_ENTERED, 'You entered'],
    [NOT_ESTIMATED, 'Not estimated'],
  ]
  for (const [costLine, label] of cases) {
    open(costLine)
    const sheet = screen.getByRole('dialog', { name: costLine.label })
    expect(within(sheet).getAllByText(label, { exact: true }).length).toBeGreaterThan(0)
    cleanup()
  }
})

test('amounts show cents, the period, and a range as "A to B"', () => {
  open(line({ amount_low: 1232.6, amount_high: 1500 }))
  expect(screen.getByText('$1,232.60 to $1,500.00 a year')).toBeInTheDocument()
  cleanup()
  open(PUBLISHED)
  // A "window" total takes format.ts's PERIOD_SUFFIX, as on the receipt card: no suffix.
  expect(screen.getByText('$134.72')).toBeInTheDocument()
  cleanup()
  open(USER_ENTERED)
  expect(screen.getByText('$250.00')).toBeInTheDocument()
  cleanup()
  open(line({ amount_low: 7.5, amount_high: 7.5, period: 'month' }))
  expect(screen.getByText('$7.50 a month')).toBeInTheDocument()
})

test('a range missing one end names the missing end, never "to not estimated"', () => {
  open(line({ amount_low: 159, amount_high: null }))
  expect(screen.getByText('$159.00 or more a year')).toBeInTheDocument()
  expect(screen.getByText('upper end not estimated')).toBeInTheDocument()
  cleanup()
  open(line({ amount_low: null, amount_high: 99, period: 'month' }))
  expect(screen.getByText('up to $99.00 a month')).toBeInTheDocument()
  expect(screen.getByText('lower end not estimated')).toBeInTheDocument()
  expect(screen.queryByText(/to not estimated/i)).toBeNull()
})

test('the main source and every other source show title, publisher, link and retrieved date', () => {
  open(RATED)
  const sheet = screen.getByRole('dialog', { name: 'Electricity' })
  expect(within(sheet).getByRole('heading', { name: 'Sources' })).toBeInTheDocument()
  expect(within(sheet).getByText('380 kWh a year x $0.15 per kWh')).toBeInTheDocument()
  for (const [source, date] of [
    [SOURCES[0], 'Retrieved Sep 26, 2026'],
    [SOURCES[1], 'Retrieved Sep 25, 2026'],
  ] as const) {
    expect(within(sheet).getByText(source.title)).toBeInTheDocument()
    expect(within(sheet).getByText(source.publisher)).toBeInTheDocument()
    expect(within(sheet).getByText(date)).toBeInTheDocument()
    const link = within(sheet).getByRole('link', { name: `${source.url} (opens in a new tab)` })
    expect(link).toHaveAttribute('href', source.url)
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noreferrer')
  }
})

test('reserved ids read as plain words, and an unknown id says its details are missing', () => {
  open(USER_ENTERED)
  expect(screen.getByText('From the listing you entered')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Source' })).toBeInTheDocument()
  cleanup()
  open(line({ source_type: 'user_entered', source_id: 'user', other_source_ids: ['user_lease', 'not_in_sources'] }))
  expect(screen.getByText('You entered this')).toBeInTheDocument()
  expect(screen.getByText('From your lease')).toBeInTheDocument()
  expect(screen.getByText('Source details are not available right now.')).toBeInTheDocument()
  expect(screen.getByText('Reference: not_in_sources')).toBeInTheDocument()
})

test('a source URL that is not http or https is shown as text, not a link', () => {
  const sources: Source[] = [{ ...SOURCES[2], url: 'javascript:alert(1)' }]
  render(<SourceSheet line={PUBLISHED} sources={sources} onClose={() => {}} />)
  expect(screen.queryByRole('link')).toBeNull()
  expect(screen.getByText('javascript:alert(1)')).toBeInTheDocument()
})

test('a not-estimated line says it is left blank on purpose and lists no sources', () => {
  open(NOT_ESTIMATED)
  const sheet = screen.getByRole('dialog', { name: 'Extra use from age' })
  expect(within(sheet).getByRole('heading', { name: 'Why it is left blank' })).toBeInTheDocument()
  expect(within(sheet).getByText('Left blank on purpose rather than guessed.')).toBeInTheDocument()
  expect(within(sheet).queryByRole('heading', { name: /^Sources?$/ })).toBeNull()
  expect(within(sheet).queryByText(/\$/)).toBeNull()
})

test('focus moves into the sheet, Tab stays inside it, and Escape or Close calls onClose', () => {
  const onClose = vi.fn()
  open(RATED, onClose)
  const sheet = screen.getByRole('dialog', { name: 'Electricity' })
  expect(sheet).toHaveAttribute('aria-modal', 'true')
  expect(sheet).toHaveFocus()

  const close = within(sheet).getByRole('button', { name: 'Close' })
  const links = within(sheet).getAllByRole('link')
  const last = links[links.length - 1]
  last.focus()
  fireEvent.keyDown(last, { key: 'Tab' })
  expect(close).toHaveFocus()
  fireEvent.keyDown(close, { key: 'Tab', shiftKey: true })
  expect(last).toHaveFocus()

  fireEvent.keyDown(document, { key: 'Escape' })
  expect(onClose).toHaveBeenCalledTimes(1)
  fireEvent.click(close)
  expect(onClose).toHaveBeenCalledTimes(2)
  fireEvent.click(screen.getByTestId('source-sheet-backdrop'))
  expect(onClose).toHaveBeenCalledTimes(3)
})

function TappableLine({ costLine }: { costLine: CostLine }) {
  const [openLine, setOpenLine] = useState<CostLine | null>(null)
  return (
    <>
      <button type="button" onClick={() => setOpenLine(costLine)}>
        {costLine.label}
      </button>
      {openLine && <SourceSheet line={openLine} sources={SOURCES} onClose={() => setOpenLine(null)} />}
    </>
  )
}

test('tapping a cost line opens the sheet, and closing it returns focus to the line', () => {
  render(<TappableLine costLine={RATED} />)
  const trigger = screen.getByRole('button', { name: 'Electricity' })
  trigger.focus()
  fireEvent.click(trigger)
  expect(screen.getByRole('dialog', { name: 'Electricity' })).toHaveFocus()
  expect(document.body.style.overflow).toBe('hidden')

  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(trigger).toHaveFocus()
  expect(document.body.style.overflow).toBe('')
})
