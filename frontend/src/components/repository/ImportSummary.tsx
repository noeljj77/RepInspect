import { AlertTriangle, ShieldCheck } from 'lucide-react'

import type { AnalysisSummary } from '../../api/repositories'
import { formatBytes } from '../../lib/format'

// Plain-language names for why a file was left out.
const SKIP_LABELS: Record<string, string> = {
  sensitive: 'Sensitive files, such as .env and private keys',
  binary: 'Images, fonts and other binary files',
  lockfile: 'Dependency lock files',
  generated: 'Minified and generated files',
  too_large: 'Files that are too large',
  ignored_directory: 'Files in dependency and build folders',
  unsupported_name: 'Files with names that cannot be stored safely',
  special_file: 'Links and special files',
  unwritable: 'Files that could not be stored',
}

export default function ImportSummary({ analysis }: { analysis: AnalysisSummary }) {
  const skipped = Object.entries(analysis.skipped_summary ?? {}).sort((a, b) => b[1] - a[1])

  return (
    <section aria-labelledby="import-heading" className="rounded-xl border border-line bg-surface p-5">
      <h2 id="import-heading" className="font-semibold">
        What was imported
      </h2>
      <p className="mt-2 text-sm">
        <span className="text-xl font-semibold">{analysis.file_count.toLocaleString('en')}</span>{' '}
        <span className="text-muted">
          {analysis.file_count === 1 ? 'file' : 'files'} · {formatBytes(analysis.total_bytes)}
        </span>
      </p>

      {analysis.truncated && (
        <p className="mt-3 flex gap-2 rounded-md border border-mark/30 px-3 py-2 text-sm text-mark-text">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>This repository is large, so only the first files were imported. The rest were left out.</span>
        </p>
      )}

      {analysis.redaction_count > 0 && (
        <p className="mt-3 flex gap-2 text-sm text-muted">
          <ShieldCheck size={16} className="mt-0.5 shrink-0 text-ok" aria-hidden="true" />
          <span>
            {analysis.redaction_count} {analysis.redaction_count === 1 ? 'value that looked' : 'values that looked'} like
            a password or key {analysis.redaction_count === 1 ? 'was' : 'were'} hidden before the code was stored.
          </span>
        </p>
      )}

      {skipped.length > 0 && (
        <details className="mt-4 text-sm">
          <summary className="cursor-pointer text-muted hover:text-ink">
            {skipped.reduce((sum, [, count]) => sum + count, 0).toLocaleString('en')} files left out
          </summary>
          <dl className="mt-3 space-y-1.5">
            {skipped.map(([reason, count]) => (
              <div key={reason} className="flex justify-between gap-4">
                <dt className="text-muted">{SKIP_LABELS[reason] ?? reason}</dt>
                <dd>{count.toLocaleString('en')}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </section>
  )
}
