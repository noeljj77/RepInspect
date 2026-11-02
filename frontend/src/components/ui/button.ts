import { cn } from '../../lib/cn'

type Variant = 'primary' | 'secondary' | 'ghost'

const variants: Record<Variant, string> = {
  primary: 'bg-mark text-mark-ink hover:bg-[#f6cf6f] font-semibold',
  secondary: 'border border-line bg-surface text-ink hover:border-faint',
  ghost: 'text-muted hover:text-ink',
}

/**
 * Class names for anything that should look like a button, including
 * router <Link>s, so we don't need a polymorphic Button component.
 */
export function buttonClass(variant: Variant = 'primary', extra?: string): string {
  return cn(
    'inline-flex items-center justify-center gap-2 rounded-md px-4 h-10 text-sm transition-colors',
    'disabled:cursor-not-allowed disabled:opacity-50',
    variants[variant],
    extra,
  )
}
