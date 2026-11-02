import { formatBytes, formatCount, formatDate, formatRelativeTime } from './format'

describe('formatBytes', () => {
  it.each([
    [0, '0 B'],
    [999, '999 B'],
    [1024, '1.0 KB'],
    [1536, '1.5 KB'],
    [20480, '20 KB'],
    [5 * 1024 * 1024, '5.0 MB'],
    [3 * 1024 ** 3, '3.0 GB'],
    [5000 * 1024 ** 3, '5000 GB'],
  ])('%i bytes -> %s', (bytes, expected) => {
    expect(formatBytes(bytes)).toBe(expected)
  })
})

describe('formatCount', () => {
  it.each([
    [0, '0'],
    [999, '999'],
    [1200, '1.2K'],
    [68500, '68.5K'],
    [1_500_000, '1.5M'],
  ])('%i -> %s', (value, expected) => {
    expect(formatCount(value)).toBe(expected)
  })
})

describe('formatRelativeTime', () => {
  const now = new Date('2026-11-02T12:00:00Z')

  it.each([
    ['2026-11-02T11:59:50Z', 'just now'],
    ['2026-11-02T11:30:00Z', '30 minutes ago'],
    ['2026-11-02T09:00:00Z', '3 hours ago'],
    ['2026-11-01T12:00:00Z', 'yesterday'],
    ['2026-10-30T12:00:00Z', '3 days ago'],
    ['2026-08-02T12:00:00Z', '3 months ago'],
    ['2024-11-02T12:00:00Z', '2 years ago'],
  ])('%s -> %s', (iso, expected) => {
    expect(formatRelativeTime(iso, now)).toBe(expected)
  })
})

it('formatDate gives a short readable date', () => {
  expect(formatDate('2010-04-06T12:00:00Z')).toBe('Apr 6, 2010')
})
