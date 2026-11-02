import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { renderRoute } from '../test/renderRoute'

describe('LandingPage', () => {
  it('shows the tagline and a link into the app', () => {
    renderRoute('/')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Understand the code. Own the interview.')
    expect(screen.getByRole('link', { name: 'Analyze a repository' })).toHaveAttribute('href', '/dashboard')
  })

  it('lists the three steps in order', () => {
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
    renderRoute('/')

    const understood = screen.getByRole('button', { name: 'Understood' })
    expect(understood).toHaveAttribute('aria-pressed', 'false')

    await user.click(understood)

    expect(understood).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Not attempted' })).toHaveAttribute('aria-pressed', 'false')
  })
})
