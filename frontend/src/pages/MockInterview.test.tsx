import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import type { Grade, MockInterview, Turn } from '../api/mock'
import { REPO_ID, repositoryDetail } from '../test/fixtures'
import { ada, mockApi, type ApiRoutes } from '../test/mockApi'
import { renderRoute } from '../test/renderRoute'

const base = `/api/repositories/${REPO_ID}`
const ID = 'm1'
const pageUrl = `/repositories/${REPO_ID}/interview/mock/${ID}`
const CITE = { path: 'src/flask/app.py', start_line: 5, end_line: 5, quote: 'class Flask:' }

function grade(overrides: Partial<Grade> = {}): Grade {
  return {
    score: 3,
    label: 'Good',
    summary: 'You named the class but not how requests reach it.',
    strengths: ['Named the right class'],
    gaps: ['Did not explain routing'],
    claims: [
      { claim: 'The app is the Flask class.', verdict: 'supported', citations: [CITE] },
      { claim: 'It uses a database.', verdict: 'contradicted', citations: [CITE] },
      { claim: 'It caches templates.', verdict: 'not_found', citations: [] },
      { claim: 'It is fast.', verdict: 'unverified', citations: [] },
    ],
    missed_points: [{ statement: 'Routes are added with decorators.', citations: [CITE], verified: true, ungrounded_paths: [] }],
    follow_up: null,
    removed_citations: 0,
    ...overrides,
  }
}

function turn(overrides: Partial<Turn> = {}): Turn {
  return {
    id: 't1',
    position: 1,
    kind: 'question',
    prompt: 'What is the central object?',
    category: 'architecture',
    difficulty: 'basic',
    status: 'waiting',
    answer: null,
    score: null,
    grade: null,
    error_message: null,
    asked_at: new Date().toISOString(),
    answered_at: null,
    graded_at: null,
    ...overrides,
  }
}

function interview(turns: Turn[], overrides: Partial<MockInterview> = {}): MockInterview {
  return {
    id: ID,
    status: 'active',
    question_count: 3,
    asked: turns.filter((t) => t.kind === 'question').length,
    categories: null,
    difficulty: null,
    report: null,
    error_message: null,
    created_at: '2026-11-03T10:00:00Z',
    completed_at: null,
    turns,
    ...overrides,
  }
}

function open(url: string, routes: ApiRoutes = {}) {
  const fetchMock = mockApi({
    'GET /api/auth/me': { body: ada },
    [`GET ${base}`]: { body: repositoryDetail() },
    [`GET ${base}/questions`]: { body: { questions: [], latest_batch: null, progress: { new: 0, practicing: 0, confident: 0 } } },
    [`GET ${base}/mock-interviews`]: { body: [] },
    ...routes,
  })
  return { fetchMock, ...renderRoute(url) }
}

const sent = (fetchMock: ReturnType<typeof open>['fetchMock'], target: string) =>
  fetchMock.mock.calls.filter(([input, init]) => String(input) === target && init?.method === 'POST')

describe('Starting a mock interview', () => {
  it('starts one with the chosen length and level, and opens it', async () => {
    const user = userEvent.setup()
    const { fetchMock, router } = open(`/repositories/${REPO_ID}/interview`, {
      [`POST ${base}/mock-interviews`]: { status: 201, body: interview([turn()]) },
      [`GET ${base}/mock-interviews/${ID}`]: { body: interview([turn()]) },
    })

    await user.selectOptions(await screen.findByLabelText('Questions'), '3')
    await user.selectOptions(screen.getByLabelText('Level'), 'advanced')
    await user.click(screen.getByRole('button', { name: 'Start the interview' }))

    expect(JSON.parse(String(sent(fetchMock, `${base}/mock-interviews`)[0][1]?.body))).toEqual({
      question_count: 3,
      difficulty: 'advanced',
    })
    await waitFor(() => expect(router.state.location.pathname).toBe(pageUrl))
    expect(await screen.findByText('Question 1 of 3')).toBeInTheDocument()
  })

  it('offers to continue an interview that is still running, and lists earlier ones', async () => {
    open(`/repositories/${REPO_ID}/interview`, {
      [`GET ${base}/mock-interviews`]: {
        body: [
          { id: ID, status: 'active', question_count: 5, percent: null, created_at: '2026-11-03T10:00:00Z', completed_at: null },
          { id: 'm0', status: 'completed', question_count: 3, percent: 67, created_at: '2026-11-02T10:00:00Z', completed_at: '2026-11-02T10:20:00Z' },
        ],
      },
    })

    expect(await screen.findByRole('link', { name: 'Continue your interview' })).toHaveAttribute('href', pageUrl)
    expect(screen.getByRole('link', { name: /3 questions.*67%/ })).toBeInTheDocument()
  })
})

