type Reply = { status?: number; body?: unknown }
/** A fixed reply, a function that computes one per call, or a failed network request. */
type Handler = Reply | (() => Reply) | 'network-error'

/** Routes are keyed "METHOD /path". Anything not listed fails the test loudly. */
export type ApiRoutes = Record<string, Handler>

export const ada = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'ada@example.com',
  display_name: 'Ada',
  created_at: '2026-11-02T00:00:00Z',
}

export const loggedOut = { status: 401, body: { detail: 'Not authenticated' } }

const AI_READ = /^GET \/api\/repositories\/[^/]+\/ai\/(overview|technologies|file|report)(?:\?path=(.*))?$/

/**
 * Most pages ask for AI explanations as soon as they open. Unless a test lists those
 * routes, answer that nothing has been requested yet, so older tests need not care.
 */
function aiNotRequested(key: string): Reply | undefined {
  const match = AI_READ.exec(key)
  if (!match) return undefined
  const [, kind, path] = match
  return {
    body: {
      id: null,
      kind,
      path: path ? decodeURIComponent(path) : null,
      status: 'missing',
      error_code: null,
      error_message: null,
      content: null,
      model: null,
      created_at: null,
      completed_at: null,
    },
  }
}

/** Pages also load collections and notes. Unless a test lists them, there are none. */
function emptyLibrary(key: string): Reply | undefined {
  if (key === 'GET /api/collections' || /^GET \/api\/repositories\/[^/]+\/notes$/.test(key)) return { body: [] }
  return undefined
}

/** Replace fetch with a fake that answers from a route table. Returns the mock for assertions. */
export function mockApi(routes: ApiRoutes) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    const handler = routes[key] ?? aiNotRequested(key) ?? emptyLibrary(key)
    if (!handler) throw new Error(`Unexpected request: ${key}`)
    if (handler === 'network-error') throw new TypeError('Failed to fetch')

    const { status = 200, body } = typeof handler === 'function' ? handler() : handler
    if (status === 204) return new Response(null, { status })
    return new Response(JSON.stringify(body), {
      status,
      headers: { 'content-type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
