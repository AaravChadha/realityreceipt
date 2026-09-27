import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import sample from '../../../contracts/receipt_fridge.json'
import type { CostLine, Path } from '../contracts'
import { Receipt } from './Receipt'

const fixture = sample as Path[]

afterEach(cleanup)

function card(name: string) {
  return within(screen.getByRole('article', { name }))
}

test('shows the sample banner and all 9 paths in API order', () => {
  render(<Receipt paths={fixture} />)
  expect(screen.getByText('Sample data, not a real quote')).toBeVisible()
  const names = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
  expect(names).toHaveLength(9)
  expect(names).toEqual(fixture.map((p) => p.name))
})

test('no banner when no path is fixture data', () => {
  const real = fixture.map((p) => ({ ...p, flags: p.flags.filter((f) => f !== 'fixture') }))
  render(<Receipt paths={real} />)
  expect(screen.queryByText('Sample data, not a real quote')).toBeNull()
})

test('each path shows its three headline numbers in whole dollars', () => {
  render(<Receipt paths={fixture} />)
  const used = card('Used, as-is')
  expect(used.getByText('$250')).toBeVisible()
  expect(used.getByText('$484 to $1,383')).toBeVisible()
  expect(used.getByText('$128 to $328')).toBeVisible()
  expect(card('New, pay cash').getByText('$1,070')).toBeVisible()
  expect(card('New, pay cash').getByText('$110 to $132')).toBeVisible()
})

test('a missing upper end reads "or more" with its note', () => {
  render(<Receipt paths={fixture} />)
  const repair = card('Repair the one you have')
  expect(repair.getByText('$159 or more')).toBeVisible()
  expect(repair.getByText('upper end not estimated')).toBeVisible()
})

test('the carbon line shows only when carbon_kg is set', () => {
  const paths = fixture.map((p, i) => (i === 0 ? { ...p, carbon_kg: null } : p))
  render(<Receipt paths={paths} />)
  expect(card(paths[0].name).queryByText(/Carbon/)).toBeNull()
  expect(card('Used, as-is').getByText('624 kg CO2e')).toBeVisible()
})

const COSTS_NOTE = 'Some costs are not estimated, so the real total may be higher.'

