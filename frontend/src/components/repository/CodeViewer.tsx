import { useEffect, useMemo, useRef, useState } from 'react'

import { cn } from '../../lib/cn'

/** Showing tens of thousands of lines at once makes the page sluggish, so start with a window. */
const INITIAL_LINES = 3000
const EXTRA_LINES_AFTER_TARGET = 200

interface Props {
  content: string
  /** 1-based line to highlight and scroll to. */
  highlightLine: number | null
  onSelectLine: (line: number) => void
}

export default function CodeViewer({ content, highlightLine, onSelectLine }: Props) {
  const lines = useMemo(() => content.split('\n'), [content])
  // A trailing newline would otherwise show up as an empty last line.
  const lineCount = lines.length > 1 && lines[lines.length - 1] === '' ? lines.length - 1 : lines.length

  const [showAll, setShowAll] = useState(false)
  const limit = showAll ? lineCount : Math.min(lineCount, Math.max(INITIAL_LINES, (highlightLine ?? 0) + EXTRA_LINES_AFTER_TARGET))
  const targetRef = useRef<HTMLDivElement | null>(null)

  const containerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    // Scroll only inside the code panel. scrollIntoView would also scroll the whole page
    // and push the repository header and tabs out of sight.
    const container = containerRef.current
    const target = targetRef.current
    if (container && target) container.scrollTop = Math.max(0, target.offsetTop - container.clientHeight / 2)
  }, [highlightLine, content])

  return (
    <div
      ref={containerRef}
      className="relative max-h-[70vh] overflow-auto rounded-lg border border-line bg-canvas py-2 font-mono text-[13px] leading-6"
      role="region"
      aria-label="Source code"
      tabIndex={0}
    >
      {lines.slice(0, limit).map((text, index) => {
        const number = index + 1
        const highlighted = number === highlightLine
        return (
          <div
            key={number}
            ref={highlighted ? targetRef : undefined}
            data-highlighted={highlighted || undefined}
            className={cn(
              'flex min-w-max border-l-2',
              highlighted ? 'border-mark bg-mark/[0.12]' : 'border-transparent',
            )}
          >
            <button
              type="button"
              onClick={() => onSelectLine(number)}
              aria-label={`Highlight line ${number}`}
              className="w-14 shrink-0 pr-3 text-right text-faint select-none hover:text-ink"
            >
              {number}
            </button>
            <code className="pr-4 whitespace-pre">{text || ' '}</code>
          </div>
        )
      })}
      {limit < lineCount && (
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className="mt-2 ml-14 text-sm text-muted underline underline-offset-4 hover:text-ink"
        >
          Show the remaining {(lineCount - limit).toLocaleString('en')} lines
        </button>
      )}
    </div>
  )
}
