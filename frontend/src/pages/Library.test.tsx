import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import type { AnalysisSummary } from '../api/repositories'
import { analysis, analysisSummary, fileContent, REPO_ID, repositoryDetail, repositorySummary } from '../test/fixtures'
import { ada, mockApi, type ApiRoutes } from '../test/mockApi'
import { renderRoute } from '../test/renderRoute'

const base = `/api/repositories/${REPO_ID}`
const COLLECTION = { id: 'c1', name: 'Acme interview', description: null, created_at: '2026-11-02T10:00:00Z', repository_ids: [] }

function open(url: string, routes: ApiRoutes = {}) {
  const fetchMock = mockApi({ 'GET /api/auth/me': { body: ada }, 'GET /api/health': { body: { status: 'ok', database: 'ok', version: '0.1.0' } }, ...routes })
  return { fetchMock, ...renderRoute(url) }
}

const calls = (fetchMock: ReturnType<typeof open>['fetchMock'], method: string, url: string) =>
  fetchMock.mock.calls.filter(([input, init]) => String(input) === url && (init?.method ?? 'GET') === method)

const body = (fetchMock: ReturnType<typeof open>['fetchMock'], method: string, url: string) =>
  JSON.parse(String(calls(fetchMock, method, url)[0][1]?.body))

