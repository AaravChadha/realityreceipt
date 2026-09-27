import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Join class names, letting a later Tailwind class win over an earlier one it conflicts with. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
