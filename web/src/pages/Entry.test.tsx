import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import sample from '../../../contracts/receipt_fridge.json'
import type { Path, Source } from '../contracts'
import Entry from './Entry'

const fixture = sample as Path[]

// jsdom has no scrollIntoView; record the calls instead.
const scrollIntoView = vi.fn()

beforeEach(() => {
  scrollIntoView.mockClear()
  Element.prototype.scrollIntoView = scrollIntoView
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

const section = (name: string) => within(screen.getByRole('group', { name }))

const type = (input: HTMLElement, value: string) => fireEvent.change(input, { target: { value } })

const submit = () => fireEvent.click(screen.getByRole('button', { name: 'Show every way to get it' }))

const SOURCES: Source[] = [
  {
    id: 'frb_g19',
    title: 'Consumer Credit G.19',
    publisher: 'Federal Reserve Board',
    url: 'https://www.federalreserve.gov/releases/g19/current/',
    retrieved_date: '2026-09-24',
  },
  {
    id: 'energystar_refrigerators',
    title: 'ENERGY STAR Certified Residential Refrigerators',
    publisher: 'U.S. EPA ENERGY STAR',
    url: 'https://data.energystar.gov/example',
    retrieved_date: '2026-09-26',
  },
]

// A fake API: /item echoes the unit back, /sources returns SOURCES, /quote returns `paths`.
function fakeApi(paths: Path[] = fixture) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const body = url === '/api/item' ? JSON.parse(String(init?.body)) : url === '/api/sources' ? SOURCES : paths
    return { ok: true, status: 200, json: async () => body } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const bodyOf = (call: unknown[]) => JSON.parse(String((call[1] as RequestInit).body))

// A used listing alone: the smallest form that sends a quote.
function fillUsed() {
  const used = section('A used one you found')
  type(used.getByLabelText('Brand'), 'Whirlpool')
  type(used.getByLabelText('Model number'), 'WRT318FZDW')
  type(used.getByLabelText('Listing price'), '300')
}

// Quotes the fixture and opens one card's cost lines.
async function quoteAndOpen(cardName: string) {
  render(<Entry />)
  fillUsed()
  submit()
  const card = within(await screen.findByRole('article', { name: cardName }))
  fireEvent.click(card.getByRole('button', { name: "What's in this number" }))
  return card
}

test('brand, model and serial inputs are found by their labels', () => {
  render(<Entry />)
  const now = section('Your fridge now')
  expect(now.getByLabelText('Brand')).toBeInTheDocument()
  expect(now.getByLabelText('Model number')).toBeInTheDocument()
  expect(now.getByLabelText('Serial number (optional)')).toBeInTheDocument()
  const used = section('A used one you found')
  expect(used.getByLabelText('Brand')).toBeInTheDocument()
  expect(used.getByLabelText('Model number')).toBeInTheDocument()
  expect(used.getByLabelText('Listing price')).toBeInTheDocument()
})

test('"Year made" is on both sections and the label kWh only on "Your fridge now"', () => {
  render(<Entry />)
  const now = section('Your fridge now')
  expect(now.getByLabelText('Year made (optional)')).toHaveAttribute('inputmode', 'numeric')
  expect(now.getByLabelText('kWh per year on the yellow label (optional)')).toHaveAttribute('inputmode', 'decimal')
  const used = section('A used one you found')
  expect(used.getByLabelText('Year made (optional)')).toHaveAttribute('inputmode', 'numeric')
  expect(used.queryByLabelText(/kWh/)).toBeNull()
})

test('both units go through /item, then /quote gets current, the listing, the years, the label kWh and the amounts', async () => {
  const fetchMock = fakeApi()
  render(<Entry />)
  const now = section('Your fridge now')
  type(now.getByLabelText('Brand'), 'GE')
  type(now.getByLabelText('Model number'), 'GTE18GTHRWW')
  type(now.getByLabelText('Serial number (optional)'), 'VS123456')
  type(now.getByLabelText('Year made (optional)'), '2004')
  type(now.getByLabelText('Product class (optional)'), '3')
  type(now.getByLabelText('Volume in cubic feet (optional)'), '18.2')
  type(now.getByLabelText('kWh per year on the yellow label (optional)'), '586')
  type(now.getByLabelText('Repair quote (optional)'), '$180')
  const used = section('A used one you found')
  type(used.getByLabelText('Brand'), 'Whirlpool')
  type(used.getByLabelText('Model number'), 'WRT318FZDW')
  type(used.getByLabelText('Year made (optional)'), '2015')
  type(used.getByLabelText('Listing price'), '350')
  type(used.getByLabelText('Condition'), 'refurbished')
  type(used.getByLabelText('Warranty in months (optional)'), '6')
  type(screen.getByLabelText('I can spend up to this much today (optional)'), '1,000')
  submit()

  await screen.findByText('Sample data, not a real quote')
  const urls = fetchMock.mock.calls.map((c) => c[0])
  expect(urls).toEqual(['/api/item', '/api/item', '/api/quote', '/api/sources'])
  expect(bodyOf(fetchMock.mock.calls[2])).toEqual({
    current: {
      id: 'current',
      category: 'refrigerator',
      brand: 'GE',
      model: 'GTE18GTHRWW',
      serial: 'VS123456',
      mfg_year: 2004,
      condition: 'used_as_is',
      attributes: { product_class: '3', volume_cuft: 18.2, label_kwh_per_year: 586 },
    },
    items: [
      {
        id: 'listing',
        category: 'refrigerator',
        brand: 'Whirlpool',
        model: 'WRT318FZDW',
        mfg_year: 2015,
        condition: 'refurbished',
        warranty_months: 6,
      },
    ],
    offers: [
      { item_id: 'listing', price: 350, seller_type: 'refurbisher', source: 'user_listing', source_id: 'user_listing' },
    ],
    repair_quote_low: 180,
    repair_quote_high: 180,
    budget_today: 1000,
  })
  const receipt = within(screen.getByRole('region', { name: 'Your receipt' }))
  for (const path of fixture) expect(receipt.getByRole('article', { name: path.name })).toBeInTheDocument()
})

test('the /quote response renders through Receipt: one card per path with its three headline numbers', async () => {
  fakeApi()
  render(<Entry />)
  fillUsed()
  submit()

  const receipt = within(await screen.findByRole('region', { name: 'Your receipt' }))
  expect(receipt.getByText('Sample data, not a real quote')).toBeInTheDocument()
  const names = receipt.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
  expect(names).toEqual(fixture.map((p) => p.name))
  const used = within(receipt.getByRole('article', { name: 'Used, as-is' }))
  expect(used.getByText('Pay today')).toBeInTheDocument()
  expect(used.getByText('$250')).toBeInTheDocument()
  expect(used.getByText('$484 to $1,383')).toBeInTheDocument()
  expect(used.getByText('$128 to $328')).toBeInTheDocument()
})

test('a used one alone is sent as a used_as_is listing with no current unit', async () => {
  const fetchMock = fakeApi([])
  render(<Entry />)
  const used = section('A used one you found')
  type(used.getByLabelText('Brand'), 'Whirlpool')
  type(used.getByLabelText('Model number'), 'WRT318FZDW')
  type(used.getByLabelText('Listing price'), '300')
  fireEvent.click(screen.getByRole('button', { name: 'Show every way to get it' }))

  await screen.findByText('No paths came back for these details.')
  const req = bodyOf(fetchMock.mock.calls.find((c) => c[0] === '/api/quote')!)
  expect(req.current).toBeNull()
  expect(req.items[0].condition).toBe('used_as_is')
  expect(req.items[0].mfg_year).toBeNull()
  expect(req.items[0].warranty_months).toBeNull()
  expect(req.offers[0].seller_type).toBe('private')
  expect(req.repair_quote_low).toBeNull()
})

test('a half-filled section shows errors and sends nothing', () => {
  const fetchMock = fakeApi()
  render(<Entry />)
  const used = section('A used one you found')
  type(used.getByLabelText('Brand'), 'Whirlpool')
  type(used.getByLabelText('Listing price'), 'about 300')
  fireEvent.click(screen.getByRole('button', { name: 'Show every way to get it' }))

  expect(fetchMock).not.toHaveBeenCalled()
  expect(used.getByLabelText('Model number')).toHaveAttribute('aria-invalid', 'true')
  expect(used.getByLabelText('Listing price')).toHaveAccessibleDescription('Enter the listing price as a dollar amount.')
  expect(screen.getByRole('alert')).toHaveTextContent('2 fields need a fix.')
})

test('scan and upload controls and every lease field are on the form', () => {
  render(<Entry />)
  expect(screen.getByRole('button', { name: 'Scan' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Upload saved image' })).toBeInTheDocument()
  expect(screen.getByLabelText('What are you scanning?')).toHaveValue('label')
  expect(screen.queryByRole('option', { name: 'Price tag' })).not.toBeInTheDocument()
  const scanInput = document.querySelector('input[type="file"][capture="environment"]')
  expect(scanInput).toHaveAttribute('accept', 'image/*')
  expect(scanInput).toHaveAttribute('tabindex', '-1')
  expect(scanInput).toHaveAttribute('aria-hidden', 'true')
  const uploads = [...document.querySelectorAll('input[type="file"]')].filter((el) => !el.hasAttribute('capture'))
  expect(uploads).toHaveLength(1)
  expect(uploads[0]).toHaveAttribute('accept', 'image/*')
  expect(uploads[0]).toHaveAttribute('tabindex', '-1')
  expect(uploads[0]).toHaveAttribute('aria-hidden', 'true')

  const lease = section('A rent-to-own lease')
  expect(lease.getByLabelText('Brand')).toBeInTheDocument()
  expect(lease.getByLabelText('Model number')).toBeInTheDocument()
  expect(lease.getByLabelText('Weekly payment')).toBeInTheDocument()
  expect(lease.getByLabelText('Term in weeks')).toBeInTheDocument()
  expect(lease.getByLabelText('Cash price')).toBeInTheDocument()
  expect(lease.getByLabelText('Fees ($0 if none)')).toBeInTheDocument()
  expect(lease.getByLabelText('Paid today')).toBeInTheDocument()
  expect(lease.getByLabelText('Total of all payments, as printed')).toBeInTheDocument()
  expect(lease.getByLabelText('Early purchase rule')).toHaveValue('none')
  expect(lease.getByLabelText('Early purchase fraction')).toBeInTheDocument()
  expect(lease.getByLabelText('Early purchase terms')).toBeInTheDocument()
  expect(lease.getByLabelText('Missed payment rule')).toBeInTheDocument()
  expect(lease.queryByLabelText('Lease source')).not.toBeInTheDocument()
})

test('an invalid scan pre-fills the brand and shows the errors, and does not quote', async () => {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    expect(url).toBe('/api/scan')
    const form = init?.body as FormData
    expect(form.get('kind')).toBe('label')
    expect(form.get('image')).toBeInstanceOf(File)
    return {
      ok: true,
      status: 200,
      json: async () => ({
        kind: 'label',
        valid: false,
        errors: ['could not read the serial', 'model is incomplete'],
        fields: {
          brand: 'Maytag',
          model: 'MB2562',
          serial: null,
          mfg_year: 2004,
          product_class: '3',
          volume_cuft: null,
          label_kwh_per_year: 586,
        },
        item: null,
        offer: null,
        lease: null,
      }),
    } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  const { container } = render(<Entry />)
  const input = container.querySelector('input[type="file"][capture="environment"]') as HTMLInputElement
  fireEvent.change(input, { target: { files: [new File(['label'], 'label.jpg', { type: 'image/jpeg' })] } })

  const now = section('Your fridge now')
  await waitFor(() => expect(now.getByLabelText('Brand')).toHaveValue('Maytag'))
  expect(now.getByLabelText('Model number')).toHaveValue('MB2562')
  expect(now.getByLabelText('Serial number (optional)')).toHaveValue('')
  expect(now.getByLabelText('Year made (optional)')).toHaveValue('2004')
  expect(now.getByLabelText('Product class (optional)')).toHaveValue('3')
  expect(now.getByLabelText('Volume in cubic feet (optional)')).toHaveValue('')
  expect(now.getByLabelText('kWh per year on the yellow label (optional)')).toHaveValue('586')
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('could not read the serial')
  expect(alert).toHaveTextContent('model is incomplete')
  expect(screen.getByText('Correct anything that looks wrong, then show every way to get it.')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
  expect(screen.queryByRole('region', { name: 'Every way to get it' })).not.toBeInTheDocument()
})

test('a lease is quoted only after the user confirms the form', async () => {
  const fetchMock = fakeApi([])
  render(<Entry />)
  const lease = section('A rent-to-own lease')
  type(lease.getByLabelText('Brand'), 'Frigidaire')
  type(lease.getByLabelText('Model number'), 'FRTE1936AV')
  type(lease.getByLabelText('Weekly payment'), '30')
  type(lease.getByLabelText('Term in weeks'), '52')
  type(lease.getByLabelText('Cash price'), '800')
  type(lease.getByLabelText('Fees ($0 if none)'), '25')
  fireEvent.change(lease.getByLabelText('Early purchase rule'), { target: { value: 'pct_of_remaining' } })
  type(lease.getByLabelText('Early purchase fraction'), '0.5')
  type(lease.getByLabelText('Early purchase terms'), 'Half of what is left')
  type(lease.getByLabelText('Missed payment rule'), 'Fees keep accruing')
  type(lease.getByLabelText('Paid today'), '0.01')
  type(lease.getByLabelText('Total of all payments, as printed'), '1739.88')
  expect(fetchMock).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Show every way to get it' }))

  await screen.findByText('No paths came back for these details.')
  const quoteCall = fetchMock.mock.calls.find((c) => c[0] === '/api/quote')
  expect(quoteCall).toBeDefined()
  expect(bodyOf(quoteCall!)).toMatchObject({
    lease: {
      weekly_payment: 30,
      term_weeks: 52,
      cash_price: 800,
      fees: 25,
      early_purchase_rule: 'pct_of_remaining',
      early_purchase_pct: 0.5,
      early_purchase_text: 'Half of what is left',
      missed_payment_rule: 'Fees keep accruing',
      source_id: 'user_lease',
      payment_today: 0.01,
      total_of_payments: 1739.88,
    },
    items: [
      {
        id: 'lease',
        category: 'refrigerator',
        brand: 'Frigidaire',
        model: 'FRTE1936AV',
        condition: 'new',
      },
    ],
    offers: [
      {
        item_id: 'lease',
        price: 800,
        seller_type: 'rent_to_own',
        source: 'user_listing',
        source_id: 'user_listing',
      },
    ],
  })
})

test('a lease scan pre-fills printed fields and stores the early purchase percent as a fraction', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        kind: 'lease',
        valid: false,
        errors: ['weekly payment was hard to read'],
        fields: {
          brand: 'Frigidaire',
          model: 'FRTE1936AV',
          weekly_payment: 33.48,
          early_purchase_rule: 'pct_of_remaining',
          early_purchase_percent: 50,
          payment_today: 0.01,
          total_of_payments: 1739.88,
        },
        item: null,
        offer: null,
        lease: null,
      }),
    }) as Response),
  )
  const { container } = render(<Entry />)
  fireEvent.change(screen.getByLabelText('What are you scanning?'), { target: { value: 'lease' } })
  const input = container.querySelector('input[type="file"][capture="environment"]') as HTMLInputElement
  fireEvent.change(input, { target: { files: [new File(['lease'], 'lease.jpg', { type: 'image/jpeg' })] } })

  const lease = section('A rent-to-own lease')
  await waitFor(() => expect(lease.getByLabelText('Brand')).toHaveValue('Frigidaire'))
  expect(lease.getByLabelText('Model number')).toHaveValue('FRTE1936AV')
  expect(lease.getByLabelText('Weekly payment')).toHaveValue('33.48')
  expect(lease.getByLabelText('Early purchase rule')).toHaveValue('pct_of_remaining')
  expect(lease.getByLabelText('Early purchase fraction')).toHaveValue('0.5')
  expect(lease.getByLabelText('Paid today')).toHaveValue('0.01')
  expect(lease.getByLabelText('Total of all payments, as printed')).toHaveValue('1739.88')
})

