import { Trash2 } from 'lucide-react'
import { useId, useState } from 'react'

import { CATEGORY_LABELS, type Progress, type Question } from '../../api/interview'
import { useDeleteQuestion, useUpdateQuestion } from '../../hooks/useInterview'
import { cn } from '../../lib/cn'
import { FindingList } from '../ai/Findings'
import { buttonClass } from '../ui/button'

const PROGRESS: Array<{ value: Progress; label: string }> = [
  { value: 'new', label: 'New' },
  { value: 'practicing', label: 'Practicing' },
  { value: 'confident', label: 'Confident' },
]

const DIFFICULTY_LABELS = { basic: 'Basic', intermediate: 'Intermediate', advanced: 'Advanced' }

export default function QuestionCard({
  repositoryId,
  question,
  currentVersion,
}: {
  repositoryId: string
  question: Question
  /** The version on screen: older questions may point at lines that have moved. */
  currentVersion: number
}) {
  const update = useUpdateQuestion(repositoryId)
  const remove = useDeleteQuestion(repositoryId)
  const [draft, setDraft] = useState(question.user_answer ?? '')
  const id = useId()
  const dirty = draft.trim() !== (question.user_answer ?? '')

  return (
    <article aria-labelledby={`${id}-q`} className="border-t border-line py-5 first:border-t-0 first:pt-0">
      <div className="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
        <span>{CATEGORY_LABELS[question.category] ?? question.category}</span>
        <span aria-hidden="true" className="text-faint">/</span>
        <span>{DIFFICULTY_LABELS[question.difficulty] ?? question.difficulty}</span>
        {question.analysis_version < currentVersion && (
          <span className="text-faint">written for version {question.analysis_version}</span>
        )}
      </div>
      <h3 id={`${id}-q`} className="text-[17px] leading-snug font-semibold">
        {question.question}
      </h3>
      {question.why_asked && <p className="mt-1 text-sm text-muted">{question.why_asked}</p>}

      <details className="mt-3 group">
        <summary className="cursor-pointer text-sm text-muted hover:text-ink">What a strong answer covers</summary>
        <div className="mt-3 space-y-3">
          {!question.grounded && (
            <p className="border-l-2 border-dashed border-hint/70 pl-3 text-sm text-hint">
              None of these points could be confirmed in the code. Treat them as a guess.
            </p>
          )}
          <FindingList repositoryId={repositoryId} findings={question.answer_points} />
          {question.follow_ups.length > 0 && (
            <div>
              <h4 className="text-xs text-muted">Likely follow-ups</h4>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm marker:text-faint">
                {question.follow_ups.map((followUp, index) => (
                  <li key={index}>{followUp}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </details>

      <div className="mt-3">
        <label htmlFor={`${id}-answer`} className="text-xs text-muted">
          Your answer
        </label>
        <textarea
          id={`${id}-answer`}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          rows={3}
          maxLength={10_000}
          placeholder="Write your answer in your own words, then compare it with the points above."
          className="mt-1 block w-full resize-y rounded-md border border-line bg-canvas px-3 py-2 text-sm leading-relaxed placeholder:text-faint focus:border-mark focus:outline-none"
        />
      </div>

      <div className="mt-2.5 flex flex-wrap items-center justify-between gap-3">
        <div role="radiogroup" aria-label="Progress" className="inline-flex rounded-md border border-line p-0.5">
          {PROGRESS.map((option) => {
            const active = question.status === option.value
            return (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={active}
                disabled={update.isPending}
                onClick={() => !active && update.mutate({ id: question.id, status: option.value })}
                className={cn(
                  'rounded px-2.5 py-1 text-xs',
                  active
                    ? option.value === 'confident'
                      ? 'bg-ok/15 text-ok'
                      : 'bg-raised text-ink'
                    : 'text-muted hover:text-ink',
                )}
              >
                {option.label}
              </button>
            )
          })}
        </div>
        <div className="flex items-center gap-2">
          {dirty && (
            <button
              type="button"
              onClick={() => update.mutate({ id: question.id, user_answer: draft.trim() || null })}
              disabled={update.isPending}
              className={buttonClass('secondary', 'h-8 px-3 text-xs')}
            >
              Save answer
            </button>
          )}
          <button
            type="button"
            onClick={() => remove.mutate(question.id)}
            disabled={remove.isPending}
            aria-label="Delete question"
            title="Delete this question"
            className={buttonClass('ghost', 'h-8 px-2')}
          >
            <Trash2 size={14} aria-hidden="true" />
          </button>
        </div>
      </div>
      {(update.isError || remove.isError) && (
        <p role="alert" className="mt-2 text-xs text-danger">
          {(update.error ?? remove.error)?.message}
        </p>
      )}
    </article>
  )
}
