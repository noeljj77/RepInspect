import { act, render, screen } from '@testing-library/react'

import { estimatedProgress } from '../../lib/progress'
import FullPageLoader from './FullPageLoader'
import LoadingLine from './LoadingLine'
import Skeleton from './Skeleton'
import WorkingNote from './WorkingNote'

describe('estimatedProgress', () => {
  it('starts at zero and rises', () => {
    expect(estimatedProgress(0, 30)).toBe(0)
    expect(estimatedProgress(10, 30)).toBeGreaterThan(estimatedProgress(5, 30))
  })

  it('is well along at the usual time but never claims to be finished', () => {
    expect(estimatedProgress(30, 30)).toBeGreaterThan(0.6)
    expect(estimatedProgress(30, 30)).toBeLessThan(0.92)
    expect(estimatedProgress(100000, 30)).toBeLessThanOrEqual(0.92)
  })
})

describe('LoadingLine', () => {
  it('announces the message as a status, with a decorative spinner', () => {
    render(<LoadingLine>Loading files…</LoadingLine>)

    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('Loading files…')
    expect(status.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
  })
})

describe('Skeleton', () => {
  it('is hidden from assistive technology', () => {
    const { container } = render(<Skeleton className="h-4" />)

    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true')
  })
})

describe('FullPageLoader', () => {
  it('shows its message as a status', () => {
    render(<FullPageLoader>Checking your session…</FullPageLoader>)

    expect(screen.getByRole('status')).toHaveTextContent('Checking your session…')
  })
})

describe('WorkingNote', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('shows the message, a clock and a bar that fills over time', () => {
    const { container } = render(<WorkingNote expected={10}>Writing the explanation…</WorkingNote>)
    const fill = () => container.querySelector<HTMLElement>('.bar-live')!

    expect(screen.getByText('Writing the explanation…')).toHaveAttribute('role', 'status')
    expect(screen.getByText('0s')).toBeInTheDocument()
    const before = parseFloat(fill().style.width)

    act(() => void vi.advanceTimersByTime(5000))

    expect(screen.getByText('5s')).toBeInTheDocument()
    expect(parseFloat(fill().style.width)).toBeGreaterThan(before)
  })

  it('says so when it is taking longer than usual, and keeps moving', () => {
    const { container } = render(<WorkingNote expected={10}>Writing the explanation…</WorkingNote>)

    expect(screen.queryByText(/longer than usual/)).not.toBeInTheDocument()
    act(() => void vi.advanceTimersByTime(16000))

    expect(screen.getByText(/Taking a little longer than usual/)).toBeInTheDocument()
    expect(container.querySelector('.bar-indeterminate')).toBeInTheDocument()
  })
})
