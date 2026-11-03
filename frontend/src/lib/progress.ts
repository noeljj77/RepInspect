/**
 * How far along a job of about `expected` seconds probably is, from 0 to 1. It eases towards
 * 92% and never reaches 100%, because the real end is only known when the server says so.
 */
export function estimatedProgress(elapsedSeconds: number, expected: number): number {
  return 0.92 * (1 - Math.exp(-elapsedSeconds / (expected * 0.6)))
}
