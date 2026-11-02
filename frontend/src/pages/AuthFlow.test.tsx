import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ada, loggedOut, mockApi } from '../test/mockApi'
import { renderRoute } from '../test/renderRoute'

const healthy = { body: { status: 'ok', version: '0.1.0', database: 'ok' } }

describe('route protection', () => {
  it('sends guests from the dashboard to the login page', async () => {
    mockApi({ 'GET /api/auth/me': loggedOut })
    const { router } = renderRoute('/dashboard')

    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
  })

  it('sends logged-in users away from the login and register pages', async () => {
    mockApi({ 'GET /api/auth/me': { body: ada }, 'GET /api/health': healthy })

    const { router } = renderRoute('/login')

    await waitFor(() => expect(router.state.location.pathname).toBe('/dashboard'))
  })
})

describe('login', () => {
  it('logs in and returns to the page the person was trying to reach', async () => {
    const user = userEvent.setup()
    let loggedIn = false
    const fetchMock = mockApi({
      'GET /api/auth/me': () => (loggedIn ? { body: ada } : loggedOut),
      'POST /api/auth/login': () => {
        loggedIn = true
        return { body: ada }
      },
      'GET /api/health': healthy,
    })
    const { router } = renderRoute('/dashboard')

    await user.type(await screen.findByLabelText('Email'), 'ada@example.com')
    await user.type(screen.getByLabelText('Password'), 'analytical-engine')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByRole('heading', { name: 'Welcome, Ada' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/dashboard')

    const loginCall = fetchMock.mock.calls.find(([url]) => url === '/api/auth/login')
    expect(JSON.parse(String(loginCall?.[1]?.body))).toEqual({
      email: 'ada@example.com',
      password: 'analytical-engine',
    })
  })

  it('shows the server message when the credentials are wrong', async () => {
    const user = userEvent.setup()
    mockApi({
      'GET /api/auth/me': loggedOut,
      'POST /api/auth/login': { status: 401, body: { detail: 'Incorrect email or password' } },
    })
    renderRoute('/login')

    await user.type(await screen.findByLabelText('Email'), 'ada@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password')
    expect(screen.getByRole('heading', { name: 'Log in' })).toBeInTheDocument()
  })
})

describe('register', () => {
  it('creates an account and opens the dashboard', async () => {
    const user = userEvent.setup()
    let loggedIn = false
    const fetchMock = mockApi({
      'GET /api/auth/me': () => (loggedIn ? { body: ada } : loggedOut),
      'POST /api/auth/register': () => {
        loggedIn = true
        return { status: 201, body: ada }
      },
      'GET /api/health': healthy,
    })
    renderRoute('/register')

    await user.type(await screen.findByLabelText('Name'), 'Ada')
    await user.type(screen.getByLabelText('Email'), 'ada@example.com')
    await user.type(screen.getByLabelText('Password'), 'analytical-engine')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('heading', { name: 'Welcome, Ada' })).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(([url]) => url === '/api/auth/register')
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      display_name: 'Ada',
      email: 'ada@example.com',
      password: 'analytical-engine',
    })
  })

  it('shows a readable message for a duplicate email', async () => {
    const user = userEvent.setup()
    mockApi({
      'GET /api/auth/me': loggedOut,
      'POST /api/auth/register': {
        status: 409,
        body: { detail: 'An account with this email already exists' },
      },
    })
    renderRoute('/register')

    await user.type(await screen.findByLabelText('Name'), 'Ada')
    await user.type(screen.getByLabelText('Email'), 'ada@example.com')
    await user.type(screen.getByLabelText('Password'), 'analytical-engine')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('An account with this email already exists')
  })
})

describe('logout', () => {
  it('logs out, returns to the home page and protects the dashboard again', async () => {
    const user = userEvent.setup()
    let loggedIn = true
    mockApi({
      'GET /api/auth/me': () => (loggedIn ? { body: ada } : loggedOut),
      'POST /api/auth/logout': () => {
        loggedIn = false
        return { status: 204 }
      },
      'GET /api/health': healthy,
    })
    const { router } = renderRoute('/dashboard')

    // The layout has a phone and a desktop button; CSS hides one, but tests run without CSS.
    const [logOutButton] = await screen.findAllByRole('button', { name: 'Log out' })
    await user.click(logOutButton)

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    expect(await screen.findByRole('link', { name: 'Log in' })).toBeInTheDocument()

    await router.navigate('/dashboard')
    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
  })
})
