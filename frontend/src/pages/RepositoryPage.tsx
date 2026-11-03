import { ArrowLeft, CircleAlert, ExternalLink, FileArchive } from 'lucide-react'
import { Link, NavLink, Outlet, useParams } from 'react-router'

import { ApiError } from '../api/client'
import { isInProgress, type RepositoryDetail } from '../api/repositories'
import CollectionPicker from '../components/library/CollectionPicker'
import LabelEditor from '../components/library/LabelEditor'
import RepositoryActions from '../components/library/RepositoryActions'
import AnalysisProgress from '../components/repository/AnalysisProgress'
import StatusBadge from '../components/repository/StatusBadge'
import { ZipPicker } from '../components/library/RepositoryActions'
import { buttonClass } from '../components/ui/button'
import { useReloadOnNewVersion, useRepository, useStartAnalysis, useUploadNewVersion } from '../hooks/useRepositories'
import type { RepositoryContext } from '../hooks/useRepositoryContext'
import { cn } from '../lib/cn'
import { formatRelativeTime } from '../lib/format'

/** Retrying means analyzing GitHub again, or for an upload, choosing the ZIP again. */
function RetryButton({ repository, label }: { repository: RepositoryDetail; label: string }) {
  const retry = useStartAnalysis(repository.id)
  const upload = useUploadNewVersion(repository.id)
  const error = retry.error ?? upload.error
  return (
    <>
      {error && <p className="mt-2 text-sm text-danger">{error.message}</p>}
      {repository.source_type === 'zip' ? (
        <div className="mt-4">
          <ZipPicker label="Upload the ZIP again" onPick={(file) => upload.mutate(file)} disabled={upload.isPending} />
        </div>
      ) : (
        <button
          type="button"
          onClick={() => retry.mutate()}
          disabled={retry.isPending}
          className={buttonClass('secondary', 'mt-4')}
        >
          {retry.isPending ? 'Starting…' : label}
        </button>
      )}
    </>
  )
}

/** Shown above the tabs while a refresh runs, or after one failed. The previous version stays usable. */
function RefreshBanner({ repository }: { repository: RepositoryDetail }) {
  const latest = repository.latest_analysis
  const current = repository.current_analysis
  if (!latest || !current || latest.id === current.id) return null

  if (isInProgress(latest)) {
    return (
      <section aria-label="Refresh" className="mb-6 flex flex-wrap items-center gap-3 rounded-xl border border-mark/25 bg-surface px-5 py-3.5 text-sm">
        <StatusBadge status={latest.status} />
        <p className="text-muted">
          Version {latest.version} is being analyzed. You are looking at version {current.version} until it is ready.
        </p>
      </section>
    )
  }
  return (
    <section role="alert" className="mb-6 rounded-xl border border-danger/30 bg-surface px-5 py-4 text-sm">
      <p>
        <span className="font-medium text-danger">The refresh failed.</span>{' '}
        <span className="text-muted">
          {latest.error_message ?? 'Something went wrong.'} You are looking at version {current.version}, analyzed{' '}
          {formatRelativeTime(current.completed_at ?? current.created_at)}.
        </span>
      </p>
      <RetryButton repository={repository} label="Try the refresh again" />
    </section>
  )
}

function FailedCard({ repository, message }: { repository: RepositoryDetail; message: string }) {

  return (
    <section role="alert" className="rounded-xl border border-danger/30 bg-surface p-6">
      <div className="flex gap-3">
        <CircleAlert size={20} className="mt-0.5 shrink-0 text-danger" aria-hidden="true" />
        <div>
          <h2 className="font-semibold">This repository could not be analyzed</h2>
          <p className="mt-1.5 text-muted">{message}</p>
          <RetryButton repository={repository} label="Try again" />
        </div>
      </div>
    </section>
  )
}

