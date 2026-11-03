import { useEffect, useState, type ReactNode } from 'react'

import { cn } from '../../lib/cn'
import { estimatedProgress } from '../../lib/progress'
import Spinner from './Spinner'

/** Seconds since the component appeared, updated four times a second. */
function useElapsedSeconds(): number {
  const [start] = useState(() => Date.now())
  const [now, setNow] = useState(start)
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 250)
    return () => window.clearInterval(timer)
  }, [])
  return (now - start) / 1000
}

/**
 * Something the AI is working on, with a bar that fills towards the usual time and a clock,
 * so a wait of 10 to 30 seconds has something to watch. The bar is an estimate: it slows down
 * rather than claim to be finished, and the note says so when the job is taking longer than usual.
 */
export default function WorkingNote({
  children,
  expected = 30,
  boxed = false,
  className,
}: {
  children: ReactNode
  /** The usual time in seconds. */
  expected?: number
  /** Draw a border and background around it, for notes that sit on their own. */
  boxed?: boolean
  className?: string
}) {
  const elapsed = useElapsedSeconds()
  const slow = elapsed > expected * 1.5
  const percent = Math.round(estimatedProgress(elapsed, expected) * 100)

  return (
    <div
      role="status"
      className={cn(
        'flex flex-wrap items-center gap-x-2.5 gap-y-2.5 text-sm text-muted',
        boxed && 'rounded-xl border border-line bg-surface px-4 py-3',
        className,
      )}
    >
      <Spinner size={15} tone="hint" />
      {children}
      <span aria-hidden="true" className="ml-auto font-mono text-xs text-faint tabular-nums">
        {Math.floor(elapsed)}s
      </span>
      <span
        aria-hidden="true"
        className="relative h-1 w-full basis-full overflow-hidden rounded-full bg-raised"
      >
        {slow ? (
          <span className="bar-indeterminate absolute inset-0 block text-hint">
            <span />
          </span>
        ) : (
          <span
            className="bar-live block h-full rounded-full bg-hint transition-[width] duration-300 ease-out"
            style={{ width: `${percent}%` }}
          />
        )}
      </span>
      {slow && <span className="basis-full text-xs text-faint">Taking a little longer than usual. It is still working.</span>}
    </div>
  )
}
