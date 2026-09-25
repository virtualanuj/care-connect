import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

import App from '../App'
import { AuthProvider } from '../auth/AuthProvider'
import { tokenStore } from '../auth/tokenStore'
import { ToastProvider } from '../components/Toast'

export interface MockResult {
  status?: number
  body?: unknown
}
export type Handler = (request: { body: unknown; url: URL }) => MockResult | Promise<MockResult>
export type Handlers = Record<string, Handler>

export interface Call {
  method: string
  path: string
  body: unknown
  headers: Record<string, string>
}

/** Route-based fetch mock. Keys look like `GET /api/v1/users`. Records every call. */
export function mockFetch(handlers: Handlers) {
  const calls: Call[] = []
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({
      method,
      path: url.pathname + url.search,
      body,
      headers: (init?.headers ?? {}) as Record<string, string>,
    })
    const handler = handlers[`${method} ${url.pathname}`]
    if (!handler) {
      return new Response(JSON.stringify({ code: 'NOT_FOUND', message: 'unmocked' }), {
        status: 404,
      })
    }
    const result = await handler({ body, url })
    const status = result.status ?? 200
    return new Response(status === 204 ? null : JSON.stringify(result.body ?? {}), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fn)
  return { calls, fn }
}

export const ADMIN = {
  id: 'u-admin',
  email: 'admin@clinic.test',
  name: 'Ada Admin',
  role: 'front_desk_admin',
  active: true,
}
export const DOCTOR = {
  id: 'u-doc',
  email: 'doc@clinic.test',
  name: 'Dan Doctor',
  role: 'doctor',
  active: true,
}

interface RenderOptions {
  path?: string
  token?: string | null
}

export function renderApp(handlers: Handlers, { path = '/', token = null }: RenderOptions = {}) {
  const mocked = mockFetch(handlers)
  if (token) tokenStore.set(token)
  else tokenStore.clear()
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const view = render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <AuthProvider>
            <App />
          </AuthProvider>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  )
  return { ...mocked, ...view }
}
