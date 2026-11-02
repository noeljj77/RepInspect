import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ada, mockApi, type ApiRoutes } from '../test/mockApi'
import { fileContent, fileEntry, REPO_ID, repositoryDetail } from '../test/fixtures'
import { renderRoute } from '../test/renderRoute'

const base = `/api/repositories/${REPO_ID}`
const APP = 'src/flask/app.py'
const contentKey = (path: string) => `GET ${base}/files/content?path=${encodeURIComponent(path)}`

const files = [
  fileEntry({ path: 'README.md', language: 'Markdown', importance_score: 50 }),
  fileEntry({ path: APP, importance_score: 45, symbol_count: 2 }),
  fileEntry({ path: 'src/flask/helpers.py' }),
  fileEntry({ path: 'tests/test_app.py' }),
  fileEntry({ path: '.env', language: null, line_count: null, skipped_reason: 'sensitive' }),
  fileEntry({ path: 'docs/logo.png', language: null, line_count: null, skipped_reason: 'binary' }),
]

function open(url: string, extra: ApiRoutes = {}) {
  const fetchMock = mockApi({
    'GET /api/auth/me': { body: ada },
    [`GET ${base}`]: { body: repositoryDetail() },
    [`GET ${base}/files`]: { body: files },
    [contentKey(APP)]: { body: fileContent() },
    ...extra,
  })
  return { fetchMock, ...renderRoute(url) }
}

const tree = () => screen.findByRole('navigation', { name: 'Files' })

describe('Files tab: the file tree', () => {
  it('lists top-level folders and files, folders first', async () => {
    open(`/repositories/${REPO_ID}/files`)

    const nav = await tree()
    const labels = within(nav).getAllByRole('listitem').map((li) => li.textContent)
    expect(labels).toEqual([
      'docs',
      'src',
      'tests',
      '.envNot imported: may contain secrets', // dotfiles sort first, as in most explorers
      'README.md, important file',
    ])
  })

  it('opens and closes folders', async () => {
    const user = userEvent.setup()
    open(`/repositories/${REPO_ID}/files`)
    const nav = await tree()

    expect(within(nav).queryByText('flask')).not.toBeInTheDocument()
    await user.click(within(nav).getByRole('button', { name: 'src' }))
    await user.click(within(nav).getByRole('button', { name: 'flask' }))
    expect(within(nav).getByRole('link', { name: /^app\.py/ })).toHaveAttribute(
      'href',
      `/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}`,
    )

    await user.click(within(nav).getByRole('button', { name: 'src' }))
    expect(within(nav).queryByRole('link', { name: /^app\.py/ })).not.toBeInTheDocument()
  })

  it('shows files that were not imported, but not as links', async () => {
    open(`/repositories/${REPO_ID}/files`)
    const nav = await tree()

    expect(within(nav).queryByRole('link', { name: /\.env/ })).not.toBeInTheDocument()
    expect(within(nav).getByText('Not imported: may contain secrets')).toBeInTheDocument()
  })

  it('flags important files', async () => {
    open(`/repositories/${REPO_ID}/files`)
    const nav = await tree()

    expect(within(nav).getByRole('link', { name: /^README\.md, important file$/ })).toBeInTheDocument()
  })

  it('searches by any part of the path', async () => {
    const user = userEvent.setup()
    open(`/repositories/${REPO_ID}/files`)
    await tree()

    await user.type(screen.getByRole('searchbox', { name: 'Search files' }), 'helpers')
    const nav = screen.getByRole('navigation', { name: 'Files' })
    expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual(['helpers.py'])

    await user.clear(screen.getByRole('searchbox', { name: 'Search files' }))
    await user.type(screen.getByRole('searchbox', { name: 'Search files' }), 'zzz')
    expect(within(nav).getByText(/No files match/)).toBeInTheDocument()
  })

  it('opens the folders that contain the selected file', async () => {
    open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}`)
    const nav = await tree()

    expect(within(nav).getByRole('link', { name: /^app\.py/ })).toHaveAttribute('aria-current', 'true')
  })

  it('keeps a folder collapsible even when it contains the selected file', async () => {
    const user = userEvent.setup()
    open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}`)
    const nav = await tree()

    await user.click(within(nav).getByRole('button', { name: 'flask' }))

    expect(within(nav).queryByRole('link', { name: /^app\.py/ })).not.toBeInTheDocument()
  })

  it('invites people to pick a file when none is selected', async () => {
    open(`/repositories/${REPO_ID}/files`)

    expect(await screen.findByRole('heading', { name: 'Pick a file' })).toBeInTheDocument()
  })
})

