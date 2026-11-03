import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { Citation } from '../../api/ai'
import { citationPlace, fileLink } from '../../lib/links'

// `code` spans and citation markers such as [1] or [1, 3].
const INLINE = /(`[^`\n]+`|\[\d+(?:,\s*\d+)*\])/g
const BULLET = /^\s*[-*]\s+/
const NUMBERED = /^\s*\d+[.)]\s+/

function Marker({ numbers, citations, repositoryId }: { numbers: number[]; citations: Citation[]; repositoryId: string }) {
  return (
    <>
      {numbers.map((number) => {
        const citation = citations[number - 1]
        if (!citation) return null
        return (
          <Link
            key={number}
            to={fileLink(repositoryId, citation.path, citation.start_line)}
            title={citationPlace(citation)}
            aria-label={`Source ${number}: ${citationPlace(citation)}`}
            className="mx-0.5 inline-block rounded bg-mark/15 px-1.5 align-baseline font-mono text-[12px] leading-5 text-mark-text hover:bg-mark/25"
          >
            {number}
          </Link>
        )
      })}
    </>
  )
}

const LEADING_PUNCTUATION = /^[.,;:!?)]+/

function inline(text: string, citations: Citation[], repositoryId: string): ReactNode[] {
  const parts = text.split(INLINE)
  return parts.map((part, index) => {
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return (
        <code key={index} className="rounded bg-raised px-1 py-px font-mono text-[13px]">
          {part.slice(1, -1)}
        </code>
      )
    }
    if (/^\[\d+(?:,\s*\d+)*\]$/.test(part)) {
      const numbers = part.slice(1, -1).split(',').map((n) => Number(n.trim()))
      // Keep "[2]." together, so a full stop never wraps onto a line of its own.
      const punctuation = LEADING_PUNCTUATION.exec(parts[index + 1] ?? '')?.[0] ?? ''
      if (punctuation) parts[index + 1] = parts[index + 1].slice(punctuation.length)
      return (
        <span key={index} className="whitespace-nowrap">
          <Marker numbers={numbers} citations={citations} repositoryId={repositoryId} />
          {punctuation}
        </span>
      )
    }
    return part
  })
}

type Block = { kind: 'p' | 'ul' | 'ol'; lines: string[] } | { kind: 'code'; text: string }

/** Paragraphs, bullet lists, numbered lists and fenced code, from plain text. */
function toBlocks(text: string): Block[] {
  const blocks: Block[] = []
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  let index = 0
  while (index < lines.length) {
    const line = lines[index]
    if (line.trimStart().startsWith('```')) {
      const body: string[] = []
      index += 1
      while (index < lines.length && !lines[index].trimStart().startsWith('```')) body.push(lines[index++])
      index += 1
      blocks.push({ kind: 'code', text: body.join('\n') })
      continue
    }
    if (!line.trim()) {
      index += 1
      continue
    }
    const kind = BULLET.test(line) ? 'ul' : NUMBERED.test(line) ? 'ol' : 'p'
    const pattern = kind === 'ul' ? BULLET : NUMBERED
    const group: string[] = []
    while (index < lines.length && lines[index].trim() && !lines[index].trimStart().startsWith('```')) {
      const current = lines[index]
      if (kind !== 'p' && !pattern.test(current) && group.length > 0) {
        group[group.length - 1] += ' ' + current.trim() // a wrapped list item
      } else if (kind !== 'p' && pattern.test(current)) {
        group.push(current.replace(pattern, ''))
      } else if (kind === 'p' && (BULLET.test(current) || NUMBERED.test(current))) {
        break // a list starts right after a paragraph line
      } else {
        group.push(current.trim())
      }
      index += 1
    }
    blocks.push(kind === 'p' ? { kind, lines: [group.join(' ')] } : { kind, lines: group })
  }
  return blocks
}

/**
 * Renders an answer written as plain text. Nothing is interpreted as HTML: the text is
 * split into React elements, so a model cannot inject markup or scripts into the page.
 */
export default function AnswerText({
  text,
  citations,
  repositoryId,
}: {
  text: string
  citations: Citation[]
  repositoryId: string
}) {
  return (
    <div className="space-y-3 leading-relaxed text-ink/90">
      {toBlocks(text).map((block, index) => {
        if (block.kind === 'code') {
          return (
            <pre key={index} className="overflow-x-auto rounded-md bg-canvas px-3 py-2 font-mono text-[13px] leading-6">
              {block.text}
            </pre>
          )
        }
        if (block.kind === 'p') return <p key={index}>{inline(block.lines[0], citations, repositoryId)}</p>
        const List = block.kind
        return (
          <List
            key={index}
            className={`space-y-1 pl-5 marker:text-faint ${block.kind === 'ul' ? 'list-disc' : 'list-decimal'}`}
          >
            {block.lines.map((line, i) => (
              <li key={i}>{inline(line, citations, repositoryId)}</li>
            ))}
          </List>
        )
      })}
    </div>
  )
}