test('an early purchase percent of 33.3 is stored as 0.333', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        kind: 'lease',
        valid: false,
        errors: [],
        fields: { early_purchase_percent: 33.3, early_purchase_rule: 'pct_of_remaining' },
        item: null,
        offer: null,
        lease: null,
      }),
    }) as Response),
  )
  const { container } = render(<Entry />)
  fireEvent.change(screen.getByLabelText('What are you scanning?'), { target: { value: 'lease' } })
  const input = container.querySelector('input[type="file"][capture="environment"]') as HTMLInputElement
  fireEvent.change(input, { target: { files: [new File(['lease'], 'lease.jpg', { type: 'image/jpeg' })] } })
  await waitFor(() => expect(section('A rent-to-own lease').getByLabelText('Early purchase fraction')).toHaveValue('0.333'))
})

test('a second lease scan does not keep the first lease buyout', async () => {
  let scan = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => {
      scan += 1
      const fields =
        scan === 1
          ? {
              brand: 'Frigidaire',
              model: 'FRTE1936AV',
              weekly_payment: 33.48,
              early_purchase_rule: 'pct_of_remaining',
              early_purchase_percent: 50,
            }
          : { brand: 'GE', model: 'GTE18', weekly_payment: 20 }
      return {
        ok: true,
        status: 200,
        json: async () => ({ kind: 'lease', valid: false, errors: [], fields, item: null, offer: null, lease: null }),
      } as Response
    }),
  )
  const { container } = render(<Entry />)
  fireEvent.change(screen.getByLabelText('What are you scanning?'), { target: { value: 'lease' } })
  const input = container.querySelector('input[type="file"][capture="environment"]') as HTMLInputElement
  const file = () => fireEvent.change(input, { target: { files: [new File(['lease'], 'lease.jpg', { type: 'image/jpeg' })] } })
  file()
  const lease = section('A rent-to-own lease')
  await waitFor(() => expect(lease.getByLabelText('Early purchase fraction')).toHaveValue('0.5'))
  expect(lease.getByLabelText('Early purchase rule')).toHaveValue('pct_of_remaining')
  file()
  await waitFor(() => expect(lease.getByLabelText('Brand')).toHaveValue('GE'))
  expect(lease.getByLabelText('Early purchase rule')).toHaveValue('none')
  expect(lease.getByLabelText('Early purchase fraction')).toHaveValue('')
})

