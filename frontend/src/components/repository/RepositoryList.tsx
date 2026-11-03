import { FileArchive, Search, Sparkles, X } from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import type { RepositorySummary } from '../../api/repositories'
import { useCollections } from '../../hooks/useLibrary'
import { useAddRepository, useRepositories } from '../../hooks/useRepositories'
import { cn } from '../../lib/cn'
import { formatCount, formatRelativeTime } from '../../lib/format'
import { buttonClass } from '../ui/button'
import StatusBadge from './StatusBadge'
import Skeleton from '../ui/Skeleton'
import Spinner from '../ui/Spinner'

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

const SORTS = [
  { value: 'newest', label: 'Newest first' },
  { value: 'practice', label: 'Least practised first' },
  { value: 'name', label: 'Name' },
] as const
type Sort = (typeof SORTS)[number]['value']

const practised = (r: RepositorySummary) => r.practice.practicing + r.practice.confident
/** Share of the practice questions already worked on; repositories with none come first. */
const practiceShare = (r: RepositorySummary) => (r.practice.total ? practised(r) / r.practice.total : -1)

function sorted(items: RepositorySummary[], sort: Sort): RepositorySummary[] {
  if (sort === 'name') return [...items].sort((a, b) => a.name.localeCompare(b.name))
  if (sort === 'practice') return [...items].sort((a, b) => practiceShare(a) - practiceShare(b))
  return items // the server already sends the newest first
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
    sort: (SORTS.find((s) => s.value === params.get('sort'))?.value ?? 'newest') as Sort,
    set,
    // Clearing the filters keeps the chosen order.
    clear: () => setParams(params.get('sort') ? { sort: params.get('sort')! } : {}, { replace: true }),
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

function Practice({ repository }: { repository: RepositorySummary }) {
  // Absent when talking to an older server during a deploy.
  const { total, practicing, confident } = repository.practice ?? { total: 0, practicing: 0, confident: 0 }
  if (total === 0) {
    return repository.latest_analysis?.status === 'completed' ? <span>No practice questions yet</span> : null
  }
  const done = practicing + confident
  return (
    <span className="flex items-center gap-2" title={`${confident} confident, ${practicing} practising, ${total - done} new`}>
      <span aria-hidden="true" className="flex h-1.5 w-14 overflow-hidden rounded-full bg-line">
        <span className="bg-ok" style={{ width: `${(confident / total) * 100}%` }} />
        <span className="bg-mark" style={{ width: `${(practicing / total) * 100}%` }} />
      </span>
      <span className={cn(done === 0 && 'text-mark-text')}>
        {done} of {total} practised
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
        className="group grid gap-x-4 gap-y-1.5 border-l-2 border-transparent py-4 pr-5 pl-[18px] transition-colors hover:border-mark hover:bg-mark/[0.06] sm:grid-cols-[minmax(0,1fr)_auto]"
      >
        <div className="min-w-0">
          <p className="flex min-w-0 items-center gap-2">
            {repository.source_type === 'zip' && (
              <FileArchive size={14} className="shrink-0 text-muted" aria-label="Uploaded ZIP" />
            )}
            <span className="truncate text-[15px] font-semibold group-hover:text-mark-text">
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
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 font-mono text-[11.5px] text-faint">
          <Languages repository={repository} />
          {repository.code_lines != null && <span>{formatCount(repository.code_lines)} lines</span>}
          <Practice repository={repository} />
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

const SAMPLE_URL = 'https://github.com/pallets/click'

/** First visit: offer a ready-made repository so the first result takes seconds, not a decision. */
function EmptyLibrary() {
  const add = useAddRepository()
  const navigate = useNavigate()
  return (
    <div className="rounded-xl border border-dashed border-line px-6 py-10">
      <h3 className="font-semibold">No repositories yet</h3>
      <p className="mt-1.5 max-w-md text-sm text-muted">
        Paste a GitHub link or upload a ZIP above. Each one is analyzed once and saved here, ready to explore, chat
        with and practise on.
      </p>
      <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2">
        <button
          type="button"
          disabled={add.isPending}
          onClick={() => add.mutate(SAMPLE_URL, { onSuccess: (repository) => navigate(`/repositories/${repository.id}`) })}
          className={buttonClass('secondary', 'h-9 px-3')}
        >
          {add.isPending ? <Spinner size={15} /> : <Sparkles size={15} className="text-mark-text" aria-hidden="true" />}
          {add.isPending ? 'Adding…' : 'Try it with pallets/click'}
        </button>
        <span className="text-sm text-faint">A small, well-known project. It takes under a minute.</span>
      </div>
      {add.isError && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {add.error.message}
        </p>
      )}
    </div>
  )
}

export default function RepositoryList() {
  const { data, isPending, isError, refetch } = useRepositories()
  const { data: collections = [] } = useCollections()
  const filters = useFilters()

  if (isPending) {
    return (
      <div role="status" aria-label="Loading your repositories" className="overflow-hidden rounded-xl border border-line bg-surface">
        <span className="sr-only">Loading your repositories…</span>
        {[0, 1, 2].map((row) => (
          <div key={row} className="space-y-2.5 border-b border-line py-4 pr-5 pl-5 last:border-b-0">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-3 w-3/5" />
          </div>
        ))}
      </div>
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
    return <EmptyLibrary />
  }

  const labels = [...new Set(data.flatMap((r) => r.labels))].sort((a, b) => a.localeCompare(b))
  const collection = collections.find((c) => c.id === filters.collection)
  const shown = data.filter(
    (r) =>
      (!filters.query || matches(r, filters.query)) &&
      (!filters.label || r.labels.includes(filters.label)) &&
      (!filters.collection || r.collection_ids.includes(filters.collection)),
  )
  const ordered = sorted(shown, filters.sort)
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
        <select
          aria-label="Sort by"
          value={filters.sort}
          onChange={(event) => filters.set('sort', event.target.value === 'newest' ? null : event.target.value)}
          className="h-9 rounded-md border border-line bg-canvas px-2 text-sm text-ink"
        >
          {SORTS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
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
          <span className="inline-flex items-center gap-1 rounded-full border border-mark/40 py-0.5 pr-1 pl-2.5 text-xs text-mark-text">
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
                  active ? 'border-mark/50 bg-mark/15 text-mark-text' : 'border-line text-muted hover:border-faint hover:text-ink',
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
          <button type="button" onClick={filters.clear} className="mt-1.5 text-mark-text hover:underline">
            Clear filters
          </button>
        </div>
      ) : (
        <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
          {ordered.map((repository) => (
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
