import { useState } from 'react'

import { cn } from '../../lib/cn'

const statuses = ['Not attempted', 'Understood', 'Needs revision'] as const
type Status = (typeof statuses)[number]

/** Example of a generated interview question, with a working status toggle. */
export default function QuestionPreview() {
  const [status, setStatus] = useState<Status>('Not attempted')

  return (
    <article className="rounded-xl border border-line bg-surface p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="rounded-full border border-line px-2.5 py-0.5 text-ink">Medium</span>
        <span className="text-muted">Authentication and security</span>
      </div>

      <h3 className="mt-4 text-lg font-semibold leading-snug">
        Why does <code className="font-mono text-[15px]">login</code> return the same error for an unknown email and a
        wrong password?
      </h3>

      <dl className="mt-5 space-y-3 text-[15px]">
        <div>
          <dt className="text-sm text-muted">Source</dt>
          <dd className="mt-0.5 font-mono text-[13px] text-mark">api/auth.py:14–16</dd>
        </div>
        <div>
          <dt className="text-sm text-muted">What the interviewer is testing</dt>
          <dd className="mt-0.5 text-ink/85">Whether you understand user enumeration and why vague errors help.</dd>
        </div>
      </dl>

      <div role="group" aria-label="Your progress" className="mt-6 flex flex-wrap gap-1 rounded-lg bg-canvas p-1">
        {statuses.map((option) => (
          <button
            key={option}
            type="button"
            aria-pressed={status === option}
            onClick={() => setStatus(option)}
            className={cn(
              'flex-1 rounded-md px-3 py-1.5 text-sm whitespace-nowrap transition-colors',
              status === option ? 'bg-raised text-ink' : 'text-muted hover:text-ink',
            )}
          >
            {option}
          </button>
        ))}
      </div>
    </article>
  )
}