test('a fee the scan did not print stays empty', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        kind: 'lease',
        valid: false,
        errors: ['fees: not printed. Enter 0 if the lease has none.'],
        fields: { brand: 'Frigidaire', model: 'FRTE1936AV', weekly_payment: 33.48, fees: 'not printed' },
        item: null,
        offer: null,
        lease: null,
      }),
    }) as Response),
  )
  const { container } = render(<Entry />)
  fireEvent.change(screen.getByLabelText('What are you scanning?'), { target: { value: 'lease' } })
  const input = container.querySelector('input[type="file"][capture="environment"]') as HTMLInputElement
  fireEvent.change(input, { target: { files: [new File(['lease'], 'lease.jpg', { type: 'image/jpeg' })] } })
  const lease = section('A rent-to-own lease')
  await waitFor(() => expect(lease.getByLabelText('Weekly payment')).toHaveValue('33.48'))
  expect(lease.getByLabelText('Fees ($0 if none)')).toHaveValue('')
})

function fillLeaseExceptFees() {
  const lease = section('A rent-to-own lease')
  type(lease.getByLabelText('Brand'), 'Frigidaire')
  type(lease.getByLabelText('Model number'), 'FRTE1936AV')
  type(lease.getByLabelText('Weekly payment'), '30')
  type(lease.getByLabelText('Term in weeks'), '52')
  type(lease.getByLabelText('Cash price'), '800')
  return lease
}

