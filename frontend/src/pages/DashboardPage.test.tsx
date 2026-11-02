import { screen } from '@testing-library/react'

import { renderRoute } from '../test/renderRoute'

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } }),
    ),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('DashboardPage', () => {
  it('shows a connected database when the API is healthy', async () => {
    mockFetch(200, { status: 'ok', version: '0.1.0', database: 'ok' })
    renderRoute('/dashboard')

    expect(await screen.findByText('Connected')).toBeInTheDocument()
    expect(screen.getByText('Running')).toBeInTheDocument()
    expect(screen.getByText('0.1.0')).toBeInTheDocument()
  })

  it('reports the database as unavailable when the API returns 503', async () => {
    mockFetch(503, { status: 'degraded', version: '0.1.0', database: 'unavailable' })
    renderRoute('/dashboard')

    expect(await screen.findByText('Unavailable')).toBeInTheDocument()
    expect(screen.getByText('Running')).toBeInTheDocument()
  })

  it('reports the API as unreachable when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    renderRoute('/dashboard')

    expect(await screen.findByText('Unreachable')).toBeInTheDocument()
  })

  it('marks Dashboard as the active navigation item', () => {
    mockFetch(200, { status: 'ok', version: '0.1.0', database: 'ok' })
    renderRoute('/dashboard')

    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page')
  })
})
