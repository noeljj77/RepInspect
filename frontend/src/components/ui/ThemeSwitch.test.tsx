import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { setTheme } from '../../hooks/useTheme'
import ThemeSwitch from './ThemeSwitch'

afterEach(() => {
  act(() => setTheme('dark'))
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

describe('ThemeSwitch', () => {
  it('starts in the dark theme', () => {
    render(<ThemeSwitch />)

    expect(screen.getByRole('switch', { name: 'Light theme' })).toHaveAttribute('aria-checked', 'false')
    expect(document.documentElement.dataset.theme).not.toBe('light')
  })

  it('switches to the light theme and remembers the choice', async () => {
    const user = userEvent.setup()
    render(<ThemeSwitch />)

    await user.click(screen.getByRole('switch', { name: 'Light theme' }))

    expect(screen.getByRole('switch', { name: 'Light theme' })).toHaveAttribute('aria-checked', 'true')
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem('repinspect-theme')).toBe('light')
  })

  it('switches back to dark', async () => {
    const user = userEvent.setup()
    render(<ThemeSwitch />)

    await user.click(screen.getByRole('switch', { name: 'Light theme' }))
    await user.click(screen.getByRole('switch', { name: 'Light theme' }))

    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('repinspect-theme')).toBe('dark')
  })

  it('keeps every switch on the page in step', async () => {
    const user = userEvent.setup()
    render(
      <>
        <ThemeSwitch />
        <ThemeSwitch label={false} />
      </>,
    )

    await user.click(screen.getAllByRole('switch')[0])

    screen.getAllByRole('switch').forEach((toggle) => expect(toggle).toHaveAttribute('aria-checked', 'true'))
  })
})
