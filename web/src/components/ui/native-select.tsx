import { ChevronDown } from 'lucide-react'
import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'
import { inputClass } from './input'

// A real <select> (not a Radix listbox): the phone's own picker, and tests can choose options.
export function NativeSelect({ className, ...props }: ComponentProps<'select'>) {
  return (
    <div className="relative mt-1">
      <select data-slot="native-select" className={cn(inputClass, 'appearance-none pr-9', className)} {...props} />
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground"
      />
    </div>
  )
}
