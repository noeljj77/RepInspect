import { Search } from 'lucide-react'

import type { SearchIndex } from '../../api/chat'
import { useBuildIndex } from '../../hooks/useChat'
import { buttonClass } from '../ui/button'

/** Shown instead of the chat until the repository's search index is ready. */
export default function IndexPanel({ repositoryId, index }: { repositoryId: string; index: SearchIndex }) {
  const build = useBuildIndex(repositoryId)
  const action = (label: string) => (
    <button
      type="button"
      onClick={() => build.mutate()}
      disabled={build.isPending}
      className={buttonClass('primary', 'mt-4')}
    >
      <Search size={16} aria-hidden="true" />
      {label}
    </button>
  )

  if (index.status === 'pending' || index.status === 'building') {
    const total = index.chunk_count
    const done = index.chunks_embedded
    return (
      <section aria-labelledby="index-heading" className="max-w-xl">
        <h2 id="index-heading" className="font-semibold">
          Preparing chat
        </h2>
        <p className="mt-1.5 text-sm text-muted">
          The code is being split into functions, classes and sections, and each part is turned into a vector
          so questions can find it by meaning. This runs once per import.
        </p>
        <div
          role="progressbar"
          aria-label="Indexing progress"
          aria-valuemin={0}
          aria-valuemax={total || 1}
          aria-valuenow={done}
          className="mt-4 h-1.5 overflow-hidden rounded-full bg-raised"
        >
          <div
            className="h-full rounded-full bg-mark transition-[width] duration-500"
            style={{ width: total ? `${Math.round((done / total) * 100)}%` : '4%' }}
          />
        </div>
        <p role="status" className="mt-2 text-sm text-muted">
          {total
            ? `${done.toLocaleString('en')} of ${total.toLocaleString('en')} parts indexed`
            : 'Reading the files…'}
        </p>
      </section>
    )
  }

  return (
    <section aria-labelledby="index-heading" className="max-w-xl rounded-xl border border-dashed border-line px-6 py-8">
      <h2 id="index-heading" className="font-semibold">
        {index.status === 'failed' ? 'The search index could not be built' : 'Chat needs a search index'}
      </h2>
      {index.status === 'failed' ? (
        <p role="alert" className="mt-1.5 text-sm text-danger">
          {index.error_message}
        </p>
      ) : (
        <p className="mt-1.5 text-sm text-muted">
          Imports made before chat existed do not have one yet. Building it reads every file once and takes
          about a minute for a mid-sized repository.
        </p>
      )}
      {index.error_code !== 'nothing_to_index' &&
        action(index.status === 'failed' ? 'Try again' : 'Build the search index')}
      {build.isError && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {build.error.message}
        </p>
      )}
    </section>
  )
}
