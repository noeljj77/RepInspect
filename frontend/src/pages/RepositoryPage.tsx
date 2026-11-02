import { ArrowLeft, CircleAlert, ExternalLink, GitFork, Star } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../api/client'
import { isInProgress, type AnalysisDetail, type RepositoryDetail } from '../api/repositories'
import AnalysisProgress from '../components/repository/AnalysisProgress'
import ImportSummary from '../components/repository/ImportSummary'
import LanguageBar from '../components/repository/LanguageBar'
import StatusBadge from '../components/repository/StatusBadge'
import { buttonClass } from '../components/ui/button'
import { useRepository, useStartAnalysis } from '../hooks/useRepositories'
import { formatCount, formatDate, formatRelativeTime } from '../lib/format'

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="mt-0.5 font-medium">{children}</dd>
    </div>
  )
}

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

function Results({ analysis }: { analysis: AnalysisDetail }) {
  const meta = analysis.github_metadata

  return (
    <div className="space-y-6">
      {meta && (
        <section aria-labelledby="facts-heading" className="rounded-xl border border-line bg-surface p-5">
          <h2 id="facts-heading" className="sr-only">
            Repository facts
          </h2>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-4">
            <Fact label="Stars">
              <span className="inline-flex items-center gap-1.5">
                <Star size={14} aria-hidden="true" />
                {formatCount(meta.stars)}
              </span>
            </Fact>
            <Fact label="Forks">
              <span className="inline-flex items-center gap-1.5">
                <GitFork size={14} aria-hidden="true" />
                {formatCount(meta.forks)}
              </span>
            </Fact>
            <Fact label="Open issues and pull requests">{formatCount(meta.open_issues)}</Fact>
            <Fact label="Default branch">
              <span className="font-mono text-[14px]">{meta.default_branch}</span>
            </Fact>
            <Fact label="Last pushed">{meta.pushed_at ? formatRelativeTime(meta.pushed_at) : 'Unknown'}</Fact>
            <Fact label="Created">{meta.created_at ? formatDate(meta.created_at) : 'Unknown'}</Fact>
            <Fact label="License">{meta.license && meta.license !== 'NOASSERTION' ? meta.license : 'None found'}</Fact>
            <Fact label="Analyzed commit">
              <span className="font-mono text-[14px]">{analysis.commit_sha?.slice(0, 7) ?? 'Unknown'}</span>
            </Fact>
          </dl>
        </section>
      )}

      {analysis.languages && Object.keys(analysis.languages).length > 0 && (
        <section aria-labelledby="languages-heading" className="rounded-xl border border-line bg-surface p-5">
          <h2 id="languages-heading" className="mb-4 font-semibold">
            Languages
          </h2>
          <LanguageBar languages={analysis.languages} />
        </section>
      )}

      <ImportSummary analysis={analysis} />

      <section aria-labelledby="readme-heading" className="rounded-xl border border-line bg-surface p-5">
        <h2 id="readme-heading" className="font-semibold">
          README
        </h2>
        {analysis.readme_text ? (
          <pre className="mt-3 max-h-96 overflow-auto rounded-md bg-canvas p-4 font-mono text-[13px] leading-6 whitespace-pre-wrap text-ink/90">
            {analysis.readme_text}
          </pre>
        ) : (
          <p className="mt-2 text-sm text-muted">This repository has no README file.</p>
        )}
      </section>
    </div>
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
      <div className="mx-auto max-w-4xl">
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
      <div className="mx-auto max-w-4xl">
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

  return (
    <div className="mx-auto max-w-4xl">
      {back}

      <header className="mt-5 mb-8">
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

      {!analysis ? (
        <FailedCard repository={repository} message="This repository has not been analyzed yet." />
      ) : isInProgress(analysis) ? (
        <AnalysisProgress status={analysis.status} />
      ) : analysis.status === 'failed' ? (
        <FailedCard
          repository={repository}
          message={analysis.error_message ?? 'Something went wrong while analyzing this repository.'}
        />
      ) : (
        <Results analysis={analysis} />
      )}
    </div>
  )
}
