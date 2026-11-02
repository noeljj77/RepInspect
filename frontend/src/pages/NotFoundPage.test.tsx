import { screen } from '@testing-library/react'

import { renderRoute } from '../test/renderRoute'

it('shows a not-found page for unknown routes', () => {
  renderRoute('/no/such/page')

  expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Go to home page' })).toHaveAttribute('href', '/')
})
