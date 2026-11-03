import { Sparkles } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { CATEGORY_LABELS, type Category, type Difficulty, type Progress, type Questions } from '../../api/interview'
import QuestionCard from '../../components/interview/QuestionCard'
import ReportView from '../../components/interview/ReportView'
import { buttonClass } from '../../components/ui/button'
import { useGenerateQuestions, useQuestions } from '../../hooks/useInterview'
import { useRepositoryContext } from '../../hooks/useRepositoryContext'
import { cn } from '../../lib/cn'

const CATEGORIES = Object.keys(CATEGORY_LABELS) as Category[]

function ProgressBar({ progress }: { progress: Questions['progress'] }) {
  const total = progress.new + progress.practicing + progress.confident
  if (total === 0) return null
  const width = (n: number) => `${(n / total) * 100}%`
  return (
    <div>
      <div
        role="img"
        aria-label={`${progress.confident} confident, ${progress.practicing} practicing, ${progress.new} new`}
        className="flex h-1.5 overflow-hidden rounded-full bg-raised"
      >
        <div className="bg-ok" style={{ width: width(progress.confident) }} />
        <div className="bg-mark/70" style={{ width: width(progress.practicing) }} />
      </div>
      <p className="mt-1.5 text-sm text-muted">
        {progress.confident} of {total} confident, {progress.practicing} practicing
      </p>
    </div>
  )
}

function GenerateForm({ repositoryId, hasQuestions }: { repositoryId: string; hasQuestions: boolean }) {
  const generate = useGenerateQuestions(repositoryId)
  const [count, setCount] = useState(8)
  const [difficulty, setDifficulty] = useState<Difficulty | ''>('')
  const [categories, setCategories] = useState<Category[]>([])

  function toggle(category: Category) {
    setCategories((now) => (now.includes(category) ? now.filter((c) => c !== category) : [...now, category]))
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    generate.mutate({ count, difficulty: difficulty || null, categories: categories.length ? categories : null })
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-xl border border-line bg-surface p-4">
      <div role="group" aria-label="Topics" className="flex flex-wrap gap-1.5">
        {CATEGORIES.map((category) => {
          const active = categories.includes(category)
          return (
            <button
              key={category}
              type="button"
              aria-pressed={active}
              onClick={() => toggle(category)}
              className={cn(
                'rounded-full border px-2.5 py-0.5 text-xs',
                active ? 'border-mark/50 bg-mark/15 text-mark' : 'border-line text-muted hover:border-faint hover:text-ink',
              )}
            >
              {CATEGORY_LABELS[category]}
            </button>
          )
        })}
      </div>
      <p className="text-xs text-faint">{categories.length === 0 ? 'No topic picked: a mix of all of them.' : ''}</p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs text-muted">
          How many
          <select
            value={count}
            onChange={(event) => setCount(Number(event.target.value))}
            className="mt-1 block h-9 rounded-md border border-line bg-canvas px-2 text-sm text-ink"
          >
            {[5, 8, 12].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-muted">
          Difficulty
          <select
            value={difficulty}
            onChange={(event) => setDifficulty(event.target.value as Difficulty | '')}
            className="mt-1 block h-9 rounded-md border border-line bg-canvas px-2 text-sm text-ink"
          >
            <option value="">A mix</option>
            <option value="basic">Basic</option>
            <option value="intermediate">Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>
        </label>
        <button type="submit" disabled={generate.isPending} className={buttonClass('secondary', 'h-9')}>
          <Sparkles size={15} className="text-hint" aria-hidden="true" />
          {hasQuestions ? `Add ${count} more questions` : `Write ${count} questions`}
        </button>
      </div>
      {generate.isError && (
        <p role="alert" className="text-sm text-danger">
          {generate.error.message}
        </p>
      )}
    </form>
  )
}

const FILTERS: Array<{ value: Progress | 'all'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'new', label: 'New' },
  { value: 'practicing', label: 'Practicing' },
  { value: 'confident', label: 'Confident' },
]

function Practice({ repositoryId, version }: { repositoryId: string; version: number }) {
  const { data, isPending, isError } = useQuestions(repositoryId)
  const [filter, setFilter] = useState<Progress | 'all'>('all')

  if (isPending) {
    return (
      <p role="status" className="text-sm text-muted">
        Loading questions…
      </p>
    )
  }
  if (isError) {
    return (
      <p role="alert" className="text-sm text-danger">
        Your questions could not be loaded. Try refreshing the page.
      </p>
    )
  }

  const batch = data.latest_batch
  const shown = data.questions.filter((q) => filter === 'all' || q.status === filter)

  return (
    <div className="space-y-5">
      <ProgressBar progress={data.progress} />
      {batch?.status === 'pending' ? (
        <p role="status" className="flex items-center gap-2.5 rounded-xl border border-line bg-surface px-4 py-3 text-sm text-muted">
          <span className="size-2 shrink-0 animate-pulse rounded-full bg-hint" aria-hidden="true" />
          Writing {batch.requested_count} questions from the code. This usually takes 10 to 30 seconds.
        </p>
      ) : (
        <GenerateForm repositoryId={repositoryId} hasQuestions={data.questions.length > 0} />
      )}
      {batch?.status === 'failed' && (
        <p role="alert" className="text-sm text-danger">
          The last request failed: {batch.error_message}
        </p>
      )}

      {data.questions.length > 0 && (
        <>
          <div role="group" aria-label="Show questions" className="flex gap-1 border-b border-line">
            {FILTERS.map((option) => {
              const count = option.value === 'all' ? data.questions.length : data.progress[option.value]
              return (
                <button
                  key={option.value}
                  type="button"
                  aria-pressed={filter === option.value}
                  onClick={() => setFilter(option.value)}
                  className={cn(
                    '-mb-px border-b-2 px-3 py-2 text-sm',
                    filter === option.value ? 'border-mark text-ink' : 'border-transparent text-muted hover:text-ink',
                  )}
                >
                  {option.label} <span className="text-xs text-faint">{count}</span>
                </button>
              )
            })}
          </div>
          {shown.length === 0 ? (
            <p className="text-sm text-muted">No questions here yet.</p>
          ) : (
            <div>
              {shown.map((question) => (
                <QuestionCard key={question.id} repositoryId={repositoryId} question={question} currentVersion={version} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default function InterviewTab() {
  const { repository, analysis } = useRepositoryContext()

  return (
    <div className="space-y-10">
      <ReportView repositoryId={repository.id} />
      <section aria-labelledby="practice-heading" className="max-w-3xl">
        <h2 id="practice-heading" className="font-semibold">
          Practice questions
        </h2>
        <p className="mt-1 mb-4 text-sm text-muted">
          Questions an interviewer could ask about this code. Answer them in your own words, then mark how sure you
          feel. Your progress stays when you refresh the repository.
        </p>
        <Practice repositoryId={repository.id} version={analysis.version} />
      </section>
    </div>
  )
}
