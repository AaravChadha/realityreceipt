import { expect, test } from 'vitest'
import sample from '../../contracts/receipt_fridge.json'
import { MODEL_ENERGY_KEYS, MONTHS, PATH_GROUPS, PATH_KEYS, SOURCE_TYPES, type Path } from './contracts'

const fixture = sample as Path[]

test('the sample receipt has 10 paths across all 6 groups', () => {
  expect(fixture).toHaveLength(10)
  expect(new Set(fixture.map((p) => p.group))).toEqual(new Set(PATH_GROUPS))
})

test('every path has exactly the fields in PATH_KEYS', () => {
  for (const path of fixture) {
    expect(new Set(Object.keys(path))).toEqual(new Set(PATH_KEYS))
  }
})

test('every line uses one of the four source labels', () => {
  for (const line of fixture.flatMap((p) => p.lines)) {
    expect(SOURCE_TYPES).toContain(line.source_type)
  }
})

test('monthly arrays are 36 long', () => {
  for (const path of fixture) {
    expect(path.monthly_low).toHaveLength(MONTHS)
    expect(path.monthly_high).toHaveLength(MONTHS)
  }
})

test('a kWh figure can carry how it was chosen', () => {
  // Checked against api/app/models.py's ModelEnergy fields by api/tests/test_contracts.py.
  expect(MODEL_ENERGY_KEYS).toEqual(['kwh_per_year', 'source_type', 'source_id', 'note', 'note_source_ids'])
})
