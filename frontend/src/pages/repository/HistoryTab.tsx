import { useState } from 'react'
import { Link } from 'react-router'

import type { AnalysisSummary, Changes, PathChanges } from '../../api/repositories'
import StatusBadge from '../../components/repository/StatusBadge'
import { useVersionChanges, useVersions } from '../../hooks/useRepositories'
import { useRepositoryContext } from '../../hooks/useRepositoryContext'
import { cn } from '../../lib/cn'
import { formatDate, formatRelativeTime } from '../../lib/format'
import { fileLink } from '../../lib/links'

function PathList({
  title,
  changes,
  repositoryId,
  linkable,
  tone,
}: {
  title: string
  changes: PathChanges
  repositoryId: string
  /** Files of the version on screen can be opened; files that were removed cannot. */
  linkable: boolean
  tone: string
}) {
  if (changes.count === 0) return null
  return (
    <div>
      <h4 className="text-xs text-muted">
        {title} <span className="text-faint">{changes.count.toLocaleString('en')}</span>
      </h4>
      <ul className="mt-1 max-h-48 space-y-0.5 overflow-y-auto font-mono text-[12.5px]">
        {changes.paths.map((path) => (
          <li key={path} className={cn('truncate border-l-2 pl-2', tone)}>
            {linkable ? (
              <Link to={fileLink(repositoryId, path)} className="hover:text-mark hover:underline">
                {path}
              </Link>
            ) : (
              path
            )}
          </li>
        ))}
        {changes.count > changes.paths.length && (
          <li className="pl-2.5 font-sans text-xs text-faint">
            and {(changes.count - changes.paths.length).toLocaleString('en')} more
          </li>
        )}
      </ul>
    </div>
  )
}

function NameList({ title, names }: { title: string; names: string[] }) {
  if (names.length === 0) return null
  return (
    <p className="text-sm">
      <span className="text-muted">{title}: </span>
      {names.join(', ')}
    </p>
  )
}

function ChangeSummary({ changes, repositoryId, isCurrent }: { changes: Changes; repositoryId: string; isCurrent: boolean }) {
  const { added, removed, modified, unchanged } = changes
  const nothing = added.count + removed.count + modified.count === 0
  return (
    <div className="space-y-3">
      <p className="text-sm">
        {nothing
          ? 'No files changed.'
          : `${added.count} added, ${modified.count} changed, ${removed.count} removed, ${unchanged} unchanged.`}
        {!changes.exact && (
          <span className="block text-xs text-muted">
            The earlier version was analyzed before file contents were compared, so changes are judged by file size.
          </span>
        )}
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        <PathList title="Added" changes={added} repositoryId={repositoryId} linkable={isCurrent} tone="border-ok/60" />
        <PathList title="Changed" changes={modified} repositoryId={repositoryId} linkable={isCurrent} tone="border-mark/60" />
        <PathList title="Removed" changes={removed} repositoryId={repositoryId} linkable={false} tone="border-danger/60" />
      </div>
      <NameList title="Technologies added" names={changes.technologies_added} />
      <NameList title="Technologies no longer found" names={changes.technologies_removed} />
      <NameList title="Dependencies added" names={changes.dependencies_added} />
      <NameList title="Dependencies removed" names={changes.dependencies_removed} />
      <NameList title="Versions changed" names={changes.dependencies_changed} />
    </div>
  )
}

function Version({
  repositoryId,
  version,
  isCurrent,
  sourceType,
}: {
  repositoryId: string
  version: AnalysisSummary
  isCurrent: boolean
  sourceType: 'github' | 'zip'
}) {
  const [open, setOpen] = useState(isCurrent)
  const completed = version.status === 'completed'
  const changes = useVersionChanges(repositoryId, version.id, open && completed)

  return (
    <li className="border-t border-line py-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <h3 className="font-medium">Version {version.version}</h3>
        <StatusBadge status={version.status} />
        {isCurrent && <span className="text-xs text-mark">Shown now</span>}
        <span className="text-sm text-muted">
          {formatDate(version.created_at)} ({formatRelativeTime(version.created_at)})
        </span>
      </div>
      <p className="mt-1 text-sm text-muted">
        {sourceType === 'github' && version.commit_sha && (
          <>
            Commit <span className="font-mono text-[13px] text-ink/85">{version.commit_sha.slice(0, 7)}</span>,{' '}
          </>
        )}
        {completed
          ? `${version.file_count.toLocaleString('en')} files`
          : version.status === 'failed'
            ? version.error_message
            : 'Being analyzed'}
        {version.source_removed && ', files no longer stored'}
      </p>

      {completed && (
        <div className="mt-2">
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-expanded={open}
            className="text-sm text-muted underline-offset-4 hover:text-ink hover:underline"
          >
            {open ? 'Hide what changed' : 'What changed'}
          </button>
          {open && (
            <div className="mt-3 rounded-lg border border-line bg-surface p-4">
              {changes.isPending ? (
                <p role="status" className="text-sm text-muted">
                  Comparing with the previous version…
                </p>
              ) : changes.isError ? (
                <p role="alert" className="text-sm text-danger">
                  The comparison could not be loaded.
                </p>
              ) : changes.data.changes === null ? (
                <p className="text-sm text-muted">This is the first version, so there is nothing to compare with.</p>
              ) : (
                <>
                  <p className="mb-3 text-xs text-muted">Compared with version {changes.data.previous_version}.</p>
                  <ChangeSummary changes={changes.data.changes} repositoryId={repositoryId} isCurrent={isCurrent} />
                </>
              )}
            </div>
          )}
        </div>
      )}
    </li>
  )
}

export default function HistoryTab() {
  const { repository, analysis } = useRepositoryContext()
  const { data: versions, isPending, isError } = useVersions(repository.id, repository.latest_analysis?.status)

  return (
    <section aria-labelledby="history-heading" className="max-w-3xl">
      <h2 id="history-heading" className="font-semibold">
        Versions
      </h2>
      <p className="mt-1 mb-5 text-sm text-muted">
        {repository.source_type === 'zip'
          ? 'Each upload of a new ZIP adds a version.'
          : 'Each refresh analyzes the latest commit as a new version.'}{' '}
        Notes, labels and collections stay with the repository; older versions keep their file list, not their files.
      </p>
      {isPending ? (
        <p role="status" className="text-sm text-muted">
          Loading versions…
        </p>
      ) : isError ? (
        <p role="alert" className="text-sm text-danger">
          The version history could not be loaded.
        </p>
      ) : (
        <ol>
          {versions.map((version) => (
            <Version
              key={version.id}
              repositoryId={repository.id}
              version={version}
              isCurrent={version.id === analysis.id}
              sourceType={repository.source_type}
            />
          ))}
        </ol>
      )}
    </section>
  )
}
