import { ArrowLeft, RotateCcw } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import type { MockInterview, Report, Turn } from '../../api/mock'
import GradeView, { ClaimList } from '../../components/mock/GradeView'
import { buttonClass } from '../../components/ui/button'
import { useInterview, useInterviewActions } from '../../hooks/useMock'
import { useRepositoryContext } from '../../hooks/useRepositoryContext'
import { cn } from '../../lib/cn'
import { fileLink } from '../../lib/links'

/** Minutes and seconds since the question was asked: interviews have a pace. */
function Elapsed({ since }: { since: string }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  const seconds = Math.max(0, Math.floor((now - new Date(since).getTime()) / 1000))
  const text = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
  return (
    <span className="font-mono text-xs text-faint" aria-label={`Time on this question: ${text}`}>
      {text}
    </span>
  )
}

function AnswerBox({ repositoryId, interview, turn }: { repositoryId: string; interview: MockInterview; turn: Turn }) {
  const { answer, skip } = useInterviewActions(repositoryId, interview.id)
  const [text, setText] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    if (text.trim()) answer.mutate(text.trim(), { onSuccess: () => setText('') })
  }

  return (
    <form onSubmit={submit} className="mt-3">
      <div className="mb-1 flex items-baseline justify-between">
        <label htmlFor={`answer-${turn.id}`} className="text-xs text-muted">
          Your answer
        </label>
        {turn.asked_at && <Elapsed since={turn.asked_at} />}
      </div>
      <textarea
        id={`answer-${turn.id}`}
        value={text}
        onChange={(event) => setText(event.target.value)}
        rows={6}
        maxLength={6000}
        autoFocus
        placeholder="Answer as you would out loud: what it does, how, and why it was built that way."
        className="block w-full resize-y rounded-md border border-line bg-canvas px-3 py-2 text-[15px] leading-relaxed placeholder:text-faint focus:border-mark focus:outline-none"
      />
      <div className="mt-2.5 flex flex-wrap gap-2">
        <button type="submit" disabled={!text.trim() || answer.isPending} className={buttonClass('primary', 'h-9')}>
          Submit answer
        </button>
        <button type="button" onClick={() => skip.mutate()} disabled={skip.isPending} className={buttonClass('ghost', 'h-9')}>
          Skip this question
        </button>
      </div>
      {(answer.isError || skip.isError) && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {(answer.error ?? skip.error)?.message}
        </p>
      )}
    </form>
  )
}

function TurnView({ repositoryId, interview, turn, number }: { repositoryId: string; interview: MockInterview; turn: Turn; number: number }) {
  const { retry } = useInterviewActions(repositoryId, interview.id)
  const followUp = turn.kind === 'follow_up'

  return (
    <li className={cn('border-t border-line py-6 first:border-t-0 first:pt-0', followUp && 'ml-4 border-l border-l-line pl-5 sm:ml-8')}>
      <p className="mb-1 text-xs text-muted">{followUp ? 'Follow-up' : `Question ${number} of ${interview.question_count}`}</p>
      <h3 className="text-lg leading-snug font-semibold">{turn.prompt}</h3>

      {turn.status === 'waiting' && <AnswerBox repositoryId={repositoryId} interview={interview} turn={turn} />}
      {turn.answer && (
        <blockquote className="mt-3 border-l-2 border-line pl-3 text-sm whitespace-pre-wrap text-ink/80">{turn.answer}</blockquote>
      )}
      {turn.status === 'grading' && (
        <p role="status" className="mt-3 flex items-center gap-2.5 text-sm text-muted">
          <span className="size-2 shrink-0 animate-pulse rounded-full bg-hint" aria-hidden="true" />
          Checking your answer against the code…
        </p>
      )}
      {turn.status === 'skipped' && <p className="mt-2 text-sm text-muted">Skipped.</p>}
      {turn.status === 'cancelled' && <p className="mt-2 text-sm text-muted">Not answered: the interview ended.</p>}
      {turn.status === 'failed' && (
        <div role="alert" className="mt-3 text-sm">
          <p className="text-danger">{turn.error_message ?? 'This answer could not be graded.'}</p>
          <button
            type="button"
            onClick={() => retry.mutate(turn.id)}
            disabled={retry.isPending}
            className={buttonClass('secondary', 'mt-2 h-8 px-3 text-xs')}
          >
            <RotateCcw size={13} aria-hidden="true" />
            Grade it again
          </button>
        </div>
      )}
      {turn.grade && (
        <div className="mt-4">
          <GradeView repositoryId={repositoryId} grade={turn.grade} />
        </div>
      )}
    </li>
  )
}

