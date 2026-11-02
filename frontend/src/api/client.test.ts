import { ApiError, apiFetch } from './client'

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

  it('falls back to a generic message for non-JSON errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Bad gateway', { status: 502 })))

    await expect(apiFetch('/api/thing')).rejects.toThrow('Request failed with status 502')
  })
})
