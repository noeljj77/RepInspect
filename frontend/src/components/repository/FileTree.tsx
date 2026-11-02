import { ChevronRight, File as FileIcon, FileX, Folder, FolderOpen, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'

import type { FileEntry } from '../../api/repositories'
import { cn } from '../../lib/cn'
import { ancestorFolders, buildTree, searchFiles, type FolderNode, type TreeNode } from '../../lib/fileTree'
import { fileLink } from '../../lib/links'

const SKIP_LABELS: Record<string, string> = {
  sensitive: 'Not imported: may contain secrets',
  binary: 'Not imported: binary file',
  lockfile: 'Not imported: dependency lock file',
  generated: 'Not imported: generated file',
  too_large: 'Not imported: too large',
}

interface Props {
  repositoryId: string
  files: FileEntry[]
  selectedPath: string | null
}

function FileRow({ file, depth, repositoryId, selected }: { file: FileEntry; depth: number; repositoryId: string; selected: boolean }) {
  const name = file.path.split('/').pop()
  const padding = { paddingLeft: `${depth * 14 + 10}px` }

  if (file.skipped_reason) {
    return (
      <li
        style={padding}
        title={SKIP_LABELS[file.skipped_reason] ?? `Not imported: ${file.skipped_reason}`}
        className="flex h-7 items-center gap-2 pr-2 text-sm text-faint"
      >
        <FileX size={14} className="shrink-0" aria-hidden="true" />
        <span className="truncate">{name}</span>
        <span className="sr-only">{SKIP_LABELS[file.skipped_reason] ?? 'Not imported'}</span>
      </li>
    )
  }

  return (
    <li>
      <Link
        to={fileLink(repositoryId, file.path)}
        style={padding}
        aria-current={selected ? 'true' : undefined}
        className={cn(
          'flex h-7 items-center gap-2 rounded-md pr-2 text-sm transition-colors',
          selected ? 'bg-raised text-ink' : 'text-muted hover:bg-raised/60 hover:text-ink',
        )}
      >
        <FileIcon size={14} className="shrink-0" aria-hidden="true" />
        <span className="truncate">{name}</span>
        {file.importance_score >= 30 && (
          <>
            <span className="ml-auto size-1.5 shrink-0 rounded-full bg-mark" title="Important file" aria-hidden="true" />
            <span className="sr-only">, important file</span>
          </>
        )}
      </Link>
    </li>
  )
}

function Branch({
  nodes,
  depth,
  expanded,
  onToggle,
  repositoryId,
  selectedPath,
}: {
  nodes: TreeNode[]
  depth: number
  expanded: Set<string>
  onToggle: (path: string) => void
  repositoryId: string
  selectedPath: string | null
}) {
  return (
    <ul>
      {nodes.map((node) => {
        if (node.type === 'file') {
          return (
            <FileRow
              key={node.path}
              file={node.file}
              depth={depth}
              repositoryId={repositoryId}
              selected={node.path === selectedPath}
            />
          )
        }
        const open = expanded.has(node.path)
        return (
          <li key={node.path}>
            <button
              type="button"
              onClick={() => onToggle(node.path)}
              aria-expanded={open}
              style={{ paddingLeft: `${depth * 14 + 4}px` }}
              className="flex h-7 w-full items-center gap-1.5 rounded-md pr-2 text-left text-sm text-muted transition-colors hover:bg-raised/60 hover:text-ink"
            >
              <ChevronRight
                size={14}
                className={cn('shrink-0 transition-transform', open && 'rotate-90')}
                aria-hidden="true"
              />
              {open ? <FolderOpen size={14} aria-hidden="true" /> : <Folder size={14} aria-hidden="true" />}
              <span className="truncate">{node.name}</span>
            </button>
            {open && (
              <Branch
                nodes={node.children}
                depth={depth + 1}
                expanded={expanded}
                onToggle={onToggle}
                repositoryId={repositoryId}
                selectedPath={selectedPath}
              />
            )}
          </li>
        )
      })}
    </ul>
  )
}

export default function FileTree({ repositoryId, files, selectedPath }: Props) {
  const root: FolderNode = useMemo(() => buildTree(files), [files])
  const [query, setQuery] = useState('')
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(ancestorFolders(selectedPath ?? '')))

  // When a different file is selected (a link, or the back button), open the folders
  // that contain it. Done during render, as React recommends for state that follows props.
  const [shownPath, setShownPath] = useState(selectedPath)
  if (selectedPath !== shownPath) {
    setShownPath(selectedPath)
    if (selectedPath) setExpanded((current) => new Set([...current, ...ancestorFolders(selectedPath)]))
  }

  const results = useMemo(() => searchFiles(files, query), [files, query])

  function toggle(path: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (!next.delete(path)) next.add(path)
      return next
    })
  }

  return (
    <div className="flex min-h-0 flex-col">
      <div className="relative mb-2">
        <Search size={14} className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-faint" aria-hidden="true" />
        <input
          type="search"
          aria-label="Search files"
          placeholder="Search files"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="h-8 w-full rounded-md border border-line bg-canvas pr-2 pl-8 text-sm placeholder:text-faint hover:border-faint focus:border-mark focus:outline-none focus:ring-1 focus:ring-mark"
        />
      </div>

      <nav aria-label="Files" className="min-h-0 flex-1 overflow-auto pb-2">
        {query.trim() ? (
          results.length > 0 ? (
            <ul>
              {results.map((file) => (
                <FileRow key={file.path} file={file} depth={0} repositoryId={repositoryId} selected={file.path === selectedPath} />
              ))}
            </ul>
          ) : (
            <p className="px-2 py-3 text-sm text-muted">No files match “{query.trim()}”.</p>
          )
        ) : (
          <Branch
            nodes={root.children}
            depth={0}
            expanded={expanded}
            onToggle={toggle}
            repositoryId={repositoryId}
            selectedPath={selectedPath}
          />
        )}
      </nav>
    </div>
  )
}
