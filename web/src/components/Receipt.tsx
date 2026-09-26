// The receipt: every path in API order, one column, phone first (PLAN.md task 2.9).

import type { CostLine, Path } from '../contracts'
import { PathCard } from './PathCard'

export function Receipt({ paths, onLineTap }: { paths: Path[]; onLineTap?: (line: CostLine) => void }) {
  const sample = paths.some((p) => p.flags.includes('fixture'))
  return (
    <section aria-labelledby="receipt-heading" className="mx-auto w-full max-w-md bg-neutral-50 px-4 pb-8 text-neutral-900">
      {sample && (
        <p className="sticky top-0 z-10 -mx-4 border-b border-amber-300 bg-amber-100 px-4 py-2 text-center text-sm font-semibold text-amber-900">
          Sample data, not a real quote
        </p>
      )}
      <h2 id="receipt-heading" className="pt-4 text-xl font-bold">
        Your receipt
      </h2>
      {paths.length === 0 ? (
        <p className="mt-2 text-sm text-neutral-600">No paths to compare yet.</p>
      ) : (
        <ol className="mt-3 space-y-4">
          {paths.map((path, i) => (
            <li key={`${i}-${path.name}`}>
              <PathCard path={path} onLineTap={onLineTap} />
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
