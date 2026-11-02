/** Address of the file viewer, optionally scrolled to and highlighting a line. */
export function fileLink(repositoryId: string, path: string, line?: number | null): string {
  const params = new URLSearchParams({ path })
  if (line) params.set('line', String(line))
  return `/repositories/${repositoryId}/files?${params.toString()}`
}
