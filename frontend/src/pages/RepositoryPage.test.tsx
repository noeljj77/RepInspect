import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { mockApi, ada } from '../test/mockApi'
import { analysis, REPO_ID, repositoryDetail } from '../test/fixtures'
import { renderRoute } from '../test/renderRoute'

const path = `/repositories/${REPO_ID}`
const key = `GET /api/repositories/${REPO_ID}`
const me = { body: ada }

function open(detail: ReturnType<typeof repositoryDetail>, extra = {}) {
  const fetchMock = mockApi({ 'GET /api/auth/me': me, [key]: { body: detail }, ...extra })
  renderRoute(path)
  return fetchMock
}

describe('RepositoryPage', () => {
  describe('while the analysis runs', () => {
    it.each([
      ['queued', 'Waiting to start'],
      ['fetching', 'Downloading from GitHub'],
      ['extracting', 'Reading files'],
    ] as const)('shows %s as the current step', async (status, label) => {
      open(repositoryDetail({ status, github_metadata: null, languages: null, readme_text: null }))

      const progress = await screen.findByRole('region', { name: 'Analysis progress' })
      const current = within(progress).getByText(label, { exact: false }).closest('li')
      expect(current).toHaveAttribute('aria-current', 'step')
    })

    it('marks earlier steps as done', async () => {
      open(repositoryDetail({ status: 'extracting' }))

      const done = await screen.findByText('Downloading from GitHub')
      expect(done.closest('li')).not.toHaveAttribute('aria-current')
      expect(within(done.closest('li')!).getByText('(done)')).toBeInTheDocument()
    })

    it('keeps polling until the analysis finishes', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true })
      try {
        let calls = 0
        mockApi({
          'GET /api/auth/me': me,
          [key]: () => ({ body: repositoryDetail({ status: ++calls < 2 ? 'fetching' : 'completed' }) }),
        })
        renderRoute(path)

        expect(await screen.findByRole('heading', { name: 'Analyzing this repository' })).toBeInTheDocument()
        await vi.advanceTimersByTimeAsync(2000)

        expect(await screen.findByRole('heading', { name: 'What was imported' })).toBeInTheDocument()
        expect(screen.queryByRole('heading', { name: 'Analyzing this repository' })).not.toBeInTheDocument()
      } finally {
        vi.useRealTimers()
      }
    })
  })

  describe('when the analysis is complete', () => {
    it('shows the repository details', async () => {
      open(repositoryDetail())

      expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('pallets/flask')
      expect(screen.getByText('The Python micro framework for building web applications.')).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /View on GitHub/ })).toHaveAttribute(
        'href',
        'https://github.com/pallets/flask',
      )
      const facts = screen.getByRole('region', { name: 'Repository facts' })
      expect(within(facts).getByText('68.5K')).toBeInTheDocument()
      expect(within(facts).getByText('16.2K')).toBeInTheDocument()
      expect(within(facts).getByText('BSD-3-Clause')).toBeInTheDocument()
      expect(within(facts).getByText('1234567')).toBeInTheDocument()
      expect(within(facts).getByText('main')).toBeInTheDocument()
    })

    it('shows the languages found in the imported files, by lines of code', async () => {
      open(
        repositoryDetail({
          code_stats: {
            ...analysis().code_stats!,
            languages: [
              { name: 'Python', files: 9, lines: 900, bytes: 1, is_programming: true },
              { name: 'TypeScript', files: 1, lines: 100, bytes: 1, is_programming: true },
              { name: 'Markdown', files: 4, lines: 5000, bytes: 1, is_programming: false },
            ],
          },
        }),
      )

      const bar = await screen.findByRole('img', { name: /Languages: Python 90\.0%, TypeScript 10\.0%/ })
      expect(bar).toBeInTheDocument() // documentation and data files do not count as code
      expect(screen.getByRole('heading', { name: 'Languages, by lines of code' })).toBeInTheDocument()
    })

    it("falls back to GitHub's language breakdown without code analysis", async () => {
      open(repositoryDetail({ code_stats: null, technologies: null, languages: { Python: 900, HTML: 100 } }))

      expect(await screen.findByRole('img', { name: /Languages: Python 90\.0%, HTML 10\.0%/ })).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: 'Languages' })).toBeInTheDocument()
      expect(screen.getByText(/Code analysis was not available for this import/)).toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: 'Frameworks and libraries' })).not.toBeInTheDocument()
    })

    it('groups very small languages into Other', async () => {
      const many = Object.fromEntries(Array.from({ length: 9 }, (_, i) => [`Lang${i}`, 100 - i]))
      open(repositoryDetail({ code_stats: null, languages: many }))

      expect(await screen.findByText('Other')).toBeInTheDocument()
    })

    it('summarises what was imported and what was left out', async () => {
      const user = userEvent.setup()
      open(
        repositoryDetail({
          file_count: 1,
          total_bytes: 1536,
          skipped_summary: { sensitive: 2, binary: 5, ignored_directory: 40 },
        }),
      )

      const section = await screen.findByRole('region', { name: 'What was imported' })
      expect(within(section).getByText('1')).toBeInTheDocument()
      expect(section).toHaveTextContent('file · 1.5 KB')

      await user.click(within(section).getByText('47 files left out'))
      expect(within(section).getByText('Sensitive files, such as .env and private keys')).toBeInTheDocument()
      expect(within(section).getByText('Files in dependency and build folders')).toBeInTheDocument()
    })

    it('tells people that secret-looking values were hidden', async () => {
      open(repositoryDetail({ redaction_count: 3 }))

      expect(await screen.findByText(/3 values that looked like a password or key were hidden/)).toBeInTheDocument()
    })

    it('warns when only part of a large repository was imported', async () => {
      open(repositoryDetail({ truncated: true }))

      expect(await screen.findByText(/only the first files were imported/)).toBeInTheDocument()
    })

    it('shows the README, or says there is none', async () => {
      open(repositoryDetail())
      expect(await screen.findByText(/A small web framework\./)).toBeInTheDocument()
    })

    it('handles a repository without a README', async () => {
      open(repositoryDetail({ readme_text: null, readme_path: null }))

      expect(await screen.findByText('This repository has no README file.')).toBeInTheDocument()
    })
  })

  describe('when the analysis failed', () => {
    it('explains what went wrong and offers a retry that starts a new analysis', async () => {
      const user = userEvent.setup()
      let retried = false
      const fetchMock = mockApi({
        'GET /api/auth/me': me,
        [key]: () => ({
          body: retried
            ? repositoryDetail({ status: 'fetching', version: 2 })
            : repositoryDetail({
                status: 'failed',
                error_code: 'rate_limited',
                error_message: "GitHub's rate limit was reached. Try again after 14:05 UTC.",
              }),
        }),
        [`POST /api/repositories/${REPO_ID}/analyses`]: () => {
          retried = true
          return { status: 202, body: repositoryDetail({ status: 'queued', version: 2 }) }
        },
      })
      renderRoute(path)

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent('This repository could not be analyzed')
      expect(alert).toHaveTextContent("GitHub's rate limit was reached. Try again after 14:05 UTC.")

      await user.click(screen.getByRole('button', { name: 'Try again' }))

      expect(await screen.findByRole('heading', { name: 'Analyzing this repository' })).toBeInTheDocument()
      expect(fetchMock).toHaveBeenCalledWith(`/api/repositories/${REPO_ID}/analyses`, expect.objectContaining({ method: 'POST' }))
    })

    it('shows why a retry was refused', async () => {
      const user = userEvent.setup()
      open(repositoryDetail({ status: 'failed', error_message: 'Repository not found.' }), {
        [`POST /api/repositories/${REPO_ID}/analyses`]: {
          status: 429,
          body: { detail: 'You already have 3 analyses running. Wait for one to finish.' },
        },
      })

      await user.click(await screen.findByRole('button', { name: 'Try again' }))

      expect(await screen.findByText(/3 analyses running/)).toBeInTheDocument()
    })
  })

  describe('error states', () => {
    it("says so when the repository doesn't exist or belongs to someone else", async () => {
      mockApi({ 'GET /api/auth/me': me, [key]: { status: 404, body: { detail: 'Repository not found' } } })
      renderRoute(path)

      expect(await screen.findByRole('heading', { name: 'Repository not found' })).toBeInTheDocument()
      // The sidebar and the page both link back to the dashboard.
      screen.getAllByRole('link', { name: 'Dashboard' }).forEach((link) => expect(link).toHaveAttribute('href', '/dashboard'))
    })

    it('treats a malformed id the same way', async () => {
      mockApi({
        'GET /api/auth/me': me,
        'GET /api/repositories/not-a-uuid': { status: 422, body: { detail: [{ loc: ['path'], msg: 'bad' }] } },
      })
      renderRoute('/repositories/not-a-uuid')

      expect(await screen.findByRole('heading', { name: 'Repository not found' })).toBeInTheDocument()
    })

    it('reports other failures without pretending the repository is missing', async () => {
      mockApi({ 'GET /api/auth/me': me, [key]: 'network-error' })
      renderRoute(path)

      expect(await screen.findByRole('heading', { name: 'Something went wrong' })).toBeInTheDocument()
    })

    it('requires login', async () => {
      mockApi({ 'GET /api/auth/me': { status: 401, body: { detail: 'Not authenticated' } } })
      const { router } = renderRoute(path)

      expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
      expect(router.state.location.pathname).toBe('/login')
    })
  })
})
