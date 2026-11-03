import type { OverviewContent, OverviewSection } from '../../api/ai'
import { cn } from '../../lib/cn'
import ExplanationPanel from './ExplanationPanel'
import { FindingList, UngroundedPaths } from './Findings'

function Section({ repositoryId, section }: { repositoryId: string; section: OverviewSection }) {
  const headingId = `ai-section-${section.key}`
  return (
    <section
      aria-labelledby={headingId}
      className="grid gap-x-6 gap-y-2 border-t border-line py-5 first:border-t-0 first:pt-0 last:pb-0 @lg:grid-cols-[11rem_minmax(0,1fr)]"
    >
      <h3 id={headingId} className={cn('font-medium', !section.determined && 'text-muted')}>
        {section.title}
      </h3>
      <div className="max-w-[72ch] space-y-3 text-[15px]">
        {section.determined ? (
          <p className="leading-relaxed text-ink/90">{section.summary}</p>
        ) : (
          <p className="text-sm text-muted">
            Could not be determined from the analyzed files.
            {section.summary && <span className="mt-1 block">{section.summary}</span>}
          </p>
        )}
        <FindingList repositoryId={repositoryId} findings={section.findings} />
        <UngroundedPaths paths={section.ungrounded_paths} />
      </div>
    </section>
  )
}

function Overview({ repositoryId, content }: { repositoryId: string; content: OverviewContent }) {
  return (
    <div>
      {content.sections.map((section) => (
        <Section key={section.key} repositoryId={repositoryId} section={section} />
      ))}
    </div>
  )
}

export default function AiOverview({ repositoryId }: { repositoryId: string }) {
  return (
    <section aria-labelledby="ai-overview-heading" className="@container rounded-xl border border-line bg-surface p-5">
      <h2 id="ai-overview-heading" className="mb-4 font-semibold">
        How this project works
      </h2>
      <ExplanationPanel
        repositoryId={repositoryId}
        kind="overview"
        actionLabel="Write the overview"
        intro={
          <p>
            An AI-written tour of the purpose, architecture and important files. Statements quote the code they
            rely on, and anything the code does not confirm is marked as inference.
          </p>
        }
      >
        {(content) => <Overview repositoryId={repositoryId} content={content} />}
      </ExplanationPanel>
    </section>
  )
}
