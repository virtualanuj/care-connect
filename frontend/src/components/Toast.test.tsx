import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ApiError } from '../api/client'
import { ERROR_MESSAGES } from '../api/errorMessages'
import { ToastProvider, useToast } from './Toast'

function Trigger({ error }: { error: unknown }) {
  const { showError } = useToast()
  return <button onClick={() => showError(error)}>fail</button>
}

describe('ToastProvider', () => {
  it('shows the friendly message for an ApiError as an alert', async () => {
    render(
      <ToastProvider>
        <Trigger error={new ApiError('CANCELLATION_WINDOW_CLOSED', 'x', 422)} />
      </ToastProvider>,
    )

    await userEvent.click(screen.getByText('fail'))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      ERROR_MESSAGES.CANCELLATION_WINDOW_CLOSED,
    )
  })

  it('can be dismissed', async () => {
    render(
      <ToastProvider>
        <Trigger error={new ApiError('FORBIDDEN', 'x', 403)} />
      </ToastProvider>,
    )
    await userEvent.click(screen.getByText('fail'))

    await userEvent.click(await screen.findByRole('button', { name: 'Dismiss' }))

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
