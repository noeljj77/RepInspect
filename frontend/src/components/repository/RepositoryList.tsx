import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router'

import { useRepositories } from '../../hooks/useRepositories'
import { formatRelativeTime } from '../../lib/format'
import StatusBadge from './StatusBadge'

export default function RepositoryList() {
  const { data, isPending, isError, refetch } = useRepositories()

  if (isPending) {
    return (
      <p role="status" className="text-sm text-muted">
        Loading your repositories…
      </p>
    )
  }

  if (isError) {
    return (
      <div role="alert" className="text-sm">
        <p className="text-danger">Your repositories could not be loaded.</p>
        <button type="button" onClick={() => void refetch()} className="mt-2 text-muted underline underline-offset-4 hover:text-ink">
          Try again
        </button>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-line px-6 py-8">
        <h3 className="font-semibold">No repositories yet</h3>
        <p className="mt-1.5 max-w-md text-sm text-muted">
          Paste a GitHub link above. Repositories you analyze are saved here so you can come back to them.
        </p>
      </div>
    )
  }

  return (
    <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
      {data.map((repository) => (
        <li key={repository.id}>
          <Link
            to={`/repositories/${repository.id}`}
            className="flex items-center gap-4 px-5 py-4 transition-colors hover:bg-raised/60"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">
                {repository.owner ? `${repository.owner}/` : ''}
                {repository.name}
              </p>
              <p className="mt-0.5 truncate text-sm text-muted">
                {repository.description ?? `Added ${formatRelativeTime(repository.created_at)}`}
              </p>
            </div>
            {repository.latest_analysis && <StatusBadge status={repository.latest_analysis.status} />}
            <ChevronRight size={16} className="shrink-0 text-faint" aria-hidden="true" />
          </Link>
        </li>
      ))}
    </ul>
  )
}
