import type { ReportContent } from '../api/ai'
import type { Report } from '../api/mock'
import { fileSafe, mockReportMarkdown, notesMarkdown } from './exportReport'

const WHEN = new Date('2026-11-04T09:00:00Z')
const cite = { path: 'src/app.py', start_line: 5, end_line: 9, quote: 'class App:' }

const notes: ReportContent = {
  pitch: 'I built a small framework.\nIt routes requests.',
  problem: 'Web apps should be simple.',
  walkthrough: [
    { statement: 'Requests reach App.', citations: [cite], verified: true, ungrounded_paths: [] },
    { statement: 'Something unconfirmed.', citations: [], verified: false, ungrounded_paths: [] },
  ],
  decisions: [
    {
      finding: { statement: 'Routing uses decorators.', citations: [{ ...cite, end_line: 5 }], verified: true, ungrounded_paths: [] },
      alternatives: ['A routing table', 'Classes'],
      trade_offs: ['Less explicit'],
    },
  ],
  highlights: [],
  improvements: [{ idea: 'Add type hints', reason: 'They are missing.' }],
  ungrounded_paths: [],
  removed_citations: 0,
}

describe('notesMarkdown', () => {
  const text = notesMarkdown('pallets/flask', notes, WHEN)

  it('starts with the title and the date', () => {
    expect(text.startsWith('# Interview notes: pallets/flask\nWritten by RepInspect on 2026-11-04.')).toBe(true)
  })

  it('quotes the pitch and numbers the walkthrough with where each step is in the code', () => {
    expect(text).toContain('> I built a small framework.\n> It routes requests.')
    expect(text).toContain('1. Requests reach App. (`src/app.py:5–9`)')
  })

  it('marks statements the code does not confirm as inference', () => {
    expect(text).toContain('2. Something unconfirmed. *(inference, not confirmed by the code)*')
  })

  it('lists decisions with their alternatives and trade-offs, and the weak spots', () => {
    expect(text).toContain('- Routing uses decorators. (`src/app.py:5`)\n  - Alternatives: A routing table; Classes\n  - Trade-offs: Less explicit')
    expect(text).toContain('- Add type hints: They are missing.')
  })

  it('leaves out sections with nothing in them', () => {
    expect(text).not.toContain('Worth bringing up')
  })
})

describe('mockReportMarkdown', () => {
  const report: Report = {
    questions_answered: 4,
    skipped: 1,
    follow_ups_answered: 2,
    average_score: 3,
    percent: 75,
    follow_up_average: 2,
    by_category: [{ category: 'architecture', label: 'Architecture', average: 3.25, count: 2 }],
    strengths: ['Clear explanations'],
    gaps: ['Error handling'],
    contradicted_claims: [{ claim: 'It uses Flask.', verdict: 'contradicted', citations: [cite] }],
    files_to_review: ['src/app.py'],
  }
  const text = mockReportMarkdown('pallets/flask', report, WHEN)

  it('summarises the score', () => {
    expect(text).toContain('**Overall: 75%** (4 questions, 1 skipped, 2 follow-ups)')
    expect(text).toContain('- Architecture: 3.3/4 (2)')
  })

  it('includes what to work on, strengths, contradicted statements and files to read', () => {
    expect(text).toContain('## What to work on\n\n- Error handling')
    expect(text).toContain('## What you did well\n\n- Clear explanations')
    expect(text).toContain('- It uses Flask. (`src/app.py:5–9`)')
    expect(text).toContain('- `src/app.py`')
  })
})

describe('fileSafe', () => {
  it('makes a name safe for a file', () => {
    expect(fileSafe('Interview notes pallets/flask')).toBe('interview-notes-pallets-flask')
  })
})