describe('Answering', () => {
  it('sends the answer and shows that it is being checked', async () => {
    const user = userEvent.setup()
    const { fetchMock } = open(pageUrl, {
      [`GET ${base}/mock-interviews/${ID}`]: { body: interview([turn()]) },
      [`POST ${base}/mock-interviews/${ID}/answer`]: {
        status: 202,
        body: interview([turn({ status: 'grading', answer: 'The Flask class.' })]),
      },
    })

    await user.type(await screen.findByRole('textbox', { name: 'Your answer' }), 'The Flask class.')
    await user.click(screen.getByRole('button', { name: 'Submit answer' }))

    expect(JSON.parse(String(sent(fetchMock, `${base}/mock-interviews/${ID}/answer`)[0][1]?.body))).toEqual({
      answer: 'The Flask class.',
    })
    expect(await screen.findByRole('status')).toHaveTextContent('Checking your answer against the code')
  })

  it('skips a question', async () => {
    const user = userEvent.setup()
    const { fetchMock } = open(pageUrl, {
      [`GET ${base}/mock-interviews/${ID}`]: { body: interview([turn()]) },
      [`POST ${base}/mock-interviews/${ID}/skip`]: {
        body: interview([turn({ status: 'skipped', score: 0 }), turn({ id: 't2', position: 2, prompt: 'Next one?' })]),
      },
    })

    await user.click(await screen.findByRole('button', { name: 'Skip this question' }))

    expect(sent(fetchMock, `${base}/mock-interviews/${ID}/skip`)).toHaveLength(1)
    expect(await screen.findByText('Skipped.')).toBeInTheDocument()
    expect(screen.getByText('Question 2 of 3')).toBeInTheDocument()
  })

  it('shows the grade, each statement checked against the code, and missed points', async () => {
    open(pageUrl, {
      [`GET ${base}/mock-interviews/${ID}`]: {
        body: interview([
          turn({ status: 'graded', answer: 'The Flask class.', score: 3, grade: grade({ follow_up: 'How are routes added?' }) }),
          turn({ id: 't2', position: 2, kind: 'follow_up', prompt: 'How are routes added?' }),
        ]),
      },
    })

    expect(await screen.findByLabelText('Score 3 of 4: Good')).toBeInTheDocument()
    expect(screen.getByText('You named the class but not how requests reach it.')).toBeInTheDocument()
    const claims = ['The code agrees', 'The code says otherwise', 'Not in the code that was searched', 'Could not be checked']
    for (const label of claims) expect(screen.getByText(label)).toBeInTheDocument()
    expect(screen.getByText('Routes are added with decorators.')).toBeInTheDocument()
    // The follow-up is asked next, and does not count as a new question.
    expect(screen.getByText('Follow-up')).toBeInTheDocument()
    expect(screen.queryByText('Question 2 of 3')).not.toBeInTheDocument()
  })

  it('lets grading be retried after a failure', async () => {
    const user = userEvent.setup()
    const { fetchMock } = open(pageUrl, {
      [`GET ${base}/mock-interviews/${ID}`]: {
        body: interview([turn({ status: 'failed', answer: 'x', error_message: 'The AI service is busy.' })]),
      },
      [`POST ${base}/mock-interviews/${ID}/turns/t1/retry`]: {
        status: 202,
        body: interview([turn({ status: 'grading', answer: 'x' })]),
      },
    })

    expect(await screen.findByRole('alert')).toHaveTextContent('The AI service is busy.')
    await user.click(screen.getByRole('button', { name: 'Grade it again' }))

    expect(sent(fetchMock, `${base}/mock-interviews/${ID}/turns/t1/retry`)).toHaveLength(1)
  })
})

describe('The report', () => {
  it('ends the interview and shows the score, topics, gaps and files to read', async () => {
    const user = userEvent.setup()
    const finished = interview(
      [turn({ status: 'graded', answer: 'x', score: 3, grade: grade() }), turn({ id: 't2', position: 2, status: 'cancelled' })],
      {
        status: 'completed',
        completed_at: '2026-11-03T10:20:00Z',
        report: {
          questions_answered: 1,
          skipped: 0,
          follow_ups_answered: 1,
          average_score: 3,
          percent: 75,
          follow_up_average: 4,
          by_category: [{ category: 'architecture', label: 'Architecture', average: 3, count: 1 }],
          strengths: ['Named the right class'],
          gaps: ['Did not explain routing'],
          contradicted_claims: [{ claim: 'It uses a database.', verdict: 'contradicted', citations: [CITE] }],
          files_to_review: ['src/flask/app.py'],
        },
      },
    )
    const { fetchMock } = open(pageUrl, {
      [`GET ${base}/mock-interviews/${ID}`]: { body: interview([turn({ status: 'graded', answer: 'x', score: 3, grade: grade() }), turn({ id: 't2', position: 2 })]) },
      [`POST ${base}/mock-interviews/${ID}/finish`]: { body: finished },
    })

    await user.click(await screen.findByRole('button', { name: 'End the interview' }))

    expect(sent(fetchMock, `${base}/mock-interviews/${ID}/finish`)).toHaveLength(1)
    const report = await screen.findByRole('region', { name: 'Interview report' })
    expect(report).toHaveTextContent('75%')
    expect(report).toHaveTextContent('1 question, 1 follow-up')
    expect(within(report).getByRole('list', { name: 'By topic' })).toHaveTextContent('Architecture3.0/4')
    expect(report).toHaveTextContent('Did not explain routing')
    expect(within(report).getByRole('link', { name: 'src/flask/app.py' })).toHaveAttribute(
      'href',
      `/repositories/${REPO_ID}/files?path=src%2Fflask%2Fapp.py`,
    )
    expect(screen.getByText('Not answered: the interview ended.')).toBeInTheDocument()
  })

  it('explains a preparation that failed', async () => {
    open(pageUrl, {
      [`GET ${base}/mock-interviews/${ID}`]: {
        body: interview([], { status: 'failed', error_message: 'The AI service is busy.' }),
      },
    })

    expect(await screen.findByRole('alert')).toHaveTextContent('The AI service is busy.')
  })
})
