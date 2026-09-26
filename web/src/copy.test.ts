import { expect, test } from 'vitest'

// Every non-test .ts and .tsx file under web/src, as text (spec §6 wording rules).
const files = import.meta.glob<string>(['./**/*.{ts,tsx}', '!./**/*.test.{ts,tsx}'], {
  query: '?raw',
  import: 'default',
  eager: true,
})

test('the scan covers the app source', () => {
  expect(Object.keys(files)).toEqual(expect.arrayContaining(['./App.tsx', './api.ts', './pages/Entry.tsx']))
  expect(Object.keys(files).some((name) => /\.test\.tsx?$/.test(name))).toBe(false)
})

test('no source file contains an em dash or the word APR', () => {
  const hits = Object.entries(files).flatMap(([name, text]) =>
    text.split('\n').flatMap((line, i) => (/—|\bAPR\b/.test(line) ? [`${name}:${i + 1}: ${line.trim()}`] : [])),
  )
  expect(hits).toEqual([])
})
