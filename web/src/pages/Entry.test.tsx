import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import sample from '../../../contracts/receipt_fridge.json'
import type { Path } from '../contracts'
import Entry from './Entry'

const fixture = sample as Path[]

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const section = (name: string) => within(screen.getByRole('group', { name }))

const type = (input: HTMLElement, value: string) => fireEvent.change(input, { target: { value } })

// A fake API: /item echoes the unit back, /quote returns `paths`.
function fakeApi(paths: Path[] = fixture) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const body = url === '/api/item' ? JSON.parse(String(init?.body)) : paths
    return { ok: true, status: 200, json: async () => body } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const bodyOf = (call: unknown[]) => JSON.parse(String((call[1] as RequestInit).body))

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

test('both units go through /item, then /quote gets current, the listing and the amounts', async () => {
  const fetchMock = fakeApi()
  render(<Entry />)
  const now = section('Your fridge now')
  type(now.getByLabelText('Brand'), 'GE')
  type(now.getByLabelText('Model number'), 'GTE18GTHRWW')
  type(now.getByLabelText('Serial number (optional)'), 'VS123456')
  type(now.getByLabelText('Product class (optional)'), '3')
  type(now.getByLabelText('Volume in cubic feet (optional)'), '18.2')
  type(now.getByLabelText('Repair quote (optional)'), '$180')
  const used = section('A used one you found')
  type(used.getByLabelText('Brand'), 'Whirlpool')
  type(used.getByLabelText('Model number'), 'WRT318FZDW')
  type(used.getByLabelText('Listing price'), '350')
  type(used.getByLabelText('Condition'), 'refurbished')
  type(used.getByLabelText('Warranty in months (optional)'), '6')
  type(screen.getByLabelText('I can spend up to this much today (optional)'), '1,000')
  fireEvent.click(screen.getByRole('button', { name: 'Show every way to get it' }))

  await screen.findByText('Sample data, not a real quote')
  const urls = fetchMock.mock.calls.map((c) => c[0])
  expect(urls).toEqual(['/api/item', '/api/item', '/api/quote'])
  expect(bodyOf(fetchMock.mock.calls[2])).toEqual({
    current: {
      id: 'current',
      category: 'refrigerator',
      brand: 'GE',
      model: 'GTE18GTHRWW',
      serial: 'VS123456',
      condition: 'used_as_is',
      attributes: { product_class: '3', volume_cuft: 18.2 },
    },
    items: [
      {
        id: 'listing',
        category: 'refrigerator',
        brand: 'Whirlpool',
        model: 'WRT318FZDW',
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
  const list = within(screen.getByRole('region', { name: 'Every way to get it' }))
  for (const path of fixture) expect(list.getByText(path.name)).toBeInTheDocument()
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
  const req = bodyOf(fetchMock.mock.calls.at(-1)!)
  expect(req.current).toBeNull()
  expect(req.items[0].condition).toBe('used_as_is')
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
  const scanInput = document.querySelector('input[type="file"][capture="environment"]')
  expect(scanInput).toHaveAttribute('accept', 'image/*')
  const uploads = [...document.querySelectorAll('input[type="file"]')].filter((el) => !el.hasAttribute('capture'))
  expect(uploads).toHaveLength(1)
  expect(uploads[0]).toHaveAttribute('accept', 'image/*')

  const lease = section('A rent-to-own lease')
  expect(lease.getByLabelText('Weekly payment')).toBeInTheDocument()
  expect(lease.getByLabelText('Term in weeks')).toBeInTheDocument()
  expect(lease.getByLabelText('Cash price')).toBeInTheDocument()
  expect(lease.getByLabelText('Fees (optional)')).toBeInTheDocument()
  expect(lease.getByLabelText('Early purchase rule')).toHaveValue('none')
  expect(lease.getByLabelText('Early purchase fraction')).toBeInTheDocument()
  expect(lease.getByLabelText('Early purchase terms')).toBeInTheDocument()
  expect(lease.getByLabelText('Missed payment rule')).toBeInTheDocument()
  expect(lease.getByLabelText('Lease source')).toHaveValue('user_lease')
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
        item: {
          id: 'from-scan',
          category: 'refrigerator',
          brand: 'Maytag',
          model: 'MB2562',
          serial: null,
          condition: 'used_as_is',
          attributes: { product_class: '3' },
        },
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
  expect(await now.findByLabelText('Brand')).toHaveValue('Maytag')
  expect(now.getByLabelText('Model number')).toHaveValue('MB2562')
  expect(now.getByLabelText('Product class (optional)')).toHaveValue('3')
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
  type(lease.getByLabelText('Weekly payment'), '30')
  type(lease.getByLabelText('Term in weeks'), '52')
  type(lease.getByLabelText('Cash price'), '800')
  type(lease.getByLabelText('Fees (optional)'), '25')
  fireEvent.change(lease.getByLabelText('Early purchase rule'), { target: { value: 'pct_of_remaining' } })
  type(lease.getByLabelText('Early purchase fraction'), '0.5')
  type(lease.getByLabelText('Early purchase terms'), 'Half of what is left')
  type(lease.getByLabelText('Missed payment rule'), 'Fees keep accruing')
  expect(fetchMock).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Show every way to get it' }))

  await screen.findByText('No paths came back for these details.')
  expect(bodyOf(fetchMock.mock.calls.at(-1)!)).toMatchObject({
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
    },
  })
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
