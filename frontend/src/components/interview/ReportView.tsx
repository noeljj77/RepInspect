import type { ReactNode } from 'react'

import type { ReportContent } from '../../api/ai'
import { useRepositoryContext } from '../../hooks/useRepositoryContext'
import { notesMarkdown } from '../../lib/exportReport'
import ExplanationPanel from '../ai/ExplanationPanel'
import { FindingList, UngroundedPaths } from '../ai/Findings'
import ExportMenu from './ExportMenu'

function Part({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="grid gap-x-6 gap-y-2 border-t border-line py-5 md:grid-cols-[11rem_minmax(0,1fr)]">
      <div>
        <h3 className="font-medium">{title}</h3>
        {hint && <p className="mt-0.5 text-xs text-muted">{hint}</p>}
      </div>
      <div className="max-w-[72ch] space-y-3 text-[15px]">{children}</div>
    </section>
  )
}

/** Lists of general knowledge: periwinkle, because they are suggestions, not facts about the code. */
function Suggestions({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div className="text-sm">
      <span className="text-hint">{title}: </span>
      <span className="text-ink/80">{items.join('; ')}</span>
    </div>
  )
}

function Report({ repositoryId, content }: { repositoryId: string; content: ReportContent }) {
  const { repository } = useRepositoryContext()
  const name = repository.owner ? `${repository.owner}/${repository.name}` : repository.name
  return (
    <div data-print-area>
      <h1 className="mb-4 hidden text-2xl font-semibold print:block">Interview notes: {name}</h1>
      <div className="mb-4 flex justify-end">
        <ExportMenu title={`Interview notes ${name}`} getMarkdown={() => notesMarkdown(name, content)} />
      </div>
      {/* The one thing people say in almost every interview, set large. */}
      <figure className="mb-6">
        <figcaption className="mb-2 text-sm text-muted">When they say “tell me about this project”</figcaption>
        <blockquote className="border-l-2 border-mark pl-4 text-xl leading-relaxed text-ink">{content.pitch}</blockquote>
        <UngroundedPaths paths={content.ungrounded_paths} />
      </figure>

      {content.problem && (
        <Part title="The problem">
          <p className="leading-relaxed text-ink/90">{content.problem}</p>
        </Part>
      )}

      {content.walkthrough.length > 0 && (
        <Part title="How it works" hint="Walk through the main flow in this order.">
          <FindingList repositoryId={repositoryId} findings={content.walkthrough} />
        </Part>
      )}

      {content.decisions.length > 0 && (
        <Part title="Decisions you can explain" hint="Interviewers ask why, and what else you considered.">
          <ul className="space-y-5">
            {content.decisions.map((decision, index) => (
              <li key={index} className="space-y-2">
                <FindingList repositoryId={repositoryId} findings={[decision.finding]} />
                <div className="space-y-1 pl-3.5">
                  <Suggestions title="Alternatives" items={decision.alternatives} />
                  <Suggestions title="Trade-offs" items={decision.trade_offs} />
                </div>
              </li>
            ))}
          </ul>
        </Part>
      )}

      {content.highlights.length > 0 && (
        <Part title="Worth bringing up" hint="Parts that show technical depth.">
          <FindingList repositoryId={repositoryId} findings={content.highlights} />
        </Part>
      )}

      {content.improvements.length > 0 && (
        <Part title="Weak spots to be ready for" hint="Suggestions, not facts about the code.">
          <ul className="space-y-3">
            {content.improvements.map((item, index) => (
              <li key={index} className="border-l-2 border-dashed border-hint/70 pl-3">
                <p className="leading-relaxed">{item.idea}</p>
                {item.reason && <p className="mt-0.5 text-sm text-muted">{item.reason}</p>}
              </li>
            ))}
          </ul>
        </Part>
      )}
    </div>
  )
}

export default function ReportView({ repositoryId }: { repositoryId: string }) {
  return (
    <section aria-labelledby="report-heading" className="rounded-xl border border-line bg-surface p-5">
      <h2 id="report-heading" className="mb-4 font-semibold">
        Interview notes
      </h2>
      <ExplanationPanel
        repositoryId={repositoryId}
        kind="report"
        actionLabel="Write my interview notes"
        intro={
          <p>
            A short pitch, a walkthrough of the main flow, the decisions you should be able to defend, and the weak
            spots an interviewer may probe. Everything about the code quotes the lines it relies on.
          </p>
        }
      >
        {(content) => <Report repositoryId={repositoryId} content={content} />}
      </ExplanationPanel>
    </section>
  )
}
