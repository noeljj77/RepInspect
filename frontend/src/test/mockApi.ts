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

/** Replace fetch with a fake that answers from a route table. Returns the mock for assertions. */
export function mockApi(routes: ApiRoutes) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    const handler = routes[key]
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