function Tabs({ repository }: { repository: RepositoryDetail }) {
  const base = `/repositories/${repository.id}`
  const totals = repository.current_analysis?.code_stats?.totals
  const tabs = [
    { to: base, label: 'Overview', end: true },
    { to: `${base}/files`, label: 'Files', count: repository.current_analysis?.file_count },
    { to: `${base}/dependencies`, label: 'Dependencies', count: totals?.dependencies },
    { to: `${base}/chat`, label: 'Chat' },
    { to: `${base}/interview`, label: 'Interview' },
    { to: `${base}/notes`, label: 'Notes' },
    { to: `${base}/history`, label: 'History' },
  ]

  return (
    <nav aria-label="Repository sections" className="mb-6 flex gap-1 overflow-x-auto border-b border-line">
      {tabs.map((tab) => (
        <NavLink
          key={tab.label}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) =>
            cn(
              '-mb-px flex shrink-0 items-center gap-2 border-b-2 px-3 py-2.5 text-sm transition-colors',
              isActive ? 'border-mark text-ink' : 'border-transparent text-muted hover:text-ink',
            )
          }
        >
          {tab.label}{' '}
          {tab.count !== undefined && (
            <span className="rounded-full bg-raised px-1.5 text-xs text-muted">{tab.count.toLocaleString('en')}</span>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

export default function RepositoryPage() {
  const { repositoryId = '' } = useParams()
  const { data: repository, isPending, error } = useRepository(repositoryId)
  useReloadOnNewVersion(repository)

  const back = (
    <Link to="/dashboard" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
      <ArrowLeft size={15} aria-hidden="true" />
      Dashboard
    </Link>
  )

  if (isPending) {
    return (
      <div className="mx-auto max-w-6xl">
        {back}
        <p role="status" className="mt-6 text-muted">
          Loading repository…
        </p>
      </div>
    )
  }

  if (error || !repository) {
    const notFound = error instanceof ApiError && (error.status === 404 || error.status === 422)
    return (
      <div className="mx-auto max-w-6xl">
        {back}
        <h1 className="mt-6 text-2xl font-semibold">{notFound ? 'Repository not found' : 'Something went wrong'}</h1>
        <p className="mt-2 text-muted">
          {notFound
            ? "It may have been removed, or it isn't in your library."
            : 'The repository could not be loaded. Try again in a moment.'}
        </p>
      </div>
    )
  }

  const analysis = repository.latest_analysis
  const shown = repository.current_analysis
  const badge = shown ?? analysis
  const description = shown?.github_metadata?.description
  const githubUrl = shown?.github_metadata?.html_url ?? repository.source_url
  // The newest finished version is shown, even while a newer one is being analyzed.
  const context: RepositoryContext | null = shown ? { repository, analysis: shown } : null

  return (
    <div className="mx-auto max-w-6xl">
      {back}

      <header className="mt-5 mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <h1 className="text-3xl font-semibold tracking-tight break-all">
              {repository.owner ? `${repository.owner}/` : ''}
              {repository.name}
            </h1>
            {badge && <StatusBadge status={badge.status} />}
          </div>
          {description && <p className="mt-3 max-w-2xl text-lg text-muted">{description}</p>}
          {repository.source_type === 'zip' ? (
            <p className="mt-3 inline-flex items-center gap-1.5 text-sm text-muted">
              <FileArchive size={14} aria-hidden="true" />
              Uploaded as a ZIP file
            </p>
          ) : (
            githubUrl && (
              <a
                href={githubUrl}
                target="_blank"
                rel="noreferrer"
                className="mt-3 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink"
              >
                View on GitHub
                <ExternalLink size={13} aria-hidden="true" />
              </a>
            )
          )}
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <LabelEditor repositoryId={repository.id} labels={repository.labels} />
            <CollectionPicker repositoryId={repository.id} memberOf={repository.collection_ids} />
          </div>
        </div>
        <RepositoryActions repository={repository} />
      </header>

      {context ? (
        <>
          <RefreshBanner repository={repository} />
          <Tabs repository={repository} />
          <Outlet context={context} />
        </>
      ) : !analysis ? (
        <FailedCard repository={repository} message="This repository has not been analyzed yet." />
      ) : isInProgress(analysis) ? (
        <AnalysisProgress status={analysis.status} sourceType={repository.source_type} />
      ) : (
        <FailedCard
          repository={repository}
          message={analysis.error_message ?? 'Something went wrong while analyzing this repository.'}
        />
      )}
    </div>
  )
}
