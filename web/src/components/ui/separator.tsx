import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

/** A decorative rule; `dashed` draws the tear-off line of a printed receipt. */
export function Separator({ className, dashed = false, ...props }: ComponentProps<'div'> & { dashed?: boolean }) {
  return (
    <div
      aria-hidden="true"
      data-slot="separator"
      className={cn('w-full shrink-0', dashed ? 'border-t-2 border-dashed border-border' : 'h-px bg-border', className)}
      {...props}
    />
  )
}
