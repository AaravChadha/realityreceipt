import { expect, test } from 'vitest'
import { money, range, rangeNote } from './format'

test('a range reads "$A to $B"', () => {
  expect(range(80, 180)).toBe('$80 to $180')
})

test('money is whole dollars, and null is not estimated', () => {
  expect(money(899)).toBe('$899')
  expect(money(1232.6)).toBe('$1,233')
  expect(money(-0.2)).toBe('$0')
  expect(money(null)).toBe('not estimated')
})

test('equal ends show one amount, compared after rounding', () => {
  expect(range(1070, 1070)).toBe('$1,070')
  expect(range(1070.2, 1070.4)).toBe('$1,070')
  expect(range(109.88, 131.92)).toBe('$110 to $132')
})

test('a missing end reads "or more" or "up to", with a note', () => {
  expect(range(159, null)).toBe('$159 or more')
  expect(rangeNote(159, null)).toBe('upper end not estimated')
  expect(range(null, 300)).toBe('up to $300')
  expect(rangeNote(null, 300)).toBe('lower end not estimated')
  expect(range(null, null)).toBe('not estimated')
  expect(rangeNote(null, null)).toBeNull()
  expect(rangeNote(80, 180)).toBeNull()
})