function ReportView({ repositoryId, report }: { repositoryId: string; report: Report }) {
  return (
    <section aria-labelledby="report-heading" className="mb-8 rounded-xl border border-line bg-surface p-5">
      <h2 id="report-heading" className="sr-only">
        Interview report
      </h2>
      <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
        <p>
          <span className="block text-5xl font-semibold tracking-tight">
            {report.percent ?? 0}
            <span className="text-2xl text-muted">%</span>
          </span>
          <span className="text-sm text-muted">
            {report.questions_answered} {report.questions_answered === 1 ? 'question' : 'questions'}
            {report.skipped > 0 && `, ${report.skipped} skipped`}
            {report.follow_ups_answered > 0 &&
              `, ${report.follow_ups_answered} ${report.follow_ups_answered === 1 ? 'follow-up' : 'follow-ups'}`}
          </span>
        </p>
        {report.by_category.length > 0 && (
          <ul aria-label="By topic" className="min-w-56 flex-1 space-y-1.5">
            {report.by_category.map((item) => (
              <li key={item.category} className="grid grid-cols-[9rem_1fr_2.5rem] items-center gap-2 text-sm">
                <span className="truncate text-muted">{item.label}</span>
                <span className="h-1.5 overflow-hidden rounded-full bg-raised">
                  <span
                    className={cn('block h-full', (item.average ?? 0) >= 3 ? 'bg-ok' : 'bg-mark')}
                    style={{ width: `${((item.average ?? 0) / 4) * 100}%` }}
                  />
                </span>
                <span className="text-right font-mono text-xs text-faint">{item.average?.toFixed(1)}/4</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        {report.gaps.length > 0 && (
          <div>
            <h3 className="text-sm font-medium">What to work on</h3>
            <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm marker:text-faint">
              {report.gaps.map((gap, i) => (
                <li key={i}>{gap}</li>
              ))}
            </ul>
          </div>
        )}
        {report.strengths.length > 0 && (
          <div>
            <h3 className="text-sm font-medium">What you did well</h3>
            <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm marker:text-faint">
              {report.strengths.map((strength, i) => (
                <li key={i}>{strength}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {report.contradicted_claims.length > 0 && (
        <div className="mt-6">
          <h3 className="mb-2 text-sm font-medium">Statements the code contradicts</h3>
          <ClaimList repositoryId={repositoryId} claims={report.contradicted_claims} />
        </div>
      )}
      {report.files_to_review.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-medium">Read these files next</h3>
          <ul className="mt-1.5 space-y-1">
            {report.files_to_review.map((path) => (
              <li key={path}>
                <Link to={fileLink(repositoryId, path)} className="font-mono text-[13px] text-mark hover:underline">
                  {path}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

export default function MockInterviewPage() {
  const { repository } = useRepositoryContext()
  const { interviewId = '' } = useParams()
  const { data: interview, isPending, isError } = useInterview(repository.id, interviewId)
  const { finish, remove } = useInterviewActions(repository.id, interviewId)
  const navigate = useNavigate()
  const back = `/repositories/${repository.id}/interview`

  const header = (
    <Link to={back} className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
      <ArrowLeft size={15} aria-hidden="true" />
      Interview preparation
    </Link>
  )

  if (isPending) {
    return (
      <div>
        {header}
        <p role="status" className="text-sm text-muted">
          Loading the interview…
        </p>
      </div>
    )
  }
  if (isError) {
    return (
      <div>
        {header}
        <p role="alert" className="text-sm text-danger">
          This interview could not be opened. It may have been deleted.
        </p>
      </div>
    )
  }

  const grading = interview.turns.some((t) => t.status === 'grading')
  // "Question 2 of 5": follow-ups do not count as questions.
  const numbers = interview.turns.map(
    (_, index) => interview.turns.slice(0, index + 1).filter((t) => t.kind === 'question').length,
  )

  return (
    <div className="max-w-3xl">
      {header}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Mock interview</h2>
        {interview.status === 'active' ? (
          <button
            type="button"
            onClick={() => finish.mutate()}
            disabled={finish.isPending || grading}
            className={buttonClass('secondary', 'h-9 px-3')}
            title={grading ? 'Wait for the last answer to be graded' : undefined}
          >
            End the interview
          </button>
        ) : (
          interview.status !== 'preparing' && (
            <button
              type="button"
              onClick={() => remove.mutate(undefined, { onSuccess: () => navigate(back) })}
              disabled={remove.isPending}
              className={buttonClass('ghost', 'h-9 px-3')}
            >
              Delete this interview
            </button>
          )
        )}
      </div>
      {(finish.isError || remove.isError) && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {(finish.error ?? remove.error)?.message}
        </p>
      )}

      {interview.status === 'preparing' && (
        <p role="status" className="flex items-center gap-2.5 rounded-xl border border-line bg-surface px-4 py-3 text-sm text-muted">
          <span className="size-2 shrink-0 animate-pulse rounded-full bg-hint" aria-hidden="true" />
          Writing questions from the code first. This usually takes 10 to 30 seconds.
        </p>
      )}
      {interview.status === 'failed' && (
        <p role="alert" className="text-sm text-danger">
          {interview.error_message ?? 'The interview could not be prepared.'}
        </p>
      )}
      {interview.report && <ReportView repositoryId={repository.id} report={interview.report} />}

      <ol>
        {interview.turns.map((turn, index) => (
          <TurnView key={turn.id} repositoryId={repository.id} interview={interview} turn={turn} number={numbers[index]} />
        ))}
      </ol>
    </div>
  )
}
