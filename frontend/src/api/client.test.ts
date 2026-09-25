import { describe, expect, it, vi } from 'vitest'

import { ApiError, createApiClient } from './client'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('api client', () => {
  it('sends the bearer token and a JSON body to the /api/v1 base path', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    const client = createApiClient({ fetch: fetchMock, getToken: () => 'tok-123' })

    await client.request('POST', '/appointments', { body: { doctorId: 'd1' } })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/appointments')
    expect(init.method).toBe('POST')
    expect(init.headers.Authorization).toBe('Bearer tok-123')
    expect(init.headers['Content-Type']).toBe('application/json')
    expect(init.body).toBe(JSON.stringify({ doctorId: 'd1' }))
  })

  it('omits Authorization when there is no token', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: 'ok' }))
    const client = createApiClient({ fetch: fetchMock, getToken: () => null })

    await client.request('GET', '/health')

    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined()
  })

  it('appends query parameters and skips undefined values', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]))
    const client = createApiClient({ fetch: fetchMock, getToken: () => null })

    await client.request('GET', '/slots', { query: { date: '2026-03-01', doctorId: undefined } })

    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/slots?date=2026-03-01')
  })

  it('returns the parsed body on success and undefined on 204', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: 'ok' }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    const client = createApiClient({ fetch: fetchMock, getToken: () => null })

    expect(await client.request('GET', '/health')).toEqual({ status: 'ok' })
    expect(await client.request('DELETE', '/x')).toBeUndefined()
  })

  it('maps an Error body to ApiError with code, message and status', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ code: 'SLOT_ALREADY_BOOKED', message: 'Taken' }, 409))
    const client = createApiClient({ fetch: fetchMock, getToken: () => null })

    const error = await client.request('POST', '/appointments').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ code: 'SLOT_ALREADY_BOOKED', message: 'Taken', status: 409 })
  })

  it('maps a non-JSON error response to a generic INTERNAL_ERROR ApiError', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response('<html>bad gateway</html>', { status: 502 }))
    const client = createApiClient({ fetch: fetchMock, getToken: () => null })

    const error = await client.request('GET', '/health').catch((e: unknown) => e)

    expect(error).toMatchObject({ code: 'INTERNAL_ERROR', status: 502 })
  })

  it('calls onUnauthorized when the API answers 401', async () => {
    const onUnauthorized = vi.fn()
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ code: 'UNAUTHENTICATED', message: 'no' }, 401))
    const client = createApiClient({ fetch: fetchMock, getToken: () => 't', onUnauthorized })

    await client.request('GET', '/auth/me').catch(() => undefined)

    expect(onUnauthorized).toHaveBeenCalledOnce()
  })
})
