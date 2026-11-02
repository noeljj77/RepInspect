import { FileText } from 'lucide-react'
import { Link } from 'react-router'

import type { ImportantFile } from '../../api/repositories'
import { fileLink } from '../../lib/links'

export default function ImportantFiles({
  files,
  repositoryId,
}: {
  files: ImportantFile[]
  repositoryId: string
}) {
  if (files.length === 0) {
    return <p className="text-sm text-muted">No standout files were found.</p>
  }

  return (
    <ul className="divide-y divide-line">
      {files.map((file) => (
        <li key={file.path}>
          <Link
            to={fileLink(repositoryId, file.path)}
            className="-mx-2 flex items-start gap-3 rounded-md px-2 py-2.5 transition-colors hover:bg-raised/60"
          >
            <FileText size={16} className="mt-1 shrink-0 text-faint" aria-hidden="true" />
            <div className="min-w-0">
              <p className="truncate font-mono text-[13px]">{file.path}</p>
              <p className="mt-0.5 text-sm text-muted">{file.reasons.join(', ')}</p>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  )
}
