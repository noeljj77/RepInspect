import { Link } from 'react-router'

import type { Citation, Finding } from '../../api/ai'
import { citationPlace, fileLink } from '../../lib/links'

/** A confirmed quote from the repository, linking to the exact lines. */
export function CitationLink({
  repositoryId,
  citation,
  label,
}: {
  repositoryId: string
  citation: Citation
  /** Shown before the location, e.g. "[2]" to match a marker in an answer. */
  label?: string
}) {
  return (
    <Link
      to={fileLink(repositoryId, citation.path, citation.start_line)}
      className="group block min-w-0 rounded-md border border-mark/20 bg-mark/[0.07] px-2.5 py-1.5 hover:border-mark/50"
    >
      <span className="block font-mono text-[12px] wrap-anywhere text-mark group-hover:underline">
        {label && <span className="mr-1.5 text-mark/70">{label}</span>}
        {citationPlace(citation)}
      </span>
      <code className="mt-0.5 block font-mono text-[12.5px] leading-5 whitespace-pre-wrap wrap-anywhere text-ink/85">
        {citation.quote}
      </code>
    </Link>
  )
}

/** Files the model named that are not in the repository. Shown so nothing is hidden. */
export function UngroundedPaths({ paths }: { paths: string[] }) {
  if (paths.length === 0) return null
  return (
    <p className="text-xs text-muted">
      Mentions {paths.length === 1 ? 'a file that is' : 'files that are'} not in this repository:{' '}
      <span className="font-mono">{paths.join(', ')}</span>
    </p>
  )
}

/**
 * Statements backed by code get the amber highlighter rule and their quotes.
 * Statements the server could not confirm get a dashed periwinkle rule and say so.
 */
export function FindingList({ repositoryId, findings }: { repositoryId: string; findings: Finding[] }) {
  if (findings.length === 0) return null
  return (
    <ul className="space-y-3">
      {findings.map((finding, index) => (
        <li
          key={index}
          className={
            finding.verified
              ? 'border-l-2 border-mark pl-3'
              : 'border-l-2 border-dashed border-hint/70 pl-3'
          }
        >
          <p className="leading-relaxed">
            {finding.verified && <span className="sr-only">Backed by code: </span>}
            {finding.statement}
          </p>
          {finding.verified ? (
            <div className="mt-2 space-y-1.5">
              {finding.citations.map((citation, i) => (
                <CitationLink key={i} repositoryId={repositoryId} citation={citation} />
              ))}
            </div>
          ) : (
            <p className="mt-1 text-xs text-hint">Inference, not confirmed in the code</p>
          )}
          {finding.ungrounded_paths.length > 0 && (
            <div className="mt-1.5">
              <UngroundedPaths paths={finding.ungrounded_paths} />
            </div>
          )}
        </li>
      ))}
    </ul>
  )
}
