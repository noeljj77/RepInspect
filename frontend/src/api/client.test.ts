import { ApiError, apiFetch, apiPost } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

describe('apiFetch', () => {
  it('returns parsed JSON and sends cookies', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiFetch('/api/thing')).resolves.toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledWith('/api/thing', expect.objectContaining({ credentials: 'include' }))
  })

  it('throws ApiError with the FastAPI detail message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(404, { detail: 'Repository not found' })))

    const error = await apiFetch('/api/thing').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 404, message: 'Repository not found' })
  })

  it('turns FastAPI validation errors into a readable message', async () => {
    const detail = [
      { loc: ['body', 'password'], msg: 'String should have at least 8 characters' },
      { loc: ['body', 'display_name'], msg: 'Field required' },
    ]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(422, { detail })))

    await expect(apiFetch('/api/thing')).rejects.toThrow(
      'Password: String should have at least 8 characters. Display name: Field required',
    )
  })

  it('returns undefined for 204 responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))

    await expect(apiFetch('/api/thing')).resolves.toBeUndefined()
  })

  it('apiPost sends JSON with the right header', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, {}))
    vi.stubGlobal('fetch', fetchMock)

    await apiPost('/api/thing', { a: 1 })

    const [, init] = fetchMock.mock.calls[0]
    expect(init).toMatchObject({ method: 'POST', body: '{"a":1}' })
    expect(init.headers).toMatchObject({ 'Content-Type': 'application/json' })
  })

  it('falls back to a generic message for non-JSON errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Bad gateway', { status: 502 })))

    await expect(apiFetch('/api/thing')).rejects.toThrow('Request failed with status 502')
  })
})