describe('Files tab: the file viewer', () => {
  it('shows the file, its details and the reasons it matters', async () => {
    open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}`)

    expect(await screen.findByRole('heading', { name: APP })).toBeInTheDocument()
    expect(screen.getByText('Python, 6 lines, 1.2 KB')).toBeInTheDocument()
    expect(screen.getByText('Application entry point')).toBeInTheDocument()
    const code = screen.getByRole('region', { name: 'Source code' })
    expect(code).toHaveTextContent('import os')
    expect(code).toHaveTextContent('class Flask:')
    expect(within(code).getAllByRole('button', { name: /Highlight line/ })).toHaveLength(6)
  })

  it('shows the outline with line numbers', async () => {
    open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}`)

    const details = await screen.findByRole('complementary', { name: 'File details' })
    const outline = within(details).getByText('Outline').closest('details')!
    expect(within(outline).getByRole('button', { name: /Flask\.run/ })).toHaveTextContent('method')
    expect(within(outline).getByRole('button', { name: /Flask\.run/ })).toHaveTextContent('6')
  })

  it('links imports to the files they point at, and marks libraries', async () => {
    open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}`)

    const details = await screen.findByRole('complementary', { name: 'File details' })
    expect(within(details).getByRole('link', { name: '.helpers' })).toHaveAttribute(
      'href',
      `/repositories/${REPO_ID}/files?path=${encodeURIComponent('src/flask/helpers.py')}`,
    )
    expect(within(details).queryByRole('link', { name: 'os' })).not.toBeInTheDocument()
    expect(within(details).getByText('os')).toBeInTheDocument()
  })

  it('lists the files that import this one', async () => {
    open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}`)

    const details = await screen.findByRole('complementary', { name: 'File details' })
    expect(within(details).getByRole('link', { name: 'tests/test_app.py' })).toBeInTheDocument()
    expect(within(details).getByRole('link', { name: 'src/flask/__init__.py' })).toBeInTheDocument()
  })

  it('highlights the line from the address', async () => {
    open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}&line=5`)

    const code = await screen.findByRole('region', { name: 'Source code' })
    const highlighted = code.querySelectorAll('[data-highlighted]')
    expect(highlighted).toHaveLength(1)
    expect(highlighted[0]).toHaveTextContent('class Flask:')
  })

  it('ignores a nonsense line number', async () => {
    open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}&line=abc`)

    const code = await screen.findByRole('region', { name: 'Source code' })
    expect(code.querySelectorAll('[data-highlighted]')).toHaveLength(0)
  })

  it('highlights a line when its number is clicked, and records it in the address', async () => {
    const user = userEvent.setup()
    const { router } = open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}`)

    await user.click(await screen.findByRole('button', { name: 'Highlight line 2' }))

    expect(router.state.location.search).toContain('line=2')
    expect(screen.getByRole('region', { name: 'Source code' }).querySelector('[data-highlighted]')).toHaveTextContent(
      'from .helpers import url_for',
    )
  })

  it('jumps to a symbol when it is clicked in the outline', async () => {
    const user = userEvent.setup()
    const { router } = open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}`)
    const details = await screen.findByRole('complementary', { name: 'File details' })

    await user.click(within(details).getByRole('button', { name: /Flask\.run/ }))

    await waitFor(() => expect(router.state.location.search).toContain('line=6'))
  })

  it('jumps to the import line when its number is clicked', async () => {
    const user = userEvent.setup()
    const { router } = open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}`)
    const details = await screen.findByRole('complementary', { name: 'File details' })

    await user.click(within(details).getByRole('button', { name: 'Go to line 2' }))

    await waitFor(() => expect(router.state.location.search).toContain('line=2'))
  })

  it('warns when the file could not be fully parsed', async () => {
    open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}`, {
      [contentKey(APP)]: { body: fileContent({ parse_error: true, symbols: [], imports: [] }) },
    })

    expect(await screen.findByText(/could not be parsed/)).toBeInTheDocument()
  })

  it('shows an empty state for panels with nothing in them', async () => {
    open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}`, {
      [contentKey(APP)]: { body: fileContent({ symbols: [], imports: [], imported_by: [] }) },
    })

    const details = await screen.findByRole('complementary', { name: 'File details' })
    expect(within(details).getAllByText('None.')).toHaveLength(3)
  })

  it('says so when the file cannot be opened', async () => {
    open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}`, {
      [contentKey(APP)]: { status: 404, body: { detail: 'File not found' } },
    })

    expect(await screen.findByRole('alert')).toHaveTextContent('could not be opened')
  })

  it('shows long files in a window, and the rest on request', async () => {
    const user = userEvent.setup()
    const long = Array.from({ length: 3500 }, (_, i) => `line ${i + 1}`).join('\n')
    open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}`, {
      [contentKey(APP)]: { body: fileContent({ content: long, line_count: 3500, symbols: [] }) },
    })
    const code = await screen.findByRole('region', { name: 'Source code' })

    expect(within(code).getAllByRole('button', { name: /Highlight line/ })).toHaveLength(3000)
    await user.click(within(code).getByRole('button', { name: 'Show the remaining 500 lines' }))

    expect(within(code).getAllByRole('button', { name: /Highlight line/ })).toHaveLength(3500)
  })

  it('shows lines past the window when one of them is linked to', async () => {
    const long = Array.from({ length: 3500 }, (_, i) => `line ${i + 1}`).join('\n')
    open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}&line=3400`, {
      [contentKey(APP)]: { body: fileContent({ content: long, line_count: 3500, symbols: [] }) },
    })
    const code = await screen.findByRole('region', { name: 'Source code' })

    expect(code.querySelector('[data-highlighted]')).toHaveTextContent('line 3400')
  })

  it('shows another file when the address changes', async () => {
    const user = userEvent.setup()
    open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent(APP)}`, {
      [contentKey('src/flask/helpers.py')]: {
        body: fileContent({ path: 'src/flask/helpers.py', content: 'def url_for(): ...\n', symbols: [], imports: [], imported_by: [APP] }),
      },
    })
    const details = await screen.findByRole('complementary', { name: 'File details' })

    await user.click(within(details).getByRole('link', { name: '.helpers' }))

    expect(await screen.findByRole('heading', { name: 'src/flask/helpers.py' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Source code' })).toHaveTextContent('def url_for')
  })
})
