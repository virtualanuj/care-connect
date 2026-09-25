import { useQueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ApiError } from './client'
import { AppProviders } from './providers'
import { shouldRetry } from './retry'

describe('shouldRetry', () => {
  it('never retries client errors (4xx)', () => {
    expect(shouldRetry(0, new ApiError('FORBIDDEN', 'no', 403))).toBe(false)
    expect(shouldRetry(0, new ApiError('SLOT_ALREADY_BOOKED', 'x', 409))).toBe(false)
  })

  it('retries server and network errors up to twice', () => {
    expect(shouldRetry(0, new ApiError('INTERNAL_ERROR', 'x', 500))).toBe(true)
    expect(shouldRetry(1, new TypeError('network'))).toBe(true)
    expect(shouldRetry(2, new ApiError('INTERNAL_ERROR', 'x', 500))).toBe(false)
  })
})

describe('AppProviders', () => {
  it('provides a QueryClient to descendants', () => {
    function Probe() {
      return <p>{useQueryClient() ? 'has-client' : 'no-client'}</p>
    }

    render(
      <AppProviders>
        <Probe />
      </AppProviders>,
    )

    expect(screen.getByText('has-client')).toBeInTheDocument()
  })
})
