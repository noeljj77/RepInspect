import { Check } from 'lucide-react'

import type { AnalysisStatus } from '../../api/repositories'
import { cn } from '../../lib/cn'
import Spinner from '../ui/Spinner'

const steps: Array<{ status: AnalysisStatus; label: string; detail: string }> = [
  { status: 'queued', label: 'Waiting to start', detail: 'Your analysis is in the queue.' },
  { status: 'fetching', label: 'Downloading from GitHub', detail: 'Fetching repository details and the code.' },
  { status: 'extracting', label: 'Reading files', detail: 'Sorting out source files and skipping anything sensitive.' },
  { status: 'analyzing', label: 'Analyzing code', detail: 'Finding functions, classes, dependencies and frameworks.' },
]

export default function AnalysisProgress({
  status,
  sourceType = 'github',
}: {
  status: AnalysisStatus
  sourceType?: 'github' | 'zip'
}) {
  // Uploaded ZIPs skip the download step.
  const shown = sourceType === 'zip' ? steps.filter((step) => step.status !== 'fetching') : steps
  const current = shown.findIndex((step) => step.status === status)

  return (
    <section aria-label="Analysis progress" className="rounded-xl border border-line bg-surface p-6">
      <h2 className="font-semibold">Analyzing this repository</h2>
      <p className="mt-1 text-sm text-muted">This usually takes under a minute. You can leave this page and come back.</p>

      {/* One segment per step: finished ones are solid, the current one keeps moving. */}
      <div aria-hidden="true" className="mt-5 flex gap-1.5">
        {shown.map((step, index) => (
          <span key={step.status} className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-raised">
            {index < current && <span className="absolute inset-0 rounded-full bg-ok" />}
            {index === current && (
              <span className="bar-indeterminate absolute inset-0 block text-mark">
                <span />
              </span>
            )}
          </span>
        ))}
      </div>

      <ol className="mt-5 space-y-4" aria-live="polite">
        {shown.map((step, index) => {
          const done = index < current
          const active = index === current
          return (
            <li key={step.status} className="flex gap-3" aria-current={active ? 'step' : undefined}>
              <span
                className={cn(
                  'mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border',
                  done && 'border-ok/40 text-ok',
                  active && 'border-mark/40 text-mark-text',
                  !done && !active && 'border-line text-faint',
                )}
              >
                {done ? (
                  <Check size={12} strokeWidth={2.5} aria-hidden="true" />
                ) : active ? (
                  <Spinner size={13} tone="current" />
                ) : null}
              </span>
              <div>
                <p className={cn('text-sm font-medium', !done && !active && 'text-muted')}>
                  {step.label}
                  <span className="sr-only">{done ? ' (done)' : active ? ' (in progress)' : ''}</span>
                </p>
                {active && <p className="mt-0.5 text-sm text-muted">{step.detail}</p>}
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