test('an empty fee blocks the quote', () => {
  const fetchMock = fakeApi([])
  render(<Entry />)
  const lease = fillLeaseExceptFees()
  fireEvent.click(screen.getByRole('button', { name: 'Show every way to get it' }))
  expect(fetchMock).not.toHaveBeenCalled()
  expect(lease.getByLabelText('Fees ($0 if none)')).toHaveAttribute('aria-invalid', 'true')
  expect(lease.getByLabelText('Fees ($0 if none)')).toHaveAccessibleDescription(
    'Enter the fees as a dollar amount, or 0 if there is none.',
  )
})

test('a fee of 0 entered on purpose is sent', async () => {
  const fetchMock = fakeApi([])
  render(<Entry />)
  const lease = fillLeaseExceptFees()
  type(lease.getByLabelText('Fees ($0 if none)'), '0')
  fireEvent.click(screen.getByRole('button', { name: 'Show every way to get it' }))
  await screen.findByText('No paths came back for these details.')
  const quoteCall = fetchMock.mock.calls.find((c) => c[0] === '/api/quote')
  expect(bodyOf(quoteCall!)).toMatchObject({ lease: { fees: 0, source_id: 'user_lease' } })
})

test('a later scan drops a serial the new image did not read', async () => {
  let scan = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => {
      scan += 1
      const fields =
        scan === 1
          ? { brand: 'Maytag', model: 'MB2562', serial: 'VS123456' }
          : { brand: 'GE', model: 'GTE18', serial: null }
      return {
        ok: true,
        status: 200,
        json: async () => ({ kind: 'label', valid: false, errors: [], fields, item: null, offer: null, lease: null }),
      } as Response
    }),
  )
  const { container } = render(<Entry />)
  const input = container.querySelector('input[type="file"][capture="environment"]') as HTMLInputElement
  const file = () => fireEvent.change(input, { target: { files: [new File(['label'], 'label.jpg', { type: 'image/jpeg' })] } })
  file()
  const now = section('Your fridge now')
  await waitFor(() => expect(now.getByLabelText('Serial number (optional)')).toHaveValue('VS123456'))
  file()
  await waitFor(() => expect(now.getByLabelText('Brand')).toHaveValue('GE'))
  expect(now.getByLabelText('Serial number (optional)')).toHaveValue('')
})

