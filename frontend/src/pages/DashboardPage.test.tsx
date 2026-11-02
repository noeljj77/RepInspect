import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ada, mockApi, type ApiRoutes } from '../test/mockApi'
import { analysisSummary, repositoryDetail, repositorySummary, REPO_ID } from '../test/fixtures'
import { renderRoute } from '../test/renderRoute'

const me = { body: ada }
const healthy = { body: { status: 'ok', version: '0.1.0', database: 'ok' } }

function dashboardApi(extra: ApiRoutes = {}): ApiRoutes {
  return {
    'GET /api/auth/me': me,
    'GET /api/health': healthy,
    'GET /api/repositories': { body: [] },
    ...extra,
  }
}

describe('DashboardPage', () => {
  it('greets the logged-in user', async () => {
    mockApi(dashboardApi())
    renderRoute('/dashboard')

    expect(await screen.findByRole('heading', { name: 'Welcome, Ada' })).toBeInTheDocument()
  })

  it('marks Dashboard as the active navigation item', async () => {
    mockApi(dashboardApi())
    renderRoute('/dashboard')

    expect(await screen.findByRole('link', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page')
  })

  describe('service status', () => {
    it('shows a connected database when the API is healthy', async () => {
      mockApi(dashboardApi())
      renderRoute('/dashboard')

      expect(await screen.findByText('Connected')).toBeInTheDocument()
      expect(screen.getByText('Running')).toBeInTheDocument()
      expect(screen.getByText('0.1.0')).toBeInTheDocument()
    })

    it('reports the database as unavailable when the API returns 503', async () => {
      mockApi(
        dashboardApi({
          'GET /api/health': {
            status: 503,
            body: { status: 'degraded', version: '0.1.0', database: 'unavailable' },
          },
        }),
      )
      renderRoute('/dashboard')

      expect(await screen.findByText('Unavailable')).toBeInTheDocument()
      expect(screen.getByText('Running')).toBeInTheDocument()
    })

    it('reports the API as unreachable when the request fails', async () => {
      mockApi(dashboardApi({ 'GET /api/health': 'network-error' }))
      renderRoute('/dashboard')

      expect(await screen.findByText('Unreachable')).toBeInTheDocument()
    })
  })

  describe('repository library', () => {
    it('invites people to add their first repository', async () => {
      mockApi(dashboardApi())
      renderRoute('/dashboard')

      expect(await screen.findByRole('heading', { name: 'No repositories yet' })).toBeInTheDocument()
    })

    it('lists saved repositories with their status', async () => {
      mockApi(
        dashboardApi({
          'GET /api/repositories': {
            body: [
              repositorySummary(),
              repositorySummary({
                id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
                owner: 'octo',
                name: 'broken',
                description: null,
                latest_analysis: analysisSummary({ status: 'failed' }),
              }),
            ],
          },
        }),
      )
      renderRoute('/dashboard')

      const flask = await screen.findByRole('link', { name: /pallets\/flask/ })
      expect(flask).toHaveAttribute('href', `/repositories/${REPO_ID}`)
      expect(flask).toHaveTextContent('The Python micro framework')
      expect(flask).toHaveTextContent('Ready')
      expect(screen.getByRole('link', { name: /octo\/broken/ })).toHaveTextContent('Failed')
    })

    it('tells people when the list cannot be loaded and lets them retry', async () => {
      const user = userEvent.setup()
      let attempts = 0
      mockApi(
        dashboardApi({
          'GET /api/repositories': () => (++attempts === 1 ? { status: 500, body: {} } : { body: [repositorySummary()] }),
        }),
      )
      renderRoute('/dashboard')

      expect(await screen.findByText('Your repositories could not be loaded.')).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Try again' }))

      expect(await screen.findByRole('link', { name: /pallets\/flask/ })).toBeInTheDocument()
    })
  })

  describe('adding a repository', () => {
    it('sends the URL and opens the repository page', async () => {
      const user = userEvent.setup()
      const fetchMock = mockApi(
        dashboardApi({
          'POST /api/repositories': { status: 202, body: repositoryDetail({ status: 'queued' }) },
          [`GET /api/repositories/${REPO_ID}`]: { body: repositoryDetail({ status: 'queued' }) },
        }),
      )
      const { router } = renderRoute('/dashboard')

      await user.type(await screen.findByLabelText('GitHub repository URL'), '  https://github.com/pallets/flask  ')
      await user.click(screen.getByRole('button', { name: 'Analyze' }))

      await waitFor(() => expect(router.state.location.pathname).toBe(`/repositories/${REPO_ID}`))
      const post = fetchMock.mock.calls.find(([url, init]) => url === '/api/repositories' && init?.method === 'POST')
      expect(JSON.parse(String(post?.[1]?.body))).toEqual({ url: 'https://github.com/pallets/flask' })
      expect(await screen.findByRole('heading', { name: 'Analyzing this repository' })).toBeInTheDocument()
    })

    it('shows the message from the server for an invalid URL and stays on the page', async () => {
      const user = userEvent.setup()
      mockApi(
        dashboardApi({
          'POST /api/repositories': {
            status: 422,
            body: { detail: 'Enter a public GitHub repository URL, such as https://github.com/owner/repo' },
          },
        }),
      )
      const { router } = renderRoute('/dashboard')

      await user.type(await screen.findByLabelText('GitHub repository URL'), 'https://example.com/x/y')
      await user.click(screen.getByRole('button', { name: 'Analyze' }))

      expect(await screen.findByRole('alert')).toHaveTextContent('Enter a public GitHub repository URL')
      expect(router.state.location.pathname).toBe('/dashboard')
    })

    it('shows the limit message when too many analyses are running', async () => {
      const user = userEvent.setup()
      mockApi(
        dashboardApi({
          'POST /api/repositories': {
            status: 429,
            body: { detail: 'You already have 3 analyses running. Wait for one to finish.' },
          },
        }),
      )
      renderRoute('/dashboard')

      await user.type(await screen.findByLabelText('GitHub repository URL'), 'https://github.com/a/b')
      await user.click(screen.getByRole('button', { name: 'Analyze' }))

      expect(await screen.findByRole('alert')).toHaveTextContent('3 analyses running')
    })
  })
})
