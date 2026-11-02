import { Link } from 'react-router'

import type { Evidence, Technology } from '../../api/repositories'
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

function groupByCategory(technologies: Technology[]): Array<[string, Technology[]]> {
  const groups = new Map<string, Technology[]>()
  for (const tech of technologies) groups.set(tech.category, [...(groups.get(tech.category) ?? []), tech])
  return [...groups]
}

export default function TechnologyList({
  technologies,
  repositoryId,
}: {
  technologies: Technology[]
  repositoryId: string
}) {
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
              <li key={tech.name}>
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
                  <ul className="space-y-1.5 border-t border-line px-3 py-2.5 text-sm">
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
                </details>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}
