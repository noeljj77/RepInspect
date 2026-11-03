import { FileArchive, Search, X } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'

import type { RepositorySummary } from '../../api/repositories'
import { useCollections } from '../../hooks/useLibrary'
import { useRepositories } from '../../hooks/useRepositories'
import { cn } from '../../lib/cn'
import { formatCount, formatRelativeTime } from '../../lib/format'
import StatusBadge from './StatusBadge'

// The same calm palette as the language bar on the repository page.
const LANGUAGE_COLORS = ['#f2c14e', '#93a4f5', '#7fd1a4']

function matches(repository: RepositorySummary, query: string): boolean {
  const text = [repository.owner, repository.name, repository.description, ...repository.labels]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return query
    .toLowerCase()
    .split(/\s+/)
    .every((word) => text.includes(word))
}

/** Filters live in the address (?q=, ?label=, ?collection=) so they survive a reload and can be shared. */
function useFilters() {
  const [params, setParams] = useSearchParams()
  const set = (key: string, value: string | null) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }
  return {
    query: params.get('q') ?? '',
    label: params.get('label'),
    collection: params.get('collection'),
    set,
    clear: () => setParams({}, { replace: true }),
  }
}

function Languages({ repository }: { repository: RepositorySummary }) {
  // Absent when talking to an older server during a deploy.
  const languages = repository.languages ?? []
  if (languages.length === 0) return null
  return (
    <span className="flex items-center gap-2">
      <span aria-hidden="true" className="flex h-1.5 w-14 overflow-hidden rounded-full bg-line">
        {languages.map((language, index) => (
          <span key={language.name} style={{ width: `${language.share * 100}%`, background: LANGUAGE_COLORS[index] }} />
        ))}
      </span>
      <span>
        {languages
          .slice(0, 2)
          .map((language) => language.name)
          .join(', ')}
      </span>
    </span>
  )
}

function Row({ repository }: { repository: RepositorySummary }) {
  const analysis = repository.latest_analysis
  return (
    <li>
      <Link
        to={`/repositories/${repository.id}`}
        className="group grid gap-x-4 gap-y-1.5 px-5 py-4 transition-colors hover:bg-raised/50 sm:grid-cols-[minmax(0,1fr)_auto]"
      >
        <div className="min-w-0">
          <p className="flex min-w-0 items-center gap-2">
            {repository.source_type === 'zip' && (
              <FileArchive size={14} className="shrink-0 text-muted" aria-label="Uploaded ZIP" />
            )}
            <span className="truncate font-medium group-hover:text-mark">
              {repository.owner && <span className="font-normal text-muted">{repository.owner}/</span>}
              {repository.name}
            </span>
          </p>
          {repository.description && (
            <p className="mt-0.5 line-clamp-1 text-sm text-muted">{repository.description}</p>
          )}
        </div>
        <div className="sm:row-span-2 sm:self-center">
          {analysis && <StatusBadge status={analysis.status} />}
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-faint">
          <Languages repository={repository} />
          {repository.code_lines != null && <span>{formatCount(repository.code_lines)} lines</span>}
          <span>
            {analysis?.completed_at
              ? `Analyzed ${formatRelativeTime(analysis.completed_at)}`
              : `Added ${formatRelativeTime(repository.created_at)}`}
          </span>
          {repository.labels.map((label) => (
            <span key={label} className="rounded-full bg-raised px-2 py-px text-[11px] text-muted">
              {label}
            </span>
          ))}
        </div>
      </Link>
    </li>
  )
}

export default function RepositoryList() {
  const { data, isPending, isError, refetch } = useRepositories()
  const { data: collections = [] } = useCollections()
  const filters = useFilters()

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
      <div className="rounded-xl border border-dashed border-line px-6 py-10">
        <h3 className="font-semibold">No repositories yet</h3>
        <p className="mt-1.5 max-w-md text-sm text-muted">
          Paste a GitHub link or upload a ZIP above. Each one is analyzed once and saved here, ready to explore,
          chat with and practise on.
        </p>
      </div>
    )
  }

  const labels = [...new Set(data.flatMap((r) => r.labels))].sort((a, b) => a.localeCompare(b))
  const collection = collections.find((c) => c.id === filters.collection)
  const shown = data.filter(
    (r) =>
      (!filters.query || matches(r, filters.query)) &&
      (!filters.label || r.labels.includes(filters.label)) &&
      (!filters.collection || r.collection_ids.includes(filters.collection)),
  )
  const filtering = Boolean(filters.query || filters.label || filters.collection)

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="relative min-w-48 flex-1">
          <span className="sr-only">Search your repositories</span>
          <Search size={15} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-faint" aria-hidden="true" />
          <input
            type="search"
            value={filters.query}
            onChange={(event) => filters.set('q', event.target.value)}
            placeholder="Search by name, description or label"
            className="h-9 w-full rounded-md border border-line bg-canvas pr-3 pl-9 text-sm placeholder:text-faint focus:border-mark focus:outline-none"
          />
        </label>
        {collections.length > 0 && (
          <select
            aria-label="Collection"
            value={filters.collection ?? ''}
            onChange={(event) => filters.set('collection', event.target.value || null)}
            className="h-9 rounded-md border border-line bg-canvas px-2 text-sm text-ink"
          >
            <option value="">All collections</option>
            {collections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        )}
        {collection && (
          <span className="inline-flex items-center gap-1 rounded-full border border-mark/40 py-0.5 pr-1 pl-2.5 text-xs text-mark">
            In {collection.name}
            <button
              type="button"
              onClick={() => filters.set('collection', null)}
              aria-label="Show all collections"
              className="rounded-full p-0.5 hover:bg-mark/15"
            >
              <X size={11} aria-hidden="true" />
            </button>
          </span>
        )}
      </div>

      {labels.length > 0 && (
        <div role="group" aria-label="Filter by label" className="flex flex-wrap gap-1.5">
          {labels.map((label) => {
            const active = filters.label === label
            return (
              <button
                key={label}
                type="button"
                aria-pressed={active}
                onClick={() => filters.set('label', active ? null : label)}
                className={cn(
                  'rounded-full border px-2.5 py-0.5 text-xs',
                  active ? 'border-mark/50 bg-mark/15 text-mark' : 'border-line text-muted hover:border-faint hover:text-ink',
                )}
              >
                {label}
              </button>
            )
          })}
        </div>
      )}

      {shown.length === 0 ? (
        <div className="rounded-xl border border-dashed border-line px-6 py-6 text-sm">
          <p className="text-muted">No repositories match these filters.</p>
          <button type="button" onClick={filters.clear} className="mt-1.5 text-mark hover:underline">
            Clear filters
          </button>
        </div>
      ) : (
        <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
          {shown.map((repository) => (
            <Row key={repository.id} repository={repository} />
          ))}
        </ul>
      )}
      {filtering && shown.length > 0 && (
        <p className="text-xs text-faint">
          Showing {shown.length} of {data.length}.{' '}
          <button type="button" onClick={filters.clear} className="text-muted hover:text-ink hover:underline">
            Clear filters
          </button>
        </p>
      )}
    </div>
  )
}
