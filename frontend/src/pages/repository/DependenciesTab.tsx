import { useMemo, useState } from 'react'
import { Link } from 'react-router'

import type { Dependency } from '../../api/repositories'
import { useDependencies } from '../../hooks/useRepositories'
import { useRepositoryContext } from '../../hooks/useRepositoryContext'
import { cn } from '../../lib/cn'
import { fileLink } from '../../lib/links'

const ECOSYSTEMS: Record<string, string> = { pypi: 'Python', npm: 'npm', maven: 'Maven and Gradle' }
const SCOPE_LABELS: Record<string, string> = {
  runtime: 'Runtime',
  dev: 'Development',
  optional: 'Optional',
  peer: 'Peer',
  build: 'Build',
  plugin: 'Plugin',
  managed: 'Managed version',
}

function groupBySource(dependencies: Dependency[]): Array<[string, Dependency[]]> {
  const groups = new Map<string, Dependency[]>()
  for (const dep of dependencies) groups.set(dep.source_file, [...(groups.get(dep.source_file) ?? []), dep])
  return [...groups]
}

const selectClass =
  'h-9 rounded-md border border-line bg-canvas px-2 text-sm hover:border-faint focus:border-mark focus:outline-none focus:ring-1 focus:ring-mark'

export default function DependenciesTab() {
  const { repository } = useRepositoryContext()
  const { data, isPending, isError } = useDependencies(repository.id)
  const [query, setQuery] = useState('')
  const [scope, setScope] = useState('all')

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (data ?? []).filter(
      (dep) => (scope === 'all' || dep.scope === scope) && (!needle || dep.name.toLowerCase().includes(needle)),
    )
  }, [data, query, scope])
  const scopes = useMemo(() => [...new Set((data ?? []).map((dep) => dep.scope))], [data])

  if (isPending) {
    return (
      <p role="status" className="text-sm text-muted">
        Loading dependencies…
      </p>
    )
  }
  if (isError) {
    return (
      <p role="alert" className="text-sm text-danger">
        The dependencies could not be loaded. Try refreshing the page.
      </p>
    )
  }
  if (data.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-line px-6 py-10">
        <h2 className="font-semibold">No dependencies found</h2>
        <p className="mt-1.5 max-w-lg text-sm text-muted">
          RepInspect reads requirements.txt, pyproject.toml, package.json, pom.xml and Gradle build files. None of
          them declared a dependency in this repository.
        </p>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-5 flex flex-wrap gap-3">
        <input
          type="search"
          aria-label="Search dependencies"
          placeholder="Search dependencies"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className={cn(selectClass, 'w-full max-w-xs placeholder:text-faint')}
        />
        <select aria-label="Filter by type" value={scope} onChange={(event) => setScope(event.target.value)} className={selectClass}>
          <option value="all">All types</option>
          {scopes.map((value) => (
            <option key={value} value={value}>
              {SCOPE_LABELS[value] ?? value}
            </option>
          ))}
        </select>
      </div>

      {filtered.length === 0 ? (
        <p className="text-sm text-muted">No dependencies match these filters.</p>
      ) : (
        <div className="space-y-6">
          {groupBySource(filtered).map(([source, deps]) => (
            <section key={source} aria-label={source} className="overflow-hidden rounded-xl border border-line bg-surface">
              <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line px-5 py-3">
                <Link to={fileLink(repository.id, source)} className="font-mono text-[13px] text-mark hover:underline">
                  {source}
                </Link>
                <span className="text-sm text-muted">
                  {ECOSYSTEMS[deps[0].ecosystem]}, {deps.length} {deps.length === 1 ? 'dependency' : 'dependencies'}
                </span>
              </header>
              <table className="w-full text-sm">
                <thead className="sr-only">
                  <tr>
                    <th scope="col">Name</th>
                    <th scope="col">Version</th>
                    <th scope="col">Type</th>
                    <th scope="col">Line</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {deps.map((dep, index) => (
                    <tr key={`${dep.name}:${dep.scope}:${index}`}>
                      <td className="px-5 py-2 font-mono text-[13px] break-all">{dep.name}</td>
                      <td className="px-3 py-2 text-muted">{dep.version_spec ?? 'any version'}</td>
                      <td className="px-3 py-2 text-muted">{SCOPE_LABELS[dep.scope] ?? dep.scope}</td>
                      <td className="px-5 py-2 text-right">
                        {dep.line ? (
                          <Link
                            to={fileLink(repository.id, dep.source_file, dep.line)}
                            className="text-faint hover:text-ink"
                            aria-label={`Line ${dep.line} in ${dep.source_file}`}
                          >
                            {dep.line}
                          </Link>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