test('a path flagged costs_not_estimated says so under its headline numbers', () => {
  const paths = fixture.map((p) =>
    p.name === 'New, buy now pay later' ? { ...p, flags: [...p.flags, 'costs_not_estimated'] } : p,
  )
  render(<Receipt paths={paths} />)
  const bnpl = card('New, buy now pay later')
  const note = bnpl.getByText(COSTS_NOTE)
  expect(note).toBeVisible()
  const numbers = bnpl.getByText('Cost per year of use')
  expect(numbers.compareDocumentPosition(note) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(card('New, pay cash').queryByText(COSTS_NOTE)).toBeNull()
  expect(bnpl.queryByText('costs_not_estimated')).toBeNull()
})

test('a pinned flag shows as a plain sentence; an unpinned flag and the fixture flag do not repeat on the card', () => {
  render(<Receipt paths={fixture} />)
  expect(card('Repair the one you have').getByText('This unit is at or past its typical life.')).toBeVisible()
  expect(
    card('New, credit union PAL').getByText(
      'These figures use the federal limits on credit union PALs, not an offer from a lender.',
    ),
  ).toBeVisible()
  expect(screen.queryByText(/warranty_6_months|past_typical_life/)).toBeNull()
  expect(screen.getAllByText('Sample data, not a real quote')).toHaveLength(1)
})

test('the year_from_rating_data flag shows its sentence, not the flag name', () => {
  const paths = fixture.map((p) => (p.name === 'Used, as-is' ? { ...p, flags: [...p.flags, 'year_from_rating_data'] } : p))
  render(<Receipt paths={paths} />)
  const sentence = 'The year made is estimated from the years DOE lists this model, so its remaining life is a range.'
  expect(card('Used, as-is').getByText(sentence)).toBeVisible()
  expect(screen.getAllByText(sentence)).toHaveLength(1)
  expect(screen.queryByText(/year_from_rating_data/)).toBeNull()
})

test('the may_be_past_typical_life flag shows its sentence, not the flag name', () => {
  const paths = fixture.map((p) => (p.name === 'Used, as-is' ? { ...p, flags: [...p.flags, 'may_be_past_typical_life'] } : p))
  const { container } = render(<Receipt paths={paths} />)
  const sentence = 'This unit may be at or past its typical life.'
  expect(card('Used, as-is').getByText(sentence)).toBeVisible()
  expect(screen.getAllByText(sentence)).toHaveLength(1)
  expect(container.textContent).not.toContain('may_be_past_typical_life')
})

test('every pinned flag has a sentence with no em dash, no "APR", and nothing about qualifying', () => {
  const pinned = [
    'year_from_rating_data',
    'may_be_past_typical_life',
    'costs_not_estimated',
    'past_typical_life',
    'test_procedure_changed',
    'year_from_serial_low_confidence',
    'pal_caps_not_an_offer',
    'bnpl_terms_not_an_offer',
    'over_budget_today',
    'delivery_unknown',
    'width_unknown',
    'fixture',
  ]
  const one = { ...fixture[1], flags: pinned }
  const { container } = render(<Receipt paths={[one]} />)
  for (const flag of pinned) expect(container.textContent).not.toContain(flag)
  expect(within(screen.getByRole('article')).getAllByRole('listitem')).toHaveLength(pinned.length - 2)
  expect(screen.getByText(COSTS_NOTE)).toBeVisible()
  const text = container.textContent ?? ''
  expect(text).not.toContain(String.fromCharCode(0x2014))
  expect(text).not.toContain('APR')
  expect(text.toLowerCase()).not.toContain('qualif')
})

test('the PAL path shows "up to" beside its pay today; other paths do not', () => {
  render(<Receipt paths={fixture} />)
  const payToday = (name: string) => card(name).getByText('Pay today').nextElementSibling
  expect(payToday('New, credit union PAL')).toHaveTextContent(/^up to \$20$/)
  expect(payToday('New, pay cash')).toHaveTextContent(/^\$899$/)
  expect(payToday('New, credit card')).toHaveTextContent(/^\$0$/)
})

test('the "What\'s in this number" toggle is at least 44px tall', () => {
  render(<Receipt paths={fixture} />)
  for (const toggle of screen.getAllByRole('button', { name: "What's in this number" })) {
    expect(toggle).toHaveClass('min-h-11')
  }
})

test('cost lines are collapsed until "What\'s in this number" is tapped', () => {
  render(<Receipt paths={fixture} />)
  const credit = card('New, credit card')
  expect(credit.queryByText('Card interest')).toBeNull()
  const toggle = credit.getByRole('button', { name: "What's in this number" })
  expect(toggle).toHaveAttribute('aria-expanded', 'false')
  fireEvent.click(toggle)
  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  expect(credit.getByText('Card interest')).toBeVisible()
  expect(credit.getAllByText('Published').length).toBeGreaterThan(0)
})

test('a not estimated line is labeled and left blank', () => {
  render(<Receipt paths={fixture} />)
  const bnpl = card('New, buy now pay later')
  fireEvent.click(bnpl.getByRole('button', { name: "What's in this number" }))
  const line = bnpl.getByRole('button', { name: /Buy now pay later cost/ })
  expect(within(line).getByText('Not estimated')).toBeVisible()
  expect(line.textContent).not.toMatch(/\$/)
})

test('tapping a line calls onLineTap with that line', () => {
  const onLineTap = vi.fn<(line: CostLine) => void>()
  render(<Receipt paths={fixture} onLineTap={onLineTap} />)
  const credit = card('New, credit card')
  fireEvent.click(credit.getByRole('button', { name: "What's in this number" }))
  fireEvent.click(credit.getByRole('button', { name: /Card interest/ }))
  const expected = fixture.find((p) => p.name === 'New, credit card')!.lines.find((l) => l.label === 'Card interest')
  expect(onLineTap).toHaveBeenCalledWith(expected)
})

const OVER_SPEND = 'More than you can spend today'

test('paths that cost more today than you can spend are dimmed and still shown', () => {
  render(<Receipt paths={fixture} budgetToday={100} />)
  expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(9)

  const cash = screen.getByRole('article', { name: 'New, pay cash' })
  expect(cash).toBeVisible()
  expect(cash).toHaveClass('opacity-60')
  expect(within(cash).getByText(OVER_SPEND)).toBeVisible()
  expect(within(cash).getByText('$899')).toBeVisible()

  const credit = screen.getByRole('article', { name: 'New, credit card' })
  expect(credit).toBeVisible()
  expect(credit).not.toHaveClass('opacity-60')
  expect(within(credit).queryByText(OVER_SPEND)).toBeNull()
})

test('a path that costs exactly what you can spend today is not dimmed', () => {
  const path = { ...fixture[0], name: 'Exactly the budget', pay_today: 100 }
  render(<Receipt paths={[path]} budgetToday={100} />)
  expect(screen.getByRole('heading', { level: 3, name: 'Exactly the budget' })).toBeVisible()
  expect(screen.queryByText(OVER_SPEND)).toBeNull()
})

test('without a spend limit, nothing is marked as more than you can spend', () => {
  render(<Receipt paths={fixture} budgetToday={null} />)
  expect(screen.queryByText(OVER_SPEND)).toBeNull()
})

test('the over_budget_today flag dims a path even when pay today is within a spend limit', () => {
  const path = { ...fixture[4], flags: [...fixture[4].flags, 'over_budget_today'] }
  render(<Receipt paths={[path]} budgetToday={1000} />)
  const article = screen.getByRole('article')
  expect(article).toBeVisible()
  expect(article).toHaveClass('opacity-60')
  expect(within(article).getByText(OVER_SPEND)).toBeVisible()
  expect(within(article).getByText('This costs more today than the amount you said you can spend.')).toBeVisible()
})

test('the rendered receipt has no em dash, no "APR", and nothing about qualifying', () => {
  const { container } = render(<Receipt paths={fixture} />)
  for (const toggle of screen.getAllByRole('button', { name: "What's in this number" })) fireEvent.click(toggle)
  const text = container.textContent ?? ''
  expect(text).not.toContain(String.fromCharCode(0x2014))
  expect(text).not.toContain('APR')
  expect(text.toLowerCase()).not.toContain('qualif')
})
