import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test } from 'vitest'
import App from './App'

beforeEach(() => {
  window.location.hash = ''
})

afterEach(() => {
  cleanup()
  window.location.hash = ''
})

test('the shop page is reachable from the first screen', async () => {
  render(<App />)
  // The first screen is the fridge entry form.
  expect(screen.getByRole('group', { name: 'Your fridge now' })).toBeInTheDocument()
  expect(screen.queryByLabelText('What are you looking for?')).toBeNull()

  fireEvent.click(screen.getByRole('link', { name: 'Shop for one' }))

  expect(await screen.findByLabelText('What are you looking for?')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Shop for one' })).toHaveAttribute('aria-current', 'page')
  expect(screen.queryByRole('group', { name: 'Your fridge now' })).toBeNull()
})

test('the link back to the entry form works', async () => {
  window.location.hash = '#/shop'
  render(<App />)
  expect(screen.getByLabelText('What are you looking for?')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('link', { name: 'Check a fridge' }))

  expect(await screen.findByRole('group', { name: 'Your fridge now' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Check a fridge' })).toHaveAttribute('aria-current', 'page')
})

test('the browser back button changes the page', async () => {
  render(<App />)
  fireEvent.click(screen.getByRole('link', { name: 'Shop for one' }))
  expect(await screen.findByLabelText('What are you looking for?')).toBeInTheDocument()

  act(() => {
    window.history.back()
  })

  expect(await screen.findByRole('group', { name: 'Your fridge now' })).toBeInTheDocument()
})

test('the header is not fridge-only and says fridges come first', () => {
  render(<App />)
  expect(screen.getByText(/Every way to get a big purchase, side by side/)).toBeInTheDocument()
  expect(screen.getByText('Starting with refrigerators. Cars, ovens, window ACs and more are next.')).toBeInTheDocument()
})

test('a link straight to #/shop opens the shop page', () => {
  window.location.hash = '#/shop'
  render(<App />)
  expect(screen.getByLabelText('What are you looking for?')).toBeInTheDocument()
})
