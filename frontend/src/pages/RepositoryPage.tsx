import { ArrowLeft, CircleAlert, ExternalLink } from 'lucide-react'
import { Link, NavLink, Outlet, useParams } from 'react-router'

import { ApiError } from '../api/client'
import { isInProgress, type RepositoryDetail } from '../api/repositories'
import AnalysisProgress from '../components/repository/AnalysisProgress'
import StatusBadge from '../components/repository/StatusBadge'
import { buttonClass } from '../components/ui/button'
import { useRepository, useStartAnalysis } from '../hooks/useRepositories'
import type { RepositoryContext } from '../hooks/useRepositoryContext'
import { cn } from '../lib/cn'

function FailedCard({ repository, message }: { repository: RepositoryDetail; message: string }) {
  const retry = useStartAnalysis(repository.id)

  return (
    <section role="alert" className="rounded-xl border border-danger/30 bg-surface p-6">
      <div className="flex gap-3">
        <CircleAlert size={20} className="mt-0.5 shrink-0 text-danger" aria-hidden="true" />
        <div>
          <h2 className="font-semibold">This repository could not be analyzed</h2>
          <p className="mt-1.5 text-muted">{message}</p>
          {retry.isError && <p className="mt-2 text-sm text-danger">{retry.error.message}</p>}
          <button
            type="button"
            onClick={() => retry.mutate()}
            disabled={retry.isPending}
            className={buttonClass('secondary', 'mt-4')}
          >
            {retry.isPending ? 'Starting…' : 'Try again'}
          </button>
        </div>
      </div>
    </section>
  )
}

function Tabs({ repository }: { repository: RepositoryDetail }) {
  const base = `/repositories/${repository.id}`
  const totals = repository.latest_analysis?.code_stats?.totals
  const tabs = [
    { to: base, label: 'Overview', end: true },
    { to: `${base}/files`, label: 'Files', count: repository.latest_analysis?.file_count },
    { to: `${base}/dependencies`, label: 'Dependencies', count: totals?.dependencies },
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
  const description = analysis?.github_metadata?.description
  const githubUrl = analysis?.github_metadata?.html_url ?? repository.source_url
  const context: RepositoryContext | null =
    analysis?.status === 'completed' ? { repository, analysis } : null

  return (
    <div className="mx-auto max-w-6xl">
      {back}

      <header className="mt-5 mb-6">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <h1 className="text-3xl font-semibold tracking-tight break-all">
            {repository.owner ? `${repository.owner}/` : ''}
            {repository.name}
          </h1>
          {analysis && <StatusBadge status={analysis.status} />}
        </div>
        {description && <p className="mt-3 max-w-2xl text-lg text-muted">{description}</p>}
        {githubUrl && (
          <a
            href={githubUrl}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink"
          >
            View on GitHub
            <ExternalLink size={13} aria-hidden="true" />
          </a>
        )}
      </header>

      {context ? (
        <>
          <Tabs repository={repository} />
          <Outlet context={context} />
        </>
      ) : !analysis ? (
        <FailedCard repository={repository} message="This repository has not been analyzed yet." />
      ) : isInProgress(analysis) ? (
        <AnalysisProgress status={analysis.status} />
      ) : (
        <FailedCard
          repository={repository}
          message={analysis.error_message ?? 'Something went wrong while analyzing this repository.'}
        />
      )}
    </div>
  )
}
