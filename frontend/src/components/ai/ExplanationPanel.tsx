import { RefreshCw, Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'

import type { AiKind, ContentByKind, Explanation } from '../../api/ai'
import { useAiExplanation, useRequestExplanation } from '../../hooks/useAiExplanation'
import { formatRelativeTime } from '../../lib/format'
import { buttonClass } from '../ui/button'

function Footer({ explanation, onRegenerate, busy }: { explanation: Explanation; onRegenerate: () => void; busy: boolean }) {
  const content = explanation.content
  const removed = content && 'removed_citations' in content ? content.removed_citations : null
  const when = explanation.completed_at ? `, ${formatRelativeTime(explanation.completed_at)}` : ''

  return (
    <footer className="mt-5 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-line pt-3 text-xs text-faint">
      <p>
        {removed !== null &&
          (removed > 0
            ? `Checked against the code; ${removed} ${removed === 1 ? 'reference' : 'references'} that could not be confirmed ${removed === 1 ? 'was' : 'were'} removed. `
            : 'Checked against the code. ')}
        Written by {explanation.model ?? 'an AI model'}
        {when}.
      </p>
      <button type="button" onClick={onRegenerate} disabled={busy} className={buttonClass('ghost', 'h-8 px-2 text-xs')}>
        <RefreshCw size={13} aria-hidden="true" />
        Regenerate
      </button>
    </footer>
  )
}

interface Props<K extends AiKind> {
  repositoryId: string
  kind: K
  path?: string
  /** Shown before anything has been requested. */
  intro: ReactNode
  actionLabel: string
  children: (content: ContentByKind[K]) => ReactNode
}

/**
 * Everything around an AI explanation: asking for it, waiting, failures, and the
 * note on how it was checked. The caller only renders the finished content.
 */
export default function ExplanationPanel<K extends AiKind>({
  repositoryId,
  kind,
  path,
  intro,
  actionLabel,
  children,
}: Props<K>) {
  const query = useAiExplanation(repositoryId, kind, path)
  const request = useRequestExplanation(repositoryId, kind, path)
  const start = () => request.mutate()
  const busy = request.isPending

  const requestError = request.isError && (
    <p role="alert" className="mt-3 text-sm text-danger">
      {request.error.message}
    </p>
  )

  if (query.isPending) {
    return (
      <p role="status" className="text-sm text-muted">
        Checking for an earlier explanation…
      </p>
    )
  }
  if (query.isError) {
    return (
      <p role="alert" className="text-sm text-danger">
        The explanation could not be loaded. Try refreshing the page.
      </p>
    )
  }

  const explanation = query.data

  if (explanation.status === 'pending') {
    return (
      <p role="status" className="flex items-center gap-2.5 text-sm text-muted">
        <span className="size-2 shrink-0 animate-pulse rounded-full bg-hint" aria-hidden="true" />
        Reading the code and writing the explanation. This usually takes 10 to 30 seconds.
      </p>
    )
  }

  if (explanation.status === 'completed' && explanation.content) {
    return (
      <div>
        {children(explanation.content)}
        <Footer explanation={explanation} onRegenerate={start} busy={busy} />
        {requestError}
      </div>
    )
  }

  const failed = explanation.status !== 'missing'
  return (
    <div>
      {failed ? (
        <p role="alert" className="text-sm text-danger">
          {explanation.error_message ?? 'The explanation could not be written.'}
        </p>
      ) : (
        <div className="max-w-prose text-sm text-muted">{intro}</div>
      )}
      <button type="button" onClick={start} disabled={busy} className={buttonClass('secondary', 'mt-3 h-9')}>
        <Sparkles size={15} className="text-hint" aria-hidden="true" />
        {failed ? 'Try again' : actionLabel}
      </button>
      {requestError}
    </div>
  )
}
