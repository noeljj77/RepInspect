/** Address of the file viewer, optionally scrolled to and highlighting a line. */
export function fileLink(repositoryId: string, path: string, line?: number | null): string {
  const params = new URLSearchParams({ path })
  if (line) params.set('line', String(line))
  return `/repositories/${repositoryId}/files?${params.toString()}`
}

/** "app/main.py:4" or "app/main.py:4–9". */
export function citationPlace({ path, start_line, end_line }: { path: string; start_line: number; end_line: number }): string {
  return `${path}:${end_line > start_line ? `${start_line}–${end_line}` : start_line}`
}
