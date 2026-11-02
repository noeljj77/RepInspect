import { screen } from '@testing-library/react'

import { ada, mockApi } from '../test/mockApi'
import { renderRoute } from '../test/renderRoute'

const me = { body: ada }
const healthy = { body: { status: 'ok', version: '0.1.0', database: 'ok' } }

describe('DashboardPage', () => {
  it('greets the logged-in user', async () => {
    mockApi({ 'GET /api/auth/me': me, 'GET /api/health': healthy })
    renderRoute('/dashboard')

    expect(await screen.findByRole('heading', { name: 'Welcome, Ada' })).toBeInTheDocument()
  })

  it('shows a connected database when the API is healthy', async () => {
    mockApi({ 'GET /api/auth/me': me, 'GET /api/health': healthy })
    renderRoute('/dashboard')

    expect(await screen.findByText('Connected')).toBeInTheDocument()
    expect(screen.getByText('Running')).toBeInTheDocument()
    expect(screen.getByText('0.1.0')).toBeInTheDocument()
  })

  it('reports the database as unavailable when the API returns 503', async () => {
    mockApi({
      'GET /api/auth/me': me,
      'GET /api/health': { status: 503, body: { status: 'degraded', version: '0.1.0', database: 'unavailable' } },
    })
    renderRoute('/dashboard')

    expect(await screen.findByText('Unavailable')).toBeInTheDocument()
    expect(screen.getByText('Running')).toBeInTheDocument()
  })

  it('reports the API as unreachable when the request fails', async () => {
    mockApi({ 'GET /api/auth/me': me, 'GET /api/health': 'network-error' })
    renderRoute('/dashboard')

    expect(await screen.findByText('Unreachable')).toBeInTheDocument()
  })

  it('marks Dashboard as the active navigation item', async () => {
    mockApi({ 'GET /api/auth/me': me, 'GET /api/health': healthy })
    renderRoute('/dashboard')

    expect(await screen.findByRole('link', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page')
  })
})
