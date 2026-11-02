import { GitFork, Star } from 'lucide-react'
import type { ReactNode } from 'react'

import type { Technology } from '../../api/repositories'
import AiOverview from '../../components/ai/AiOverview'
import ExplanationPanel from '../../components/ai/ExplanationPanel'
import ImportantFiles from '../../components/repository/ImportantFiles'
import ImportSummary from '../../components/repository/ImportSummary'
import LanguageBar from '../../components/repository/LanguageBar'
import StatsGrid from '../../components/repository/StatsGrid'
import TechnologyList from '../../components/repository/TechnologyList'
import { useAiExplanation } from '../../hooks/useAiExplanation'
import { useRepositoryContext } from '../../hooks/useRepositoryContext'
import { formatCount, formatDate, formatRelativeTime } from '../../lib/format'

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="mt-0.5 font-medium">{children}</dd>
    </div>
  )
}

function Card({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="rounded-xl border border-line bg-surface p-5">
      <h2 id={id} className="mb-4 font-semibold">
        {title}
      </h2>
      {children}
    </section>
  )
}

function TechnologiesCard({ repositoryId, technologies }: { repositoryId: string; technologies: Technology[] }) {
  const { data } = useAiExplanation(repositoryId, 'technologies')
  const explanations = data?.status === 'completed' ? data.content?.technologies : undefined

  return (
    <Card id="technologies-heading" title="Frameworks and libraries">
      <TechnologyList technologies={technologies} repositoryId={repositoryId} explanations={explanations} />
      {technologies.length > 0 && (
        <div className="mt-5 border-t border-line pt-4">
          <ExplanationPanel
            repositoryId={repositoryId}
            kind="technologies"
            actionLabel="Explain these technologies"
            intro={
              <p>
                Get a short description of each one, its strengths, alternatives and trade-offs. This is general
                knowledge, shown separately from the evidence found in the code.
              </p>
            }
          >
            {() => (
              <p className="text-sm text-muted">
                Open a technology above to read what it is, why it might be used and what else could do the job.
              </p>
            )}
          </ExplanationPanel>
        </div>
      )}
    </Card>
  )
}

export default function OverviewTab() {
  const { repository, analysis } = useRepositoryContext()
  const meta = analysis.github_metadata
  const stats = analysis.code_stats

  // Prefer the languages actually found in the imported files (by lines of code).
  // GitHub's own breakdown is the fallback if code analysis was unavailable.
  const programmingLines = Object.fromEntries(
    (stats?.languages ?? []).filter((l) => l.is_programming && l.lines > 0).map((l) => [l.name, l.lines]),
  )
  const languages = Object.keys(programmingLines).length > 0 ? programmingLines : analysis.languages

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

      <AiOverview repositoryId={repository.id} />

      {languages && Object.keys(languages).length > 0 && (
        <Card id="languages-heading" title={stats ? 'Languages, by lines of code' : 'Languages'}>
          <LanguageBar languages={languages} />
        </Card>
      )}

      {stats ? (
        <StatsGrid stats={stats} />
      ) : (
        <p className="rounded-xl border border-dashed border-line px-5 py-4 text-sm text-muted">
          Code analysis was not available for this import, so statistics, technologies and the file outline are
          missing. Try analyzing the repository again.
        </p>
      )}

      {analysis.technologies && (
        <TechnologiesCard repositoryId={repository.id} technologies={analysis.technologies} />
      )}

      {analysis.technologies && (
        <Card id="important-heading" title="Important files">
          <ImportantFiles files={repository.important_files} repositoryId={repository.id} />
        </Card>
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