test('a listing scan can mark the fridge new', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        kind: 'listing',
        valid: false,
        errors: [],
        fields: { brand: 'GE', model: 'GTE18', price: 400, condition: 'new' },
        item: null,
        offer: null,
        lease: null,
      }),
    }) as Response),
  )
  const { container } = render(<Entry />)
  fireEvent.change(screen.getByLabelText('What are you scanning?'), { target: { value: 'listing' } })
  const input = container.querySelector('input[type="file"][capture="environment"]') as HTMLInputElement
  fireEvent.change(input, { target: { files: [new File(['listing'], 'listing.jpg', { type: 'image/jpeg' })] } })
  const used = section('A used one you found')
  await waitFor(() => expect(used.getByLabelText('Brand')).toHaveValue('GE'))
  expect(used.getByLabelText('Condition')).toHaveValue('new')
  expect(used.getByLabelText('Listing price')).toHaveValue('400')
})

test('reading an image is announced as status', async () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
  const { container } = render(<Entry />)
  const input = container.querySelector('input[type="file"][capture="environment"]') as HTMLInputElement
  fireEvent.change(input, { target: { files: [new File(['label'], 'label.jpg', { type: 'image/jpeg' })] } })
  expect(await screen.findByRole('status')).toHaveTextContent('Reading the image...')
})

