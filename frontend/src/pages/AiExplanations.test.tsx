import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import {
  explanation,
  fileContent,
  fileEntry,
  fileExplanationContent,
  overviewContent,
  REPO_ID,
  repositoryDetail,
  technologiesContent,
} from '../test/fixtures'
import { ada, mockApi, type ApiRoutes } from '../test/mockApi'
import { renderRoute } from '../test/renderRoute'

const base = `/api/repositories/${REPO_ID}`
const APP = 'src/flask/app.py'
const fileAi = (method: string) => `${method} ${base}/ai/file?path=${encodeURIComponent(APP)}`

function open(url: string, extra: ApiRoutes = {}) {
  const fetchMock = mockApi({
    'GET /api/auth/me': { body: ada },
    [`GET ${base}`]: { body: repositoryDetail() },
    [`GET ${base}/files`]: { body: [fileEntry({ path: APP })] },
    [`GET ${base}/files/content?path=${encodeURIComponent(APP)}`]: { body: fileContent() },
    ...extra,
  })
  return { fetchMock, ...renderRoute(url) }
}

const overviewRegion = () => screen.findByRole('region', { name: 'How this project works' })

describe('AI overview', () => {
  it('offers to write an overview, waits for it, then shows it', async () => {
    const user = userEvent.setup()
    let requested = false
    const { fetchMock } = open(`/repositories/${REPO_ID}`, {
      [`GET ${base}/ai/overview`]: () => ({
        body: requested ? explanation('overview', overviewContent()) : explanation('overview', null, { status: 'missing' }),
      }),
      [`POST ${base}/ai/overview`]: () => {
        requested = true
        return { status: 202, body: explanation('overview', null) }
      },
    })

    const region = await overviewRegion()
    await user.click(await within(region).findByRole('button', { name: 'Write the overview' }))

    expect(await within(region).findByRole('status')).toHaveTextContent('usually takes 10 to 30 seconds')
    expect(fetchMock).toHaveBeenCalledWith(`${base}/ai/overview`, expect.objectContaining({ method: 'POST' }))
    expect(
      await within(region).findByText('Flask is a small framework for web applications.', {}, { timeout: 4000 }),
    ).toBeInTheDocument()
  })

  it('links claims backed by code to the quoted lines and marks the rest as inference', async () => {
    open(`/repositories/${REPO_ID}`, {
      [`GET ${base}/ai/overview`]: { body: explanation('overview', overviewContent()) },
    })

    const region = await overviewRegion()
    const purpose = await within(region).findByRole('region', { name: 'What the project does' })

    const citation = within(purpose).getByRole('link', { name: /src\/flask\/app\.py:5/ })
    expect(citation).toHaveAttribute('href', `/repositories/${REPO_ID}/files?path=src%2Fflask%2Fapp.py&line=5`)
    expect(citation).toHaveTextContent('class Flask:')
    expect(within(purpose).getByText('Backed by code:', { exact: false })).toBeInTheDocument()

    const guess = within(purpose).getByText('It is probably used for small services.').closest('li')
    expect(guess).toHaveTextContent('Inference, not confirmed in the code')
    expect(guess).toHaveTextContent('not in this repository: server/main.py')
  })

  it('says when a part could not be determined and how the result was checked', async () => {
    open(`/repositories/${REPO_ID}`, {
      [`GET ${base}/ai/overview`]: { body: explanation('overview', overviewContent()) },
    })

    const region = await overviewRegion()
    const frontend = await within(region).findByRole('region', { name: 'Frontend structure' })
    expect(frontend).toHaveTextContent('Could not be determined from the analyzed files.')
    expect(region).toHaveTextContent('1 reference that could not be confirmed was removed')
    expect(region).toHaveTextContent('Written by gemini-test')
    expect(within(region).getByRole('button', { name: 'Regenerate' })).toBeInTheDocument()
  })

  it("shows the server's reason when AI is not available", async () => {
    const user = userEvent.setup()
    open(`/repositories/${REPO_ID}`, {
      [`POST ${base}/ai/overview`]: {
        status: 503,
        body: { detail: 'AI explanations are not set up on this server.' },
      },
    })

    const region = await overviewRegion()
    await user.click(await within(region).findByRole('button', { name: 'Write the overview' }))

    expect(await within(region).findByRole('alert')).toHaveTextContent('not set up on this server')
  })

  it('shows a failed attempt and lets the person try again', async () => {
    open(`/repositories/${REPO_ID}`, {
      [`GET ${base}/ai/overview`]: {
        body: explanation('overview', null, {
          status: 'failed',
          error_code: 'quota',
          error_message: 'The AI service is out of quota for today.',
        }),
      },
    })

    const region = await overviewRegion()
    expect(await within(region).findByRole('alert')).toHaveTextContent('out of quota')
    expect(within(region).getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})

describe('AI technology explanations', () => {
  it('keeps general knowledge apart from the evidence found in the code', async () => {
    const user = userEvent.setup()
    open(`/repositories/${REPO_ID}`, {
      [`GET ${base}/ai/technologies`]: { body: explanation('technologies', technologiesContent()) },
    })

    const card = await screen.findByRole('region', { name: 'Frameworks and libraries' })
    expect(await within(card).findByText(/Open a technology above/)).toBeInTheDocument()
    await user.click(within(card).getByText('Flask'))

    const entry = within(card).getByText('Flask').closest('details') as HTMLElement
    expect(entry).toHaveTextContent('Found in this repository')
    expect(entry).toHaveTextContent('General knowledge, not taken from this repository')
    expect(entry).toHaveTextContent('A lightweight Python web framework.')
    expect(within(entry).getByText('Django')).toBeInTheDocument()
    expect(entry).toHaveTextContent('not documented in the repository')

    // pytest has no explanation, so it shows only its evidence.
    const pytest = within(card).getByText('pytest').closest('details') as HTMLElement
    expect(pytest).not.toHaveTextContent('General knowledge')
  })

  it('offers to explain the technologies when none have been explained', async () => {
    open(`/repositories/${REPO_ID}`)

    const card = await screen.findByRole('region', { name: 'Frameworks and libraries' })
    expect(await within(card).findByRole('button', { name: 'Explain these technologies' })).toBeInTheDocument()
  })
})

describe('AI file explanation', () => {
  it('explains the open file and jumps to its key parts', async () => {
    const user = userEvent.setup()
    let requested = false
    const { fetchMock, router } = open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}`, {
      [fileAi('GET')]: () => ({
        body: requested
          ? explanation('file', fileExplanationContent(), { path: APP })
          : explanation('file', null, { path: APP, status: 'missing' }),
      }),
      [fileAi('POST')]: () => {
        requested = true
        return { status: 202, body: explanation('file', fileExplanationContent(), { path: APP }) }
      },
    })

    const panel = await screen.findByRole('region', { name: 'Explanation of this file' })
    await user.click(await within(panel).findByRole('button', { name: 'Explain this file' }))

    expect(await within(panel).findByText('Defines the central application class.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      `${base}/ai/file?path=${encodeURIComponent(APP)}`,
      expect.objectContaining({ method: 'POST' }),
    )
    expect(panel).toHaveTextContent('Takes configuration, serves requests.')

    await user.click(within(panel).getByRole('button', { name: 'Flask' }))
    await waitFor(() => expect(router.state.location.search).toContain('line=5'))
  })
})
