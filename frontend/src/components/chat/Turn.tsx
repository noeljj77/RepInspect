import { RotateCcw } from 'lucide-react'
import { Link } from 'react-router'

import type { ChatMessage, Source } from '../../api/chat'
import { cn } from '../../lib/cn'
import { fileLink } from '../../lib/links'
import { CitationLink, UngroundedPaths } from '../ai/Findings'
import { buttonClass } from '../ui/button'
import AnswerText from './AnswerText'
import WorkingNote from '../ui/WorkingNote'

const MATCH_LABELS: Record<string, string> = {
  meaning: 'similar meaning',
  keywords: 'same words',
  name: 'named in the question',
}

function Searched({ repositoryId, sources }: { repositoryId: string; sources: Source[] }) {
  if (sources.length === 0) return null
  return (
    <details className="text-sm">
      <summary className="cursor-pointer text-muted hover:text-ink">
        Searched {sources.length} {sources.length === 1 ? 'part' : 'parts'} of the code
      </summary>
      <ul className="mt-2 space-y-1.5 border-l border-line pl-3">
        {sources.map((source) => (
          <li key={`${source.path}:${source.start_line}`} className="flex flex-wrap items-baseline gap-x-2">
            <Link
              to={fileLink(repositoryId, source.path, source.start_line)}
              className="font-mono text-[13px] text-ink/85 hover:text-mark-text hover:underline"
            >
              {source.path}:{source.start_line}–{source.end_line}
            </Link>
            {source.symbol && <span className="font-mono text-[12px] text-muted">{source.symbol}</span>}
            <span className="text-xs text-faint">
              found by {source.matched_by.map((m) => MATCH_LABELS[m] ?? m).join(', ')}
            </span>
          </li>
        ))}
      </ul>
    </details>
  )
}

function Answer({
  repositoryId,
  message,
  canRetry,
  onRetry,
  retrying,
}: {
  repositoryId: string
  message: ChatMessage
  canRetry: boolean
  onRetry: () => void
  retrying: boolean
}) {
  if (message.status === 'pending') {
    return (
      <WorkingNote expected={20}>Searching the code and writing an answer…</WorkingNote>
    )
  }
  if (message.status === 'failed' || !message.details) {
    return (
      <div>
        <p role="alert" className="text-sm text-danger">
          {message.error_message ?? 'No answer could be written.'}
        </p>
        {canRetry && (
          <button
            type="button"
            onClick={onRetry}
            disabled={retrying}
            className={buttonClass('secondary', 'mt-2.5 h-8 px-3 text-xs')}
          >
            <RotateCcw size={13} aria-hidden="true" />
            Try again
          </button>
        )}
      </div>
    )
  }

  const { answerable, citations, removed_citations, ungrounded_paths, sources } = message.details
  const unsupported = answerable && citations.length === 0
  return (
    <div className="space-y-4">
      <div className={cn(!answerable && 'border-l-2 border-dashed border-hint/70 pl-3')}>
        {!answerable && <p className="mb-1.5 text-xs text-hint">Not found in the code that was searched</p>}
        <AnswerText text={message.content} citations={citations} repositoryId={repositoryId} />
      </div>

      {unsupported && (
        <p className="border-l-2 border-dashed border-hint/70 pl-3 text-sm text-hint">
          No part of this answer could be confirmed in the code. Treat it as a suggestion.
        </p>
      )}

      {citations.length > 0 && (
        <div>
          <h4 className="mb-1.5 text-xs text-muted">Sources</h4>
          <div className="grid gap-1.5">
            {citations.map((citation, index) => (
              <CitationLink
                key={index}
                repositoryId={repositoryId}
                citation={citation}
                label={`[${index + 1}]`}
              />
            ))}
          </div>
        </div>
      )}

      <UngroundedPaths paths={ungrounded_paths} />
      <Searched repositoryId={repositoryId} sources={sources} />
      {removed_citations > 0 && (
        <p className="text-xs text-faint">
          {removed_citations} {removed_citations === 1 ? 'reference' : 'references'} that could not be confirmed in
          the code {removed_citations === 1 ? 'was' : 'were'} removed.
        </p>
      )}
    </div>
  )
}

/** One question and its answer. */
export default function Turn({
  repositoryId,
  question,
  answer,
  canRetry,
  onRetry,
  retrying,
}: {
  repositoryId: string
  question: ChatMessage
  answer: ChatMessage | undefined
  canRetry: boolean
  onRetry: (messageId: string) => void
  retrying: boolean
}) {
  return (
    <article className="border-t border-line py-6 first:border-t-0 first:pt-0">
      <h3 className="mb-3 text-[17px] font-semibold leading-snug whitespace-pre-wrap">{question.content}</h3>
      {answer && (
        <Answer
          repositoryId={repositoryId}
          message={answer}
          canRetry={canRetry}
          onRetry={() => onRetry(answer.id)}
          retrying={retrying}
        />
      )}
    </article>
  )
}
