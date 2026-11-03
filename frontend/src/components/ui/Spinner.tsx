import { cn } from '../../lib/cn'

/** A small spinning ring. Decorative: put the words next to it, in a role="status" element. */
export default function Spinner({
  size = 16,
  tone = 'mark',
  className,
}: {
  size?: number
  /** "hint" is for work done by the AI, to match the rest of the AI suggestions. */
  tone?: 'mark' | 'hint' | 'current'
  className?: string
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={cn(
        'shrink-0 animate-spin',
        tone === 'mark' && 'text-mark-text',
        tone === 'hint' && 'text-hint',
        className,
      )}
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.2" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}