test('an API failure is shown, not swallowed', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok: false, status: 500, json: async () => ({ detail: 'quote engine failed' }) }) as Response),
  )
  render(<Entry />)
  fireEvent.click(screen.getByRole('button', { name: 'Show every way to get it' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not get a receipt: quote engine failed')
})

test('tapping a cost line opens the source sheet with that line and its sources from /sources', async () => {
  fakeApi()
  const card = await quoteAndOpen('New, credit card')
  fireEvent.click(card.getByRole('button', { name: /Card interest/ }))

  const sheet = within(screen.getByRole('dialog', { name: 'Card interest' }))
  expect(sheet.getByText('Published')).toBeInTheDocument()
  expect(sheet.getByText('Consumer Credit G.19')).toBeInTheDocument()
  expect(sheet.getByText('Federal Reserve Board')).toBeInTheDocument()

  fireEvent.click(sheet.getByRole('button', { name: 'Close' }))
  expect(screen.queryByRole('dialog')).toBeNull()
})

test('/sources is fetched once, however many lines are tapped or quotes are made', async () => {
  const fetchMock = fakeApi()
  const card = await quoteAndOpen('New, credit card')
  fireEvent.click(card.getByRole('button', { name: /Card interest/ }))
  fireEvent.keyDown(document, { key: 'Escape' })
  fireEvent.click(card.getByRole('button', { name: /^Electricity/ }))
  expect(screen.getByRole('dialog', { name: 'Electricity' })).toHaveTextContent('ENERGY STAR Certified Residential Refrigerators')
  fireEvent.keyDown(document, { key: 'Escape' })

  submit()
  await screen.findByRole('article', { name: 'New, credit card' })
  const urls = fetchMock.mock.calls.map((c) => c[0])
  expect(urls.filter((u) => u === '/api/quote')).toHaveLength(2)
  expect(urls.filter((u) => u === '/api/sources')).toHaveLength(1)
})

test('if /sources fails, the sheet still opens, and the next quote asks again', async () => {
  let sourcesUp = false
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/sources' && !sourcesUp) return { ok: false, status: 503, json: async () => null } as Response
    const body = url === '/api/item' ? JSON.parse(String(init?.body)) : url === '/api/sources' ? SOURCES : fixture
    return { ok: true, status: 200, json: async () => body } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  const card = await quoteAndOpen('New, credit card')
  fireEvent.click(card.getByRole('button', { name: /Card interest/ }))
  expect(screen.getByRole('dialog', { name: 'Card interest' })).toHaveTextContent('Source details are not available right now.')
  fireEvent.keyDown(document, { key: 'Escape' })

  sourcesUp = true
  submit()
  const again = within(await screen.findByRole('article', { name: 'New, credit card' }))
  fireEvent.click(again.getByRole('button', { name: "What's in this number" }))
  fireEvent.click(again.getByRole('button', { name: /Card interest/ }))
  expect(await screen.findByText('Consumer Credit G.19')).toBeInTheDocument()
  expect(fetchMock.mock.calls.filter((c) => c[0] === '/api/sources')).toHaveLength(2)
})

test('after a quote, focus moves to the results and they scroll into view', async () => {
  fakeApi()
  render(<Entry />)
  fillUsed()
  const button = screen.getByRole('button', { name: 'Show every way to get it' })
  button.focus()
  submit()

  const receipt = await screen.findByRole('region', { name: 'Your receipt' })
  const focused = document.activeElement as HTMLElement
  expect(focused).not.toBe(button)
  expect(focused).toContainElement(receipt)
  expect(focused).toHaveAttribute('tabindex', '-1')
  expect(scrollIntoView).toHaveBeenCalledTimes(1)
  expect(scrollIntoView.mock.contexts[0]).toBe(focused)
  expect(scrollIntoView.mock.calls[0][0]).toMatchObject({ block: 'start' })
})

test('a year that is not four digits from 1940 to this year, or a label kWh of 0, is an error and nothing is sent', () => {
  const fetchMock = fakeApi()
  render(<Entry />)
  const thisYear = new Date().getFullYear()
  const now = section('Your fridge now')
  type(now.getByLabelText('Brand'), 'Maytag')
  type(now.getByLabelText('Model number'), 'MB2562')
  type(now.getByLabelText('Year made (optional)'), '04')
  type(now.getByLabelText('kWh per year on the yellow label (optional)'), '0')
  fillUsed()
  type(section('A used one you found').getByLabelText('Year made (optional)'), String(thisYear + 1))
  submit()

  expect(fetchMock).not.toHaveBeenCalled()
  const yearError = `Enter the year as four digits, from 1940 to ${thisYear}.`
  expect(now.getByLabelText('Year made (optional)')).toHaveAccessibleDescription(yearError)
  expect(now.getByLabelText('kWh per year on the yellow label (optional)')).toHaveAccessibleDescription(
    'Enter the kWh per year as a number above 0, for example 586.',
  )
  expect(section('A used one you found').getByLabelText('Year made (optional)')).toHaveAccessibleDescription(yearError)
  expect(screen.getByRole('alert')).toHaveTextContent('3 fields need a fix.')
})

test('a budget below pay today dims that path on the receipt', async () => {
  fakeApi()
  render(<Entry />)
  type(screen.getByLabelText('I can spend up to this much today (optional)'), '100')
  submit()
  expect(await screen.findAllByText('More than you can spend today')).not.toHaveLength(0)
})

test('a scan waits 75 seconds before it stops, and says it is reading', async () => {
  vi.useFakeTimers()
  const fetchMock = vi.fn(
    (_url: string, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('The operation was aborted.', 'AbortError')))
      }),
  )
  vi.stubGlobal('fetch', fetchMock)
  const { container } = render(<Entry />)
  const input = container.querySelector('input[type="file"][capture="environment"]') as HTMLInputElement
  fireEvent.change(input, { target: { files: [new File(['label'], 'label.jpg', { type: 'image/jpeg' })] } })
  await act(async () => {})
  expect(screen.getByRole('status')).toHaveTextContent('Reading the image...')
  await act(async () => {
    await vi.advanceTimersByTimeAsync(15_000)
  })
  expect(fetchMock.mock.calls[0][1]?.signal?.aborted).toBe(false)
  expect(screen.queryByRole('alert')).toBeNull()
  await act(async () => {
    await vi.advanceTimersByTimeAsync(45_000)
  })
  // At 60 seconds the server's own Grok error can still arrive, so the page keeps waiting.
  expect(fetchMock.mock.calls[0][1]?.signal?.aborted).toBe(false)
  expect(screen.queryByRole('alert')).toBeNull()
  await act(async () => {
    await vi.advanceTimersByTimeAsync(15_000)
  })
  expect(fetchMock.mock.calls[0][1]?.signal?.aborted).toBe(true)
  expect(screen.getByRole('alert')).toHaveTextContent(
    'Could not read the image: No answer after 75 seconds. Check your connection and try again.',
  )
})

