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

test('an API failure is shown, not swallowed', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok: false, status: 500, json: async () => ({ detail: 'quote engine failed' }) }) as Response),
  )
  render(<Entry />)
  fireEvent.click(screen.getByRole('button', { name: 'Show every way to get it' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not get a receipt: quote engine failed')
})
