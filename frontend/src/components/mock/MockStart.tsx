import { Play } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'

import type { Difficulty } from '../../api/interview'
import { useInterviews, useStartInterview } from '../../hooks/useMock'
import { formatRelativeTime } from '../../lib/format'
import { buttonClass } from '../ui/button'

const STATUS_TEXT = { preparing: 'Preparing', active: 'In progress', completed: 'Finished', failed: 'Failed' }

/** Start a mock interview, and see earlier ones. Shown at the top of the Interview tab. */
export default function MockStart({ repositoryId }: { repositoryId: string }) {
  const { data: interviews = [] } = useInterviews(repositoryId)
  const start = useStartInterview(repositoryId)
  const navigate = useNavigate()
  const [count, setCount] = useState(5)
  const [difficulty, setDifficulty] = useState<Difficulty | ''>('')
  const open = interviews.find((i) => i.status === 'active' || i.status === 'preparing')
  const link = (id: string) => `/repositories/${repositoryId}/interview/mock/${id}`

  function submit(event: FormEvent) {
    event.preventDefault()
    start.mutate(
      { question_count: count, difficulty: difficulty || null },
      { onSuccess: (interview) => navigate(link(interview.id)) },
    )
  }

  return (
    <section aria-labelledby="mock-heading" className="rounded-xl border border-mark/25 bg-surface p-5">
      <h2 id="mock-heading" className="font-semibold">
        Mock interview
      </h2>
      <p className="mt-1 max-w-2xl text-sm text-muted">
        Questions one at a time, with no hints. Each answer is graded against the code: what you got right, what you
        missed, and any statement the code contradicts. A follow-up may probe your weakest point. Uses your practice
        questions, and writes more if there are too few.
      </p>

      {open ? (
        <Link to={link(open.id)} className={buttonClass('primary', 'mt-4')}>
          <Play size={15} aria-hidden="true" />
          Continue your interview
        </Link>
      ) : (
        <form onSubmit={submit} className="mt-4 flex flex-wrap items-end gap-3">
          <label className="text-xs text-muted">
            Questions
            <select
              value={count}
              onChange={(event) => setCount(Number(event.target.value))}
              className="mt-1 block h-9 rounded-md border border-line bg-canvas px-2 text-sm text-ink"
            >
              {[3, 5, 8].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-muted">
            Level
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
          <button type="submit" disabled={start.isPending} className={buttonClass('primary', 'h-9')}>
            <Play size={15} aria-hidden="true" />
            Start the interview
          </button>
        </form>
      )}
      {start.isError && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {start.error.message}
        </p>
      )}

      {interviews.length > 0 && (
        <div className="mt-5 border-t border-line pt-4">
          <h3 className="mb-2 text-sm text-muted">Earlier interviews</h3>
          <ul className="space-y-1">
            {interviews.map((interview) => (
              <li key={interview.id}>
                <Link
                  to={link(interview.id)}
                  className="flex items-baseline justify-between gap-3 rounded-md px-2 py-1.5 text-sm hover:bg-raised/60"
                >
                  <span>
                    {interview.question_count} questions, {formatRelativeTime(interview.created_at)}
                  </span>
                  <span className="text-muted">
                    {interview.status === 'completed' && interview.percent !== null
                      ? `${interview.percent}%`
                      : STATUS_TEXT[interview.status]}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
