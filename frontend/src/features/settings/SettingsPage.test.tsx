import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ERROR_MESSAGES } from '../../api/errorMessages'
import { tokenStore } from '../../auth/tokenStore'
import { ADMIN, DOCTOR, renderApp, type Handlers } from '../../test/renderApp'

afterEach(() => {
  tokenStore.clear()
  vi.unstubAllGlobals()
})

const SETTINGS = {
  cancellationCutoffHours: 2,
  emergencySlotsPerDoctorPerDay: 1,
  followUpMaxDays: 30,
  clinicTimezone: 'Asia/Kolkata',
  defaultTriageSpecialtyId: null,
}

function api(user: typeof ADMIN, extra: Handlers = {}) {
  return {
    'GET /api/v1/auth/me': () => ({ body: user }),
    'GET /api/v1/clinic-settings': () => ({ body: SETTINGS }),
    'GET /api/v1/specialties': () => ({
      body: [{ id: 's1', name: 'General Medicine', defaultSlotLengthMinutes: 20 }],
    }),
    ...extra,
  } satisfies Handlers
}

const open = (handlers: Handlers) => renderApp(handlers, { path: '/settings', token: 't' })

describe('Clinic settings page', () => {
  it('shows the current values', async () => {
    open(api(ADMIN))

    expect(await screen.findByLabelText('Cancellation cutoff (hours)')).toHaveValue(2)
    expect(screen.getByLabelText('Emergency slots per doctor per day')).toHaveValue(1)
    expect(screen.getByLabelText('Follow-up window (days)')).toHaveValue(30)
    expect(screen.getByLabelText('Clinic time zone')).toHaveValue('Asia/Kolkata')
  })

  it('front-desk saves only the changed fields', async () => {
    const { calls } = open(
      api(ADMIN, {
        'PATCH /api/v1/clinic-settings': () => ({ body: { ...SETTINGS, followUpMaxDays: 14 } }),
      }),
    )

    const followUp = await screen.findByLabelText('Follow-up window (days)')
    await userEvent.clear(followUp)
    await userEvent.type(followUp, '14')
    await userEvent.click(screen.getByRole('button', { name: 'Save settings' }))

    expect(await screen.findByText('Settings saved')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ followUpMaxDays: 14 })
  })

  it('can set the default triage specialty', async () => {
    const { calls } = open(
      api(ADMIN, {
        'PATCH /api/v1/clinic-settings': () => ({
          body: { ...SETTINGS, defaultTriageSpecialtyId: 's1' },
        }),
      }),
    )

    await userEvent.selectOptions(await screen.findByLabelText('Default triage specialty'), 's1')
    await userEvent.click(screen.getByRole('button', { name: 'Save settings' }))

    await screen.findByText('Settings saved')
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({
      defaultTriageSpecialtyId: 's1',
    })
  })

  it('blocks invalid values before calling the API', async () => {
    const { calls } = open(api(ADMIN))

    const cutoff = await screen.findByLabelText('Cancellation cutoff (hours)')
    await userEvent.clear(cutoff)
    await userEvent.type(cutoff, '-1')
    const followUp = screen.getByLabelText('Follow-up window (days)')
    await userEvent.clear(followUp)
    await userEvent.type(followUp, '0')
    await userEvent.click(screen.getByRole('button', { name: 'Save settings' }))

    const text = (await screen.findAllByRole('alert')).map((a) => a.textContent).join(' ')
    expect(text).toMatch(/cutoff.*0 or more/i)
    expect(text).toMatch(/follow-up.*at least 1/i)
    expect(calls.some((c) => c.method === 'PATCH')).toBe(false)
  })

  it('shows a server-side rejection', async () => {
    open(
      api(ADMIN, {
        'PATCH /api/v1/clinic-settings': () => ({
          status: 400,
          body: { code: 'VALIDATION_ERROR', message: 'raw' },
        }),
      }),
    )

    const followUp = await screen.findByLabelText('Follow-up window (days)')
    await userEvent.clear(followUp)
    await userEvent.type(followUp, '7')
    await userEvent.click(screen.getByRole('button', { name: 'Save settings' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(ERROR_MESSAGES.VALIDATION_ERROR)
  })

  it('is read-only for doctors', async () => {
    open(api(DOCTOR))

    expect(await screen.findByLabelText('Follow-up window (days)')).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Save settings' })).not.toBeInTheDocument()
    expect(screen.getByText(/only front-desk staff can change/i)).toBeInTheDocument()
  })
})
