export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, message: string, body: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

interface ValidationIssue {
  loc?: unknown[]
  msg?: string
}

function describeValidationIssues(issues: ValidationIssue[]): string {
  return issues
    .map(({ loc, msg }) => {
      const field = String(loc?.at(-1) ?? '').replaceAll('_', ' ')
      const label = field ? field.charAt(0).toUpperCase() + field.slice(1) : 'Request'
      return `${label}: ${msg ?? 'is invalid'}`
    })
    .join('. ')
}

/** Turn FastAPI's `detail` (a string, or a list for 422 validation errors) into one message. */
function errorMessage(body: unknown, status: number): string {
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const { detail } = body as { detail: unknown }
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return describeValidationIssues(detail as ValidationIssue[])
  }
  return `Request failed with status ${status}`
}

/**
 * Thin wrapper around fetch for calls to our own backend.
 * Paths are relative ("/api/...") so the Vite proxy (dev) or the
 * reverse proxy (production) routes them to FastAPI.
 */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: { Accept: 'application/json', ...init.headers },
  })

  const isJson = response.headers.get('content-type')?.includes('application/json')
  const body: unknown = isJson ? await response.json() : await response.text()

  if (!response.ok) {
    throw new ApiError(response.status, errorMessage(body, response.status), body)
  }

  // 204 No Content has an empty body; callers type those as void.
  return (response.status === 204 ? undefined : body) as T
}

export function apiPost<T>(path: string, data?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: 'POST',
    headers: data === undefined ? {} : { 'Content-Type': 'application/json' },
    body: data === undefined ? undefined : JSON.stringify(data),
  })
}
