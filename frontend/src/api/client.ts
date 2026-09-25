import type { ErrorBody, ErrorCode } from './types'

export const API_BASE = '/api/v1'

export class ApiError extends Error {
  code: ErrorCode
  status: number

  constructor(code: ErrorCode, message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
type QueryValue = string | number | boolean | undefined | null

export interface RequestOptions {
  body?: unknown
  query?: Record<string, QueryValue>
}

export interface ApiClientConfig {
  fetch?: typeof fetch
  getToken: () => string | null
  onUnauthorized?: () => void
}

function isErrorBody(value: unknown): value is ErrorBody {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as ErrorBody).code === 'string' &&
    typeof (value as ErrorBody).message === 'string'
  )
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null) params.set(key, String(value))
  }
  const qs = params.toString()
  return `${API_BASE}${path}${qs ? `?${qs}` : ''}`
}

async function readErrorBody(response: Response): Promise<ErrorBody> {
  try {
    const parsed: unknown = await response.json()
    if (isErrorBody(parsed)) return parsed
  } catch {
    // fall through to the generic error
  }
  return { code: 'INTERNAL_ERROR', message: 'Unexpected response from the server' }
}

export function createApiClient(config: ApiClientConfig) {
  const doFetch = config.fetch ?? ((...args: Parameters<typeof fetch>) => fetch(...args))

  async function request<T = unknown>(
    method: Method,
    path: string,
    options: RequestOptions = {},
  ): Promise<T> {
    const headers: Record<string, string> = {}
    const token = config.getToken()
    if (token) headers.Authorization = `Bearer ${token}`
    if (options.body !== undefined) headers['Content-Type'] = 'application/json'

    const response = await doFetch(buildUrl(path, options.query), {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })

    if (!response.ok) {
      if (response.status === 401) config.onUnauthorized?.()
      const error = await readErrorBody(response)
      throw new ApiError(error.code, error.message, response.status)
    }
    if (response.status === 204) return undefined as T
    return (await response.json()) as T
  }

  return { request }
}

export type ApiClient = ReturnType<typeof createApiClient>