test('a request with no answer after 15 seconds is stopped with a plain message', async () => {
  vi.useFakeTimers()
  const fetchMock = vi.fn(
    (_url: string, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('The operation was aborted.', 'AbortError')))
      }),
  )
  vi.stubGlobal('fetch', fetchMock)
  render(<Entry />)
  submit()
  await act(async () => {}) // let the submit handler reach fetch, which starts the 15-second timer
  expect(fetchMock).toHaveBeenCalledTimes(1)
  await act(async () => {
    await vi.advanceTimersByTimeAsync(14_999)
  })
  expect(screen.queryByRole('alert')).toBeNull()
  expect(screen.getByRole('button', { name: 'Working it out...' })).toBeDisabled()

  await act(async () => {
    await vi.advanceTimersByTimeAsync(1)
  })
  expect(fetchMock.mock.calls[0][1]?.signal?.aborted).toBe(true)
  expect(screen.getByRole('alert')).toHaveTextContent(
    'Could not get a receipt: No answer after 15 seconds. Check your connection and try again.',
  )
})

function labelScan(fields: Record<string, unknown>) {
  return {
    ok: true,
    status: 200,
    json: async () => ({ kind: 'label', valid: true, errors: [], fields, item: null, offer: null, lease: null }),
  } as Response
}

