import { AlertTriangle } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { FileContent } from '../../api/repositories'
import { useFileContent } from '../../hooks/useRepositories'
import { formatBytes } from '../../lib/format'
import { fileLink } from '../../lib/links'
import FileExplanation from '../ai/FileExplanation'
import FileNotes from '../library/FileNotes'
import CodeViewer from './CodeViewer'

const KIND_LABELS: Record<string, string> = {
  function: 'function',
  method: 'method',
  class: 'class',
  interface: 'interface',
  enum: 'enum',
  type: 'type',
}

function Panel({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  return (
    <details open={count > 0 && count <= 40} className="border-b border-line py-3 first:pt-0 last:border-b-0">
      <summary className="flex cursor-pointer items-baseline justify-between text-sm font-medium">
        {title}
        <span className="text-xs font-normal text-faint">{count}</span>
      </summary>
      <div className="mt-2">{count === 0 ? <p className="text-sm text-muted">None.</p> : children}</div>
    </details>
  )
}

function Insights({
  repositoryId,
  file,
  line,
  onSelectLine,
}: {
  repositoryId: string
  file: FileContent
  line: number | null
  onSelectLine: (line: number) => void
}) {
  return (
    <aside aria-label="File details" className="min-w-0">
      <Panel title="Outline" count={file.symbols.length}>
        <ul className="space-y-0.5">
          {file.symbols.map((symbol) => (
            <li key={`${symbol.qualified_name}:${symbol.start_line}`}>
              <button
                type="button"
                onClick={() => onSelectLine(symbol.start_line)}
                title={symbol.signature}
                className="flex w-full items-baseline gap-2 rounded px-1.5 py-1 text-left text-sm hover:bg-raised/60"
              >
                <span className="w-14 shrink-0 text-xs text-faint">{KIND_LABELS[symbol.kind] ?? symbol.kind}</span>
                <span className="min-w-0 flex-1 truncate font-mono text-[13px]">{symbol.qualified_name}</span>
                <span className="shrink-0 text-xs text-faint">{symbol.start_line}</span>
              </button>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title="Imports" count={file.imports.length}>
        <ul className="space-y-1">
          {file.imports.map((item, index) => (
            <li key={index} className="text-sm">
              <button
                type="button"
                onClick={() => onSelectLine(item.line)}
                className="mr-2 text-xs text-faint hover:text-ink"
                aria-label={`Go to line ${item.line}`}
              >
                {item.line}
              </button>
              {item.resolved_path ? (
                <Link
                  to={fileLink(repositoryId, item.resolved_path)}
                  className="font-mono text-[13px] text-mark-text hover:underline"
                >
                  {item.module}
                </Link>
              ) : (
                <span className="font-mono text-[13px] text-muted">{item.module}</span>
              )}
              {item.resolved_path && (
                <span className="block truncate pl-6 text-xs text-faint">{item.resolved_path}</span>
              )}
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title="Imported by" count={file.imported_by.length}>
        <ul className="space-y-1">
          {file.imported_by.map((path) => (
            <li key={path} className="truncate">
              <Link to={fileLink(repositoryId, path)} className="font-mono text-[13px] text-mark-text hover:underline">
                {path}
              </Link>
            </li>
          ))}
        </ul>
      </Panel>
      <FileNotes repositoryId={repositoryId} path={file.path} line={line} />
    </aside>
  )
}

interface Props {
  repositoryId: string
  path: string
  line: number | null
  onSelectLine: (line: number) => void
}

export default function FileViewer({ repositoryId, path, line, onSelectLine }: Props) {
  const { data: file, isPending, isError } = useFileContent(repositoryId, path)

  if (isPending) {
    return (
      <p role="status" className="text-sm text-muted">
        Loading {path}…
      </p>
    )
  }
  if (isError) {
    return (
      <p role="alert" className="text-sm text-danger">
        This file could not be opened. It may not have been imported.
      </p>
    )
  }

  return (
    <div className="min-w-0">
      <header className="mb-3">
        <h2 className="font-mono text-[15px] break-all">{file.path}</h2>
        <p className="mt-1 text-sm text-muted">
          {[file.language, file.line_count !== null ? `${file.line_count.toLocaleString('en')} lines` : null, formatBytes(file.size_bytes)]
            .filter(Boolean)
            .join(', ')}
        </p>
        {file.importance_reasons.length > 0 && (
          <p className="mt-1 text-sm text-mark-text">{file.importance_reasons.join(', ')}</p>
        )}
        {file.parse_error && (
          <p className="mt-2 flex gap-2 text-sm text-muted">
            <AlertTriangle size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
            Some of this file could not be parsed, so the outline and imports may be incomplete.
          </p>
        )}
      </header>

      {/* Keyed by path so a half-finished request for one file never shows on another. */}
      <FileExplanation key={file.path} repositoryId={repositoryId} path={file.path} onSelectLine={onSelectLine} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="min-w-0">
          <CodeViewer content={file.content} highlightLine={line} onSelectLine={onSelectLine} />
        </div>
        <Insights repositoryId={repositoryId} file={file} line={line} onSelectLine={onSelectLine} />
      </div>
    </div>
  )
}
