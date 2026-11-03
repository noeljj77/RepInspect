import type { CodeStats } from '../../api/repositories'

function Stat({ label, value, hint }: { label: string; value: number; hint?: string }) {
  return (
    <div>
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="mt-0.5 text-xl font-semibold tabular-nums">{value.toLocaleString('en')}</dd>
      {hint && <p className="mt-0.5 text-xs text-faint">{hint}</p>}
    </div>
  )
}

export default function StatsGrid({ stats }: { stats: CodeStats }) {
  const { totals } = stats
  const kinds = totals.symbols_by_kind
  const functions = (kinds.function ?? 0) + (kinds.method ?? 0)
  const types = (kinds.class ?? 0) + (kinds.interface ?? 0) + (kinds.enum ?? 0) + (kinds.type ?? 0)

  return (
    <section aria-labelledby="stats-heading" className="rounded-xl border border-line bg-surface p-5">
      <h2 id="stats-heading" className="font-semibold">
        Statistics
      </h2>
      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-5">
        <Stat label="Files" value={totals.files} />
        <Stat label="Lines of code" value={totals.code_lines} />
        <Stat label="Functions and methods" value={functions} />
        <Stat label="Classes and types" value={types} />
        <Stat label="Dependencies" value={totals.dependencies} />
        <Stat label="Test files" value={totals.test_files} />
      </dl>
      {totals.imports > 0 && (
        <p className="mt-4 text-sm text-muted">
          {totals.internal_imports.toLocaleString('en')} of {totals.imports.toLocaleString('en')} imports link one
          file in this repository to another.
        </p>
      )}
      {totals.parse_errors > 0 && (
        <p className="mt-2 text-sm text-muted">
          {totals.parse_errors} {totals.parse_errors === 1 ? 'file has' : 'files have'} syntax the parser could
          not fully read, so their outlines may be incomplete.
        </p>
      )}
    </section>
  )
}
