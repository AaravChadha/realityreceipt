import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import sample from '../../../contracts/receipt_fridge.json'
import { ApiError, parseShopRequest, rankShopOffers } from '../api'
import type { Path, RankedOffer, ShopFilters } from '../contracts'
import Shop from './Shop'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  parseShopRequest: vi.fn(),
  rankShopOffers: vi.fn(),
}))

const parse = vi.mocked(parseShopRequest)
const rank = vi.mocked(rankShopOffers)

const base = (sample as Path[])[0]

const FILTERS: ShopFilters = {
  category: 'refrigerator',
  budget_today: 300,
  need_within_days: 7,
  max_width_in: 28,
  conditions: ['new', 'used_as_is'],
}

const RANKED: RankedOffer[] = [
  {
    offer: {
      item_id: 'bb-ffht1822uv',
      price: 649,
      seller_type: 'retailer',
      source: 'retailer_cache',
      source_id: 'bestbuy',
      url: 'https://www.bestbuy.com/site/ffht1822uv',
    },
    path: { ...base, name: 'New, pay cash', cost_per_year_low: 80, cost_per_year_high: 95, flags: [] },
  },
  {
    offer: {
      item_id: 'hd-gte18dtnrww',
      price: 699,
      seller_type: 'retailer',
      source: 'retailer_cache',
      source_id: 'homedepot',
      url: 'https://www.homedepot.com/p/gte18dtnrww',
    },
    path: {
      ...base,
      name: 'New, pay cash',
      cost_per_year_low: 110,
      cost_per_year_high: 120,
      flags: ['delivery_unknown'],
    },
  },
  {
    offer: {
      item_id: 'listing',
      price: 175,
      seller_type: 'private',
      source: 'user_listing',
      source_id: 'user_listing',
    },
    path: {
      ...base,
      name: 'Used, as-is',
      cost_per_year_low: null,
      cost_per_year_high: null,
      flags: ['costs_not_estimated'],
    },
  },
]

beforeEach(() => {
  parse.mockResolvedValue(FILTERS)
  rank.mockResolvedValue(RANKED)
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const type = (input: HTMLElement, value: string) => fireEvent.change(input, { target: { value } })

async function readRequest(text = 'About $300, small space, need it this week') {
  render(<Shop />)
  type(screen.getByLabelText('What are you looking for?'), text)
  fireEvent.click(screen.getByRole('button', { name: 'Read my request' }))
  await screen.findByRole('heading', { name: 'What we read from it' })
}

const rankOffers = () => fireEvent.click(screen.getByRole('button', { name: 'Rank offers by cost per year' }))

test('the parsed filters show as editable chips', async () => {
  await readRequest()
  expect(parse).toHaveBeenCalledWith('About $300, small space, need it this week')
  expect(screen.getByLabelText('Spend today up to')).toHaveValue('300')
  expect(screen.getByLabelText('Need it within')).toHaveValue('7')
  expect(screen.getByLabelText('Width up to')).toHaveValue('28')
  const condition = within(screen.getByRole('group', { name: 'Condition' }))
  expect(condition.getByRole('button', { name: 'New' })).toHaveAttribute('aria-pressed', 'true')
  expect(condition.getByRole('button', { name: 'Used, as-is' })).toHaveAttribute('aria-pressed', 'true')
  expect(condition.getByRole('button', { name: 'Refurbished' })).toHaveAttribute('aria-pressed', 'false')
})

test('ranking sends the edited filters, not the parsed ones', async () => {
  await readRequest()
  type(screen.getByLabelText('Spend today up to'), '$450')
  type(screen.getByLabelText('Width up to'), '')
  fireEvent.click(screen.getByRole('button', { name: 'Used, as-is' }))
  rankOffers()
  await screen.findByRole('heading', { name: 'Offers ranked by cost per year' })
  expect(rank).toHaveBeenCalledWith({
    filters: {
      category: 'refrigerator',
      budget_today: 450,
      need_within_days: 7,
      max_width_in: null,
      conditions: ['new'],
    },
  })
})

test('ranked offers show in API order with price, cost per year, flags and a retailer link', async () => {
  await readRequest()
  rankOffers()
  const cards = await screen.findAllByRole('article')
  expect(cards).toHaveLength(3)

  const first = within(cards[0])
  expect(first.getByRole('heading', { name: '1. FFHT1822UV' })).toBeInTheDocument()
  expect(first.getByText('$649')).toBeInTheDocument()
  expect(first.getByText('$80 to $95')).toBeInTheDocument()
  const link = first.getByRole('link', { name: /View at retailer/ })
  expect(link).toHaveAttribute('href', 'https://www.bestbuy.com/site/ffht1822uv')
  expect(link).toHaveAttribute('target', '_blank')
  expect(link).toHaveAttribute('rel', 'noopener noreferrer')

  const second = within(cards[1])
  expect(second.getByText('$110 to $120')).toBeInTheDocument()
  expect(second.getByText('The delivery time for this offer is not known.')).toBeInTheDocument()
  expect(second.getByRole('link', { name: /View at retailer/ })).toHaveAttribute(
    'href',
    'https://www.homedepot.com/p/gte18dtnrww',
  )

  // A listing with no url has no link, and a missing cost per year says so.
  const third = within(cards[2])
  expect(third.getByText('not estimated')).toBeInTheDocument()
  expect(third.getByText('Some costs are not estimated, so the real total may be higher.')).toBeInTheDocument()
  expect(third.queryByRole('link')).toBeNull()
})

test('empty filters and no offers read as empty states, not errors', async () => {
  parse.mockResolvedValue({})
  rank.mockResolvedValue([])
  await readRequest('a fridge')
  expect(screen.getByText(/No filters were read from that/)).toBeInTheDocument()
  expect(screen.getByLabelText('Spend today up to')).toHaveValue('')
  rankOffers()
  expect(await screen.findByText(/No offers match these filters yet/)).toBeInTheDocument()
  expect(screen.queryByRole('alert')).toBeNull()
})

test('an API error shows its message', async () => {
  parse.mockRejectedValue(new ApiError(502, 'The model did not answer.'))
  render(<Shop />)
  type(screen.getByLabelText('What are you looking for?'), 'a fridge')
  fireEvent.click(screen.getByRole('button', { name: 'Read my request' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not read the request: The model did not answer.')
})