test('a label scan for a different fridge clears the repair quote; a rescan of the same fridge keeps it', async () => {
  let reply = labelScan({ brand: 'ge', model: ' gte18 ' })
  vi.stubGlobal('fetch', vi.fn(async () => reply))
  const { container } = render(<Entry />)
  const now = section('Your fridge now')
  type(now.getByLabelText('Brand'), 'GE')
  type(now.getByLabelText('Model number'), 'GTE18')
  type(now.getByLabelText('Repair quote (optional)'), '$180')
  const input = container.querySelector('input[type="file"][capture="environment"]') as HTMLInputElement
  const scanLabel = () =>
    fireEvent.change(input, { target: { files: [new File(['label'], 'label.jpg', { type: 'image/jpeg' })] } })

  scanLabel()
  await waitFor(() => expect(now.getByLabelText('Brand')).toHaveValue('ge'))
  expect(now.getByLabelText('Repair quote (optional)')).toHaveValue('$180')

  reply = labelScan({ brand: 'Maytag', model: 'MB2562' })
  scanLabel()
  await waitFor(() => expect(now.getByLabelText('Brand')).toHaveValue('Maytag'))
  expect(now.getByLabelText('Repair quote (optional)')).toHaveValue('')
})

function quoteFails(message: string) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/quote') {
      return { ok: false, status: 422, json: async () => ({ detail: [{ msg: message }] }) } as Response
    }
    const body = url === '/api/item' ? JSON.parse(String(init?.body)) : []
    return { ok: true, status: 200, json: async () => body } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

test('a payment today that does not fit the lease total shows beside Paid today, without "Value error"', async () => {
  quoteFails('Value error, the payment today printed on the lease does not fit its total of payments')
  render(<Entry />)
  const lease = fillLeaseExceptFees()
  type(lease.getByLabelText('Fees ($0 if none)'), '0')
  type(lease.getByLabelText('Paid today'), '500')
  submit()

  await waitFor(() =>
    expect(lease.getByLabelText('Paid today')).toHaveAccessibleDescription(
      'The payment today printed on the lease does not fit its total of payments.',
    ),
  )
  expect(lease.getByLabelText('Paid today')).toHaveAttribute('aria-invalid', 'true')
  expect(screen.getByRole('alert')).toHaveTextContent('One field needs a fix.')
  expect(screen.queryByText(/Value error/)).toBeNull()
  expect(screen.queryByText(/Could not get a receipt/)).toBeNull()
})

test('any other 422 message is shown without its "Value error, " prefix', async () => {
  quoteFails('Value error, the cash price must be above 0')
  render(<Entry />)
  submit()
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not get a receipt: the cash price must be above 0')
  expect(screen.queryByText(/Value error/)).toBeNull()
})
