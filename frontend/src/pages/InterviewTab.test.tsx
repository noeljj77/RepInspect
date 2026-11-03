import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import type { ReportContent } from '../api/ai'
import type { Question, Questions } from '../api/interview'
import { explanation, REPO_ID, repositoryDetail } from '../test/fixtures'
import { ada, mockApi, type ApiRoutes } from '../test/mockApi'
import { renderRoute } from '../test/renderRoute'

const base = `/api/repositories/${REPO_ID}`
const url = `/repositories/${REPO_ID}/interview`
const CITE = { path: 'src/flask/app.py', start_line: 5, end_line: 5, quote: 'class Flask:' }

function report(): ReportContent {
  return {
    pitch: 'I built a small web framework.',
    problem: 'Writing web apps should be simple.',
    walkthrough: [{ statement: 'Requests reach the Flask class.', citations: [CITE], verified: true, ungrounded_paths: [] }],
    decisions: [
      {
        finding: { statement: 'Routing uses decorators.', citations: [CITE], verified: true, ungrounded_paths: [] },
        alternatives: ['A routing table'],
        trade_offs: ['Less explicit'],
      },
    ],
    highlights: [],
    improvements: [{ idea: 'Add type hints', reason: 'They are missing in places.' }],
    ungrounded_paths: [],
    removed_citations: 0,
  }
}

function question(overrides: Partial<Question> = {}): Question {
  return {
    id: 'q1',
    analysis_version: 1,
    category: 'architecture',
    difficulty: 'basic',
    question: 'What is the central object of the framework?',
    why_asked: 'Checks that you know the entry point.',
    answer_points: [{ statement: 'The Flask class is the app.', citations: [CITE], verified: true, ungrounded_paths: [] }],
    follow_ups: ['How is it configured?'],
    grounded: true,
    removed_citations: 0,
    status: 'new',
    user_answer: null,
    practiced_at: null,
    created_at: '2026-11-03T10:00:00Z',
    ...overrides,
  }
}

function questions(list: Question[], batch: Questions['latest_batch'] = null): Questions {
  const progress = { new: 0, practicing: 0, confident: 0 }
  list.forEach((q) => (progress[q.status] += 1))
  return { questions: list, latest_batch: batch, progress }
}

function open(routes: ApiRoutes = {}) {
  const fetchMock = mockApi({
    'GET /api/auth/me': { body: ada },
    [`GET ${base}`]: { body: repositoryDetail({ version: 2 }) },
    [`GET ${base}/questions`]: { body: questions([]) },
    ...routes,
  })
  return { fetchMock, ...renderRoute(url) }
}

const posted = (fetchMock: ReturnType<typeof open>['fetchMock'], method: string, target: string) =>
  fetchMock.mock.calls.filter(([input, init]) => String(input) === target && init?.method === method)

describe('Interview tab: notes', () => {
  it('appears in the repository tabs', async () => {
    open()

    const tabs = await screen.findByRole('navigation', { name: 'Repository sections' })
    expect(within(tabs).getByRole('link', { name: 'Interview' })).toHaveAttribute('href', url)
  })

  it('shows the pitch, the walkthrough with citations and suggestions marked as such', async () => {
    open({ [`GET ${base}/ai/report`]: { body: explanation('report', report()) } })

    const notes = await screen.findByRole('region', { name: 'Interview notes' })
    expect(await within(notes).findByText('I built a small web framework.')).toBeInTheDocument()
    expect(within(notes).getAllByRole('link', { name: /src\/flask\/app\.py:5/ })).toHaveLength(2)
    expect(notes).toHaveTextContent('Alternatives: A routing table')
    expect(notes).toHaveTextContent('Weak spots to be ready for')
    expect(notes).toHaveTextContent('Add type hints')
  })

  it('exports the notes as a Markdown file or through the print dialog', async () => {
    const user = userEvent.setup()
    let saved: Blob | undefined
    URL.createObjectURL = vi.fn((blob: Blob) => ((saved = blob), 'blob:notes'))
    URL.revokeObjectURL = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    open({ [`GET ${base}/ai/report`]: { body: explanation('report', report()) } })

    await user.click(await screen.findByText('Export'))
    await user.click(screen.getByRole('button', { name: 'Download as Markdown' }))

    expect(click).toHaveBeenCalledTimes(1)
    expect(await saved?.text()).toContain('# Interview notes: pallets/flask')
    await user.click(screen.getByText('Export'))
    await user.click(screen.getByRole('button', { name: 'Save as PDF' }))
    expect(print).toHaveBeenCalledTimes(1)
  })

  it('offers to write the notes', async () => {
    open()

    expect(await screen.findByRole('button', { name: 'Write my interview notes' })).toBeInTheDocument()
  })
})

