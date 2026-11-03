import type { Citation, Finding, ReportContent } from '../api/ai'
import type { ClaimCheck, Report } from '../api/mock'

const place = (c: Citation) => `\`${c.path}:${c.start_line}${c.end_line !== c.start_line ? `–${c.end_line}` : ''}\``

/** A statement, followed by where in the code it comes from, or a note that it is only inference. */
function finding(f: Finding): string {
  const sources = f.citations.map(place).join(', ')
  return f.verified && sources ? `${f.statement} (${sources})` : `${f.statement} *(inference, not confirmed by the code)*`
}

function claim(c: ClaimCheck): string {
  const sources = c.citations.map(place).join(', ')
  return sources ? `${c.claim} (${sources})` : c.claim
}

const list = (items: string[]) => items.map((item) => `- ${item}`).join('\n')

function section(title: string, body: string | null): string {
  return body ? `## ${title}\n\n${body}\n` : ''
}

const stamp = (when: Date) => when.toISOString().slice(0, 10)

/** The interview notes as Markdown, for reading outside the app or keeping with other notes. */
export function notesMarkdown(repositoryName: string, content: ReportContent, when: Date = new Date()): string {
  const decisions = content.decisions
    .map((d) => {
      const extra = [
        d.alternatives.length > 0 && `  - Alternatives: ${d.alternatives.join('; ')}`,
        d.trade_offs.length > 0 && `  - Trade-offs: ${d.trade_offs.join('; ')}`,
      ].filter(Boolean)
      return [`- ${finding(d.finding)}`, ...extra].join('\n')
    })
    .join('\n')

  return [
    `# Interview notes: ${repositoryName}`,
    `Written by RepInspect on ${stamp(when)}. Statements marked as inference are not confirmed by the code.\n`,
    section('When they say “tell me about this project”', content.pitch.split('\n').map((l) => `> ${l}`).join('\n')),
    section('The problem', content.problem || null),
    section('How it works', content.walkthrough.map((f, i) => `${i + 1}. ${finding(f)}`).join('\n') || null),
    section('Decisions you can explain', decisions || null),
    section('Worth bringing up', list(content.highlights.map(finding)) || null),
    section(
      'Weak spots to be ready for',
      list(content.improvements.map((i) => (i.reason ? `${i.idea}: ${i.reason}` : i.idea))) || null,
    ),
  ]
    .filter(Boolean)
    .join('\n')
}

/** A finished mock interview as Markdown. */
export function mockReportMarkdown(repositoryName: string, report: Report, when: Date = new Date()): string {
  const answered = `${report.questions_answered} ${report.questions_answered === 1 ? 'question' : 'questions'}`
  const extras = [
    report.skipped > 0 && `${report.skipped} skipped`,
    report.follow_ups_answered > 0 &&
      `${report.follow_ups_answered} ${report.follow_ups_answered === 1 ? 'follow-up' : 'follow-ups'}`,
  ].filter(Boolean)

  return [
    `# Mock interview report: ${repositoryName}`,
    `Written by RepInspect on ${stamp(when)}.\n`,
    `**Overall: ${report.percent ?? 0}%** (${[answered, ...extras].join(', ')})\n`,
    section(
      'By topic',
      list(report.by_category.map((c) => `${c.label}: ${c.average?.toFixed(1) ?? '–'}/4 (${c.count})`)) || null,
    ),
    section('What to work on', list(report.gaps) || null),
    section('What you did well', list(report.strengths) || null),
    section('Statements the code contradicts', list(report.contradicted_claims.map(claim)) || null),
    section('Read these files next', list(report.files_to_review.map((p) => `\`${p}\``)) || null),
  ]
    .filter(Boolean)
    .join('\n')
}

export function downloadText(filename: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

/** Opens the print dialog, where "Save as PDF" is the usual choice. The page title becomes the file name. */
export function printAsPdf(title: string): void {
  const previous = document.title
  document.title = title
  window.print()
  document.title = previous
}

export const fileSafe = (text: string) => text.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').toLowerCase()
