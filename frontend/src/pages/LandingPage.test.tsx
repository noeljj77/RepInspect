import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ada, loggedOut, mockApi } from '../test/mockApi'
import { renderRoute } from '../test/renderRoute'

describe('LandingPage', () => {
  it('shows the tagline and invites guests to create an account', async () => {
    mockApi({ 'GET /api/auth/me': loggedOut })
    renderRoute('/')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Understand the code. Own the interview.')
    expect(screen.getByRole('link', { name: 'Create an account' })).toHaveAttribute('href', '/register')
    expect(await screen.findByRole('link', { name: 'Log in' })).toHaveAttribute('href', '/login')
  })

  it('offers the dashboard to people who are already logged in', async () => {
    mockApi({ 'GET /api/auth/me': { body: ada } })
    renderRoute('/')

    const links = await screen.findAllByRole('link', { name: 'Open dashboard' })
    expect(links.length).toBeGreaterThan(0)
    links.forEach((link) => expect(link).toHaveAttribute('href', '/dashboard'))
  })

  it('lists the three steps in order', () => {
    mockApi({ 'GET /api/auth/me': loggedOut })
    renderRoute('/')

    const steps = screen.getAllByRole('heading', { level: 3 }).slice(0, 3)
    expect(steps.map((step) => step.textContent)).toEqual([
      'Add a repository',
      'Ask about the implementation',
      'Rehearse the interview',
    ])
  })

  it('lets the example question status be changed', async () => {
    const user = userEvent.setup()
    mockApi({ 'GET /api/auth/me': loggedOut })
    renderRoute('/')

    const understood = screen.getByRole('button', { name: 'Understood' })
    expect(understood).toHaveAttribute('aria-pressed', 'false')

    await user.click(understood)

    expect(understood).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Not attempted' })).toHaveAttribute('aria-pressed', 'false')
  })
})
