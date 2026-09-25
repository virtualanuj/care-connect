import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'

import { ApiError } from './client'

const MAX_RETRIES = 2

export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status < 500) return false
  return failureCount < MAX_RETRIES
}

export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { retry: shouldRetry, refetchOnWindowFocus: false } },
      }),
  )
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}
