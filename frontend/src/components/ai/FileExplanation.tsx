import type { FileExplanationContent } from '../../api/ai'
import ExplanationPanel from './ExplanationPanel'
import { FindingList, UngroundedPaths } from './Findings'

function Content({
  repositoryId,
  content,
  onSelectLine,
}: {
  repositoryId: string
  content: FileExplanationContent
  onSelectLine: (line: number) => void
}) {
  return (
    <div className="max-w-[80ch] space-y-4 text-[15px]">
      {content.determined ? (
        <p className="leading-relaxed">{content.purpose}</p>
      ) : (
        <p className="text-sm text-muted">
          The purpose of this file could not be determined from its contents.
          {content.purpose && <span className="mt-1 block">{content.purpose}</span>}
        </p>
      )}

      {content.inputs_outputs && (
        <div>
          <h4 className="text-sm text-muted">Inputs and outputs</h4>
          <p className="mt-0.5 leading-relaxed text-ink/90">{content.inputs_outputs}</p>
        </div>
      )}

      {content.key_symbols.length > 0 && (
        <div>
          <h4 className="text-sm text-muted">Key parts</h4>
          <ul className="mt-1 space-y-1.5">
            {content.key_symbols.map((symbol) => (
              <li key={`${symbol.qualified_name}:${symbol.start_line}`} className="text-sm leading-relaxed">
                <button
                  type="button"
                  onClick={() => onSelectLine(symbol.start_line)}
                  className="mr-2 font-mono text-[13px] text-mark-text hover:underline"
                  title={`Go to line ${symbol.start_line}`}
                >
                  {symbol.qualified_name}
                </button>
                <span className="text-ink/85">{symbol.explanation}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <FindingList repositoryId={repositoryId} findings={content.findings} />
      <UngroundedPaths paths={content.ungrounded_paths} />
    </div>
  )
}

export default function FileExplanation({
  repositoryId,
  path,
  onSelectLine,
}: {
  repositoryId: string
  path: string
  onSelectLine: (line: number) => void
}) {
  return (
    <section aria-label="Explanation of this file" className="mb-4 rounded-lg border border-line bg-surface px-4 py-3.5">
      <ExplanationPanel
        repositoryId={repositoryId}
        kind="file"
        path={path}
        actionLabel="Explain this file"
        intro={<p>Get a plain-language summary of what this file does, its key parts, and what goes in and out.</p>}
      >
        {(content) => <Content repositoryId={repositoryId} content={content} onSelectLine={onSelectLine} />}
      </ExplanationPanel>
    </section>
  )
}
