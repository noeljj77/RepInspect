import { Link } from 'react-router'

import type { TechnologyExplanation } from '../../api/ai'
import type { Evidence, Technology } from '../../api/repositories'
import { cn } from '../../lib/cn'
import { fileLink } from '../../lib/links'

const KIND_LABELS: Record<Evidence['kind'], string> = {
  dependency: 'Declared in',
  import: 'Imported in',
  file: 'Found file',
}

const SCOPE_NOTES: Record<string, string> = {
  dev: 'development dependency',
  build: 'build dependency',
  plugin: 'build plugin',
  optional: 'optional dependency',
  peer: 'peer dependency',
  managed: 'managed version',
}

function List({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div>
      <dt className="text-xs text-muted">{title}</dt>
      <dd>
        <ul className="mt-1 list-disc space-y-0.5 pl-4 marker:text-faint">
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      </dd>
    </div>
  )
}

/** What the AI knows about a technology in general, kept apart from what was found in the code. */
function GeneralKnowledge({ explanation }: { explanation: TechnologyExplanation }) {
  return (
    <div className="space-y-3 border-t border-line px-3 py-3 text-sm">
      <div className="space-y-3 border-l-2 border-dashed border-hint/70 pl-3">
        <p className="text-xs text-hint">General knowledge, not taken from this repository</p>
        <p className="leading-relaxed">{explanation.what_it_is}</p>
        <dl className="grid gap-3 sm:grid-cols-3">
          <List title="Advantages" items={explanation.advantages} />
          <List title="Alternatives" items={explanation.alternatives} />
          <List title="Trade-offs" items={explanation.trade_offs} />
        </dl>
        {explanation.plausible_reason && (
          <p className="text-muted">
            <span className="text-ink/85">A possible reason it was chosen</span> (not documented in the
            repository): {explanation.plausible_reason}
          </p>
        )}
      </div>
    </div>
  )
}

function TechnologyItem({
  tech,
  explanation,
  repositoryId,
}: {
  tech: Technology
  explanation: TechnologyExplanation | undefined
  repositoryId: string
}) {
  return (
    <li>
      <details className="group rounded-lg border border-line bg-canvas open:w-full open:basis-full">
        <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-1.5 text-sm hover:text-mark">
          <span className="font-medium">{tech.name}</span>
          {tech.dev_only && (
            <span className="text-xs text-muted" title="Only a development dependency, used only from tests">
              development only
            </span>
          )}
          <span className="text-xs text-faint">
            {tech.evidence.length} {tech.evidence.length === 1 ? 'source' : 'sources'}
          </span>
        </summary>
        {explanation && (
          <p className="border-t border-line px-3 pt-2.5 text-xs text-muted">Found in this repository</p>
        )}
        <ul className={cn('space-y-1.5 px-3 text-sm', explanation ? 'pt-1.5 pb-2.5' : 'border-t border-line py-2.5')}>
          {tech.evidence.map((item, index) => (
            <li key={index} className="flex flex-wrap items-baseline gap-x-2">
              <span className="text-faint">{KIND_LABELS[item.kind]}</span>
              <Link
                to={fileLink(repositoryId, item.path, item.line)}
                className="font-mono text-[13px] text-mark hover:underline"
              >
                {item.path}
                {item.line ? `:${item.line}` : ''}
              </Link>
              {item.kind !== 'file' && (
                <span className="text-muted">
                  {item.detail}
                  {item.scope && SCOPE_NOTES[item.scope] ? `, ${SCOPE_NOTES[item.scope]}` : ''}
                </span>
              )}
            </li>
          ))}
        </ul>
        {explanation && <GeneralKnowledge explanation={explanation} />}
      </details>
    </li>
  )
}

function groupByCategory(technologies: Technology[]): Array<[string, Technology[]]> {
  const groups = new Map<string, Technology[]>()
  for (const tech of technologies) groups.set(tech.category, [...(groups.get(tech.category) ?? []), tech])
  return [...groups]
}

export default function TechnologyList({
  technologies,
  repositoryId,
  explanations = [],
}: {
  technologies: Technology[]
  repositoryId: string
  /** AI explanations, matched to technologies by name. */
  explanations?: TechnologyExplanation[]
}) {
  const explained = new Map(explanations.map((item) => [item.name.toLowerCase(), item]))

  if (technologies.length === 0) {
    return <p className="text-sm text-muted">No frameworks or libraries were detected in this repository.</p>
  }

  return (
    <div className="space-y-6">
      {groupByCategory(technologies).map(([category, items]) => (
        <div key={category}>
          <h3 className="mb-2 text-sm text-muted">{category}</h3>
          <ul className="flex flex-wrap gap-2">
            {items.map((tech) => (
              <TechnologyItem
                key={tech.name}
                tech={tech}
                explanation={explained.get(tech.name.toLowerCase())}
                repositoryId={repositoryId}
              />
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}