describe('Interview tab: practice questions', () => {
  it('asks for questions with the chosen topics, count and difficulty', async () => {
    const user = userEvent.setup()
    const { fetchMock } = open({
      [`POST ${base}/questions`]: {
        status: 202,
        body: questions([], {
          id: 'b1',
          status: 'pending',
          requested_count: 5,
          question_count: 0,
          error_code: null,
          error_message: null,
          created_at: '2026-11-03T10:00:00Z',
          completed_at: null,
        }),
      },
    })

    await user.click(await screen.findByRole('button', { name: 'Security', pressed: false }))
    await user.selectOptions(screen.getByLabelText('How many'), '5')
    await user.selectOptions(screen.getByLabelText('Difficulty'), 'advanced')
    await user.click(screen.getByRole('button', { name: 'Write 5 questions' }))

    const [, init] = posted(fetchMock, 'POST', `${base}/questions`)[0]
    expect(JSON.parse(String(init?.body))).toEqual({ count: 5, difficulty: 'advanced', categories: ['security'] })
    expect(await screen.findByRole('status')).toHaveTextContent('Writing 5 questions from the code')
  })

  it('shows each question with its checked answer points and follow-ups', async () => {
    open({ [`GET ${base}/questions`]: { body: questions([question()]) } })

    const card = (await screen.findByRole('heading', { name: 'What is the central object of the framework?' })).closest(
      'article',
    ) as HTMLElement
    expect(card).toHaveTextContent('Architecture')
    expect(card).toHaveTextContent('Checks that you know the entry point.')
    expect(within(card).getByRole('link', { name: /src\/flask\/app\.py:5/ })).toBeInTheDocument()
    expect(card).toHaveTextContent('How is it configured?')
    expect(screen.getByRole('button', { name: 'Add 8 more questions' })).toBeInTheDocument()
  })

  it('warns when an answer could not be confirmed and when a question is from an older version', async () => {
    open({ [`GET ${base}/questions`]: { body: questions([question({ grounded: false, analysis_version: 1 })]) } })

    expect(await screen.findByText(/None of these points could be confirmed in the code/)).toBeInTheDocument()
    expect(screen.getByText('written for version 1')).toBeInTheDocument()
  })

  it('records progress and saves a draft answer', async () => {
    const user = userEvent.setup()
    const target = `${base}/questions/q1`
    const { fetchMock } = open({
      [`GET ${base}/questions`]: { body: questions([question()]) },
      [`PATCH ${target}`]: { body: question({ status: 'confident' }) },
    })

    await user.click(await screen.findByRole('radio', { name: 'Confident' }))
    expect(JSON.parse(String(posted(fetchMock, 'PATCH', target)[0][1]?.body))).toEqual({ status: 'confident' })

    await user.type(screen.getByRole('textbox', { name: 'Your answer' }), 'It is the app object.')
    await user.click(screen.getByRole('button', { name: 'Save answer' }))
    expect(JSON.parse(String(posted(fetchMock, 'PATCH', target)[1][1]?.body))).toEqual({
      user_answer: 'It is the app object.',
    })
  })

  it('shows progress and filters questions by it', async () => {
    const user = userEvent.setup()
    open({
      [`GET ${base}/questions`]: {
        body: questions([
          question(),
          question({ id: 'q2', question: 'How are requests routed?', status: 'confident' }),
        ]),
      },
    })

    expect(await screen.findByText('1 of 2 confident, 0 practicing')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Confident 1' }))

    expect(screen.getByRole('heading', { name: 'How are requests routed?' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'What is the central object of the framework?' })).not.toBeInTheDocument()
  })

  it('shows why the last request failed', async () => {
    open({
      [`GET ${base}/questions`]: {
        body: questions([], {
          id: 'b1',
          status: 'failed',
          requested_count: 8,
          question_count: 0,
          error_code: 'ai_unavailable',
          error_message: 'The AI service is busy.',
          created_at: '2026-11-03T10:00:00Z',
          completed_at: '2026-11-03T10:00:05Z',
        }),
      },
    })

    expect(await screen.findByRole('alert')).toHaveTextContent('The last request failed: The AI service is busy.')
  })

  it('deletes a question', async () => {
    const user = userEvent.setup()
    const { fetchMock } = open({
      [`GET ${base}/questions`]: { body: questions([question()]) },
      [`DELETE ${base}/questions/q1`]: { status: 204 },
    })

    await user.click(await screen.findByRole('button', { name: 'Delete question' }))

    await waitFor(() => expect(posted(fetchMock, 'DELETE', `${base}/questions/q1`)).toHaveLength(1))
  })
})