describe('Dashboard: library', () => {
  const library = [
    repositorySummary({ id: 'r1', name: 'flask', description: 'Web framework', labels: ['python', 'web'], collection_ids: ['c1'] }),
    repositorySummary({ id: 'r2', owner: null, name: 'todo-app', source_type: 'zip', description: null, labels: ['python'] }),
    repositorySummary({ id: 'r3', name: 'react', description: 'UI library', labels: [] }),
  ]
  const routes = {
    'GET /api/repositories': { body: library },
    'GET /api/collections': { body: [{ ...COLLECTION, repository_ids: ['r1'] }] },
  }
  const names = () =>
    within(screen.getByRole('region', { name: 'Your repositories' }))
      .getAllByRole('link')
      .map((link) => link.textContent)

  it('searches by name, description and label', async () => {
    const user = userEvent.setup()
    open('/dashboard', routes)

    await user.type(await screen.findByRole('searchbox', { name: 'Search your repositories' }), 'web')

    expect(names()).toEqual([expect.stringContaining('flask')])
  })

  it('filters by label and by collection, and can clear the filters', async () => {
    const user = userEvent.setup()
    const { router } = open('/dashboard', routes)

    await user.click(await screen.findByRole('button', { name: 'python', pressed: false }))
    expect(names()).toHaveLength(2)

    await user.click(within(screen.getByRole('region', { name: 'Collections' })).getByRole('link', { name: /Acme interview/ }))
    await waitFor(() => expect(router.state.location.search).toContain('collection=c1'))
    expect(names()).toEqual([expect.stringContaining('flask')])
    expect(screen.getByText('In Acme interview')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(names()).toHaveLength(3)
  })

  it('creates a collection', async () => {
    const user = userEvent.setup()
    const { fetchMock } = open('/dashboard', {
      ...routes,
      'POST /api/collections': { status: 201, body: { ...COLLECTION, id: 'c2', name: 'Python' } },
    })

    await user.click(await screen.findByRole('button', { name: 'New collection' }))
    await user.type(screen.getByRole('textbox', { name: 'New collection name' }), 'Python{Enter}')

    expect(body(fetchMock, 'POST', '/api/collections')).toEqual({ name: 'Python' })
  })

  it('uploads a ZIP as the raw request body and opens the new repository', async () => {
    const user = userEvent.setup()
    const uploaded = repositoryDetail({ status: 'queued' }, { source_type: 'zip', owner: null, name: 'shop' })
    const { fetchMock, router } = open('/dashboard', {
      ...routes,
      'POST /api/repositories/upload?name=shop.zip': { status: 202, body: uploaded },
      [`GET ${base}`]: { body: uploaded },
    })
    const file = new File(['PK\x03\x04 zip bytes'], 'shop.zip', { type: 'application/zip' })

    await user.upload(await screen.findByLabelText('Upload a ZIP'), file)

    await waitFor(() => expect(router.state.location.pathname).toBe(`/repositories/${REPO_ID}`))
    const [, init] = calls(fetchMock, 'POST', '/api/repositories/upload?name=shop.zip')[0]
    expect(init?.body).toBe(file)
    expect(init?.headers).toMatchObject({ 'Content-Type': 'application/zip' })
  })

  it('refuses files over the upload limit before sending them', async () => {
    const user = userEvent.setup()
    const { fetchMock } = open('/dashboard', routes)
    const file = new File(['x'], 'huge.zip', { type: 'application/zip' })
    Object.defineProperty(file, 'size', { value: 60 * 1024 * 1024 })

    await user.upload(await screen.findByLabelText('Upload a ZIP'), file)

    expect(await screen.findByRole('alert')).toHaveTextContent('larger than the 50 MB upload limit')
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/upload'))).toBe(false)
  })
})

describe('Repository page: labels, collections, refresh and delete', () => {
  it('adds and removes labels', async () => {
    const user = userEvent.setup()
    const { fetchMock } = open(`/repositories/${REPO_ID}`, {
      [`GET ${base}`]: { body: repositoryDetail({}, { labels: ['web'] }) },
      [`PATCH ${base}`]: { body: repositoryDetail({}, { labels: ['web', 'to review'] }) },
    })

    await user.click(await screen.findByRole('button', { name: 'Label' }))
    await user.type(screen.getByRole('textbox', { name: 'New label' }), 'to review{Enter}')
    expect(body(fetchMock, 'PATCH', base)).toEqual({ labels: ['web', 'to review'] })

    await user.click(await screen.findByRole('button', { name: 'Remove label web' }))
    expect(JSON.parse(String(calls(fetchMock, 'PATCH', base)[1][1]?.body))).toEqual({ labels: ['to review'] })
  })

  it('puts the repository in a collection', async () => {
    const user = userEvent.setup()
    const { fetchMock } = open(`/repositories/${REPO_ID}`, {
      [`GET ${base}`]: { body: repositoryDetail() },
      'GET /api/collections': { body: [COLLECTION] },
      [`PUT /api/collections/c1/repositories/${REPO_ID}`]: { status: 204 },
    })

    await user.click(await screen.findByText('Add to a collection'))
    await user.click(await screen.findByRole('checkbox', { name: 'Acme interview' }))

    expect(calls(fetchMock, 'PUT', `/api/collections/c1/repositories/${REPO_ID}`)).toHaveLength(1)
  })

  it('keeps showing the previous version while a refresh runs', async () => {
    const current = analysis({ version: 1 })
    const refreshing = analysis({ id: 'v2', version: 2, status: 'analyzing' })
    open(`/repositories/${REPO_ID}`, {
      [`GET ${base}`]: { body: { ...repositoryDetail(), latest_analysis: refreshing, current_analysis: current } },
      [`GET ${base}/files`]: { body: [] },
    })

    expect(await screen.findByRole('region', { name: 'Refresh' })).toHaveTextContent(
      'Version 2 is being analyzed. You are looking at version 1 until it is ready.',
    )
    expect(screen.getByRole('navigation', { name: 'Repository sections' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Refresh' })).toBeDisabled()
  })

  it('explains a failed refresh and offers to try again', async () => {
    const user = userEvent.setup()
    const failed = analysis({ id: 'v2', version: 2, status: 'failed', error_message: 'GitHub is not responding.' })
    const { fetchMock } = open(`/repositories/${REPO_ID}`, {
      [`GET ${base}`]: { body: { ...repositoryDetail(), latest_analysis: failed, current_analysis: analysis() } },
      [`POST ${base}/analyses`]: { status: 202, body: repositoryDetail() },
    })

    const banner = await screen.findByRole('alert')
    expect(banner).toHaveTextContent('The refresh failed. GitHub is not responding.')
    await user.click(within(banner).getByRole('button', { name: 'Try the refresh again' }))

    expect(calls(fetchMock, 'POST', `${base}/analyses`)).toHaveLength(1)
  })

  it('offers a new upload instead of a refresh for ZIP projects', async () => {
    open(`/repositories/${REPO_ID}`, {
      [`GET ${base}`]: { body: repositoryDetail({ github_metadata: null }, { source_type: 'zip', owner: null, source_url: null }) },
    })

    expect(await screen.findByText('Uploaded as a ZIP file')).toBeInTheDocument()
    expect(screen.getByLabelText('Upload new version')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Refresh' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /View on GitHub/ })).not.toBeInTheDocument()
  })

  it('deletes the repository only after confirming', async () => {
    const user = userEvent.setup()
    const { fetchMock, router } = open(`/repositories/${REPO_ID}`, {
      [`GET ${base}`]: { body: repositoryDetail() },
      [`DELETE ${base}`]: { status: 204 },
      'GET /api/repositories': { body: [] },
    })

    await user.click(await screen.findByLabelText('More'))
    await user.click(screen.getByRole('button', { name: 'Delete' }))
    expect(calls(fetchMock, 'DELETE', base)).toHaveLength(0)
    expect(screen.getByText(/Removes the repository, its versions, notes/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Delete everything' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/dashboard'))
    expect(calls(fetchMock, 'DELETE', base)).toHaveLength(1)
  })
})

describe('History tab', () => {
  const versions: AnalysisSummary[] = [
    analysisSummary({ id: 'v2', version: 2, commit_sha: 'bbbbbbb1234567' }),
    analysisSummary({ id: 'v1', version: 1, commit_sha: 'aaaaaaa1234567', source_removed: true }),
  ]

  it('lists versions and what changed in the one shown', async () => {
    open(`/repositories/${REPO_ID}/history`, {
      [`GET ${base}`]: { body: repositoryDetail({ id: 'v2', version: 2 }) },
      [`GET ${base}/analyses`]: { body: versions },
      [`GET ${base}/analyses/v2/changes`]: {
        body: {
          version: 2,
          previous_version: 1,
          previous_commit_sha: 'aaaaaaa',
          changes: {
            added: { count: 1, paths: ['src/new.py'] },
            removed: { count: 1, paths: ['src/old.py'] },
            modified: { count: 1, paths: ['src/app.py'] },
            unchanged: 9,
            exact: true,
            technologies_added: ['SQLite'],
            technologies_removed: [],
            dependencies_added: [],
            dependencies_removed: [],
            dependencies_changed: ['flask (pypi): ==2.0 → ==3.0'],
          },
        },
      },
    })

    expect(await screen.findByText('1 added, 1 changed, 1 removed, 9 unchanged.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'src/new.py' })).toHaveAttribute(
      'href',
      `/repositories/${REPO_ID}/files?path=src%2Fnew.py`,
    )
    expect(screen.queryByRole('link', { name: 'src/old.py' })).not.toBeInTheDocument() // removed: nothing to open
    expect(screen.getByText(/Technologies added/).parentElement).toHaveTextContent('SQLite')
    expect(screen.getByText(/flask \(pypi\): ==2\.0 → ==3\.0/)).toBeInTheDocument()

    const older = screen.getByRole('heading', { name: 'Version 1' }).closest('li') as HTMLElement
    expect(older).toHaveTextContent('Commit aaaaaaa')
    expect(older).toHaveTextContent('files no longer stored')
  })
})

describe('Notes', () => {
  const note = {
    id: 'n1',
    body: 'Ask why this returns a list.',
    path: 'src/flask/app.py',
    line: 5,
    created_at: '2026-11-02T10:00:00Z',
    updated_at: '2026-11-02T10:00:00Z',
  }

  it('lists notes with a link to their line and adds new ones', async () => {
    const user = userEvent.setup()
    const { fetchMock } = open(`/repositories/${REPO_ID}/notes`, {
      [`GET ${base}`]: { body: repositoryDetail() },
      [`GET ${base}/notes`]: { body: [note] },
      [`POST ${base}/notes`]: { status: 201, body: { ...note, id: 'n2', path: null, line: null } },
    })

    expect(await screen.findByText('Ask why this returns a list.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'src/flask/app.py:5' })).toHaveAttribute(
      'href',
      `/repositories/${REPO_ID}/files?path=src%2Fflask%2Fapp.py&line=5`,
    )

    await user.type(screen.getByRole('textbox', { name: 'New note' }), 'Prepare the caching story')
    await user.click(screen.getByRole('button', { name: 'Save note' }))

    expect(body(fetchMock, 'POST', `${base}/notes`)).toEqual({ body: 'Prepare the caching story' })
  })

  it('adds a note about the highlighted line from the file viewer', async () => {
    const user = userEvent.setup()
    const { fetchMock } = open(`/repositories/${REPO_ID}/files?path=${encodeURIComponent('src/flask/app.py')}&line=5`, {
      [`GET ${base}`]: { body: repositoryDetail() },
      [`GET ${base}/files`]: { body: [] },
      [`GET ${base}/files/content?path=${encodeURIComponent('src/flask/app.py')}`]: { body: fileContent() },
      [`GET ${base}/notes`]: { body: [note] },
      [`POST ${base}/notes`]: { status: 201, body: note },
    })

    const panel = await screen.findByRole('region', { name: 'Notes on this file' })
    expect(await within(panel).findByText('Ask why this returns a list.')).toBeInTheDocument()
    await user.type(within(panel).getByPlaceholderText('A note about line 5'), 'Entry point')
    await user.click(within(panel).getByRole('button', { name: 'Save note' }))

    expect(body(fetchMock, 'POST', `${base}/notes`)).toEqual({ body: 'Entry point', path: 'src/flask/app.py', line: 5 })
  })
})
