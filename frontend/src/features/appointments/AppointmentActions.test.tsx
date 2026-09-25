import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ERROR_MESSAGES } from '../../api/errorMessages'
import { tokenStore } from '../../auth/tokenStore'
import { ADMIN, DOCTOR, renderApp, type Handlers } from '../../test/renderApp'

afterEach(() => {
  tokenStore.clear()
  vi.unstubAllGlobals()
})

const DR_DAN = {
  id: 'd1',
  userId: DOCTOR.id,
  name: 'Dr Dan',
  specialtyId: 's1',
  slotLengthMinutes: 20,
  active: true,
}
const DR_EVE = { ...DR_DAN, id: 'd2', userId: 'u-eve', name: 'Dr Eve' }
const SETTINGS = {
  cancellationCutoffHours: 2,
  emergencySlotsPerDoctorPerDay: 1,
  followUpMaxDays: 30,
  clinicTimezone: 'Asia/Kolkata',
  defaultTriageSpecialtyId: null,
}
const base = (status: string, doctorId = 'd1') => ({
  id: 'a1',
  doctorId,
  patientId: 'p1',
  startTime: '2026-03-02T03:30:00Z', // 09:00 in Asia/Kolkata
  endTime: '2026-03-02T03:50:00Z',
  status,
  source: 'scheduled',
  isEmergencySlot: false,
  reportedSymptoms: null,
  createdAt: '2026-03-01T00:00:00Z',
})
const ASHA = {
  id: 'p1',
  name: 'Asha Rao',
  phone: '+919876543210',
  dob: null,
  email: null,
  createdAt: '2026-03-01T00:00:00Z',
}
const slot = (start: string, end: string) => ({
  doctorId: 'd1',
  specialtyId: 's1',
  startTime: start,
  endTime: end,
  isEmergency: false,
})

/** A stateful mock: lifecycle POSTs move the appointment to the status they lead to. */
function api(user: typeof ADMIN, initial: string, extra: Handlers = {}, doctorId = 'd1') {
  let current = base(initial, doctorId)
  const move = (status: string) => () => {
    current = { ...current, status }
    return { body: current }
  }
  return {
    'GET /api/v1/auth/me': () => ({ body: user }),
    'GET /api/v1/doctors': () => ({ body: [DR_DAN, DR_EVE] }),
    'GET /api/v1/clinic-settings': () => ({ body: SETTINGS }),
    'GET /api/v1/patients/p1': () => ({ body: ASHA }),
    'GET /api/v1/appointments/a1': () => ({ body: current }),
    'POST /api/v1/appointments/a1/check-in': move('checked_in'),
    'POST /api/v1/appointments/a1/start-consultation': move('in_consultation'),
    'POST /api/v1/appointments/a1/complete': move('completed'),
    'POST /api/v1/appointments/a1/no-show': move('no_show'),
    'POST /api/v1/appointments/a1/cancel': move('cancelled'),
    'GET /api/v1/slots': () => ({
      body: [
        slot('2026-03-09T03:30:00Z', '2026-03-09T03:50:00Z'),
        slot('2026-03-09T03:50:00Z', '2026-03-09T04:10:00Z'),
      ],
    }),
    ...extra,
  } satisfies Handlers
}

const open = (handlers: Handlers) => renderApp(handlers, { path: '/appointments/a1', token: 't' })
const buttonNames = () => screen.queryAllByRole('button').map((b) => b.textContent)

describe('Action buttons by status', () => {
  it.each([
    ['booked', ['Check in', 'No-show', 'Cancel', 'Reschedule', 'Force cancel']],
    ['checked_in', ['Start consultation', 'No-show', 'Cancel', 'Force cancel']],
    ['in_consultation', ['Complete']],
    ['completed', ['Book follow-up']],
    ['no_show', []],
    ['cancelled', []],
  ])('front-desk sees the right actions for a %s appointment', async (status, expected) => {
    open(api(ADMIN, status))

    await screen.findByRole('heading', { name: 'Appointment' })
    await screen.findByText('Dr Dan')
    const names = buttonNames().filter((n) => n !== 'Sign out')
    expect(names.sort()).toEqual([...expected].sort())
  })

  it('a doctor sees the same actions on their own appointment but never Force cancel', async () => {
    open(api(DOCTOR, 'booked'))

    await screen.findByRole('button', { name: 'Check in' })
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Force cancel' })).not.toBeInTheDocument()
  })

  it('a doctor sees no actions on another doctors appointment', async () => {
    open(api(DOCTOR, 'booked', {}, 'd2'))

    await screen.findByRole('heading', { name: 'Appointment' })
    await screen.findByText('Dr Eve')
    expect(buttonNames().filter((n) => n !== 'Sign out')).toEqual([])
  })
})

describe('Lifecycle actions', () => {
  it('moves through check-in, start and complete, updating the status shown', async () => {
    const { calls } = open(api(ADMIN, 'booked'))

    await userEvent.click(await screen.findByRole('button', { name: 'Check in' }))
    expect(await screen.findByText('Checked in')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Start consultation' }))
    expect(await screen.findByText('In consultation')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Complete' }))
    expect(await screen.findByText('Completed')).toBeInTheDocument()
    expect(calls.filter((c) => c.method === 'POST').map((c) => c.path)).toEqual([
      '/api/v1/appointments/a1/check-in',
      '/api/v1/appointments/a1/start-consultation',
      '/api/v1/appointments/a1/complete',
    ])
  })

  it('marks a no-show', async () => {
    open(api(ADMIN, 'booked'))

    await userEvent.click(await screen.findByRole('button', { name: 'No-show' }))

    expect(await screen.findByText('No-show')).toBeInTheDocument()
  })

  it('explains an invalid transition and refreshes the status', async () => {
    open(
      api(ADMIN, 'booked', {
        'POST /api/v1/appointments/a1/check-in': () => ({
          status: 409,
          body: { code: 'INVALID_TRANSITION', message: 'raw' },
        }),
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Check in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(ERROR_MESSAGES.INVALID_TRANSITION)
  })
})

describe('Cancel and force-cancel', () => {
  it('cancels after confirmation and shows the cutoff policy', async () => {
    const { calls } = open(api(ADMIN, 'booked'))

    await userEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
    const dialog = screen.getByRole('dialog', { name: 'Cancel appointment' })
    expect(within(dialog).getByText(/up to 2 hours before/)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel appointment' }))

    expect(await screen.findByText('Cancelled')).toBeInTheDocument()
    expect(calls.some((c) => c.path.endsWith('/cancel') && c.method === 'POST')).toBe(true)
  })

  it('front-desk can force-cancel with a mandatory reason when the window is closed', async () => {
    const { calls } = open(
      api(ADMIN, 'booked', {
        'POST /api/v1/appointments/a1/cancel': () => ({
          status: 422,
          body: { code: 'CANCELLATION_WINDOW_CLOSED', message: 'raw' },
        }),
        'POST /api/v1/appointments/a1/force-cancel': ({ body }) => ({
          body: {
            ...base('cancelled'),
            cancellationType: 'force',
            cancelReason: (body as { reason: string }).reason,
          },
        }),
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
    await userEvent.click(
      within(screen.getByRole('dialog', { name: 'Cancel appointment' })).getByRole('button', {
        name: 'Cancel appointment',
      }),
    )
    const blocked = await screen.findByRole('alert')
    expect(blocked).toHaveTextContent(ERROR_MESSAGES.CANCELLATION_WINDOW_CLOSED)

    await userEvent.click(screen.getByRole('button', { name: 'Force cancel instead' }))
    const force = screen.getByRole('dialog', { name: 'Force cancel appointment' })
    await userEvent.click(within(force).getByRole('button', { name: 'Force cancel' }))
    expect(within(force).getByRole('alert')).toHaveTextContent('reason')
    expect(calls.some((c) => c.path.endsWith('/force-cancel'))).toBe(false)

    await userEvent.type(within(force).getByLabelText('Reason'), 'Patient hospitalised')
    await userEvent.click(within(force).getByRole('button', { name: 'Force cancel' }))

    await vi.waitFor(() =>
      expect(calls.find((c) => c.path.endsWith('/force-cancel'))?.body).toEqual({
        reason: 'Patient hospitalised',
      }),
    )
  })

  it('a doctor whose cancel is blocked gets the explanation but no force option', async () => {
    open(
      api(DOCTOR, 'booked', {
        'POST /api/v1/appointments/a1/cancel': () => ({
          status: 422,
          body: { code: 'CANCELLATION_WINDOW_CLOSED', message: 'raw' },
        }),
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
    await userEvent.click(
      within(screen.getByRole('dialog', { name: 'Cancel appointment' })).getByRole('button', {
        name: 'Cancel appointment',
      }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(
      ERROR_MESSAGES.CANCELLATION_WINDOW_CLOSED,
    )
    expect(screen.queryByRole('button', { name: 'Force cancel instead' })).not.toBeInTheDocument()
  })
})

describe('Reschedule', () => {
  it('picks a new slot for the same doctor and opens the new appointment', async () => {
    const { calls } = open(
      api(ADMIN, 'booked', {
        'POST /api/v1/appointments/a1/reschedule': () => ({
          body: { ...base('booked'), id: 'a2', startTime: '2026-03-09T03:50:00Z' },
        }),
        'GET /api/v1/appointments/a2': () => ({
          body: { ...base('booked'), id: 'a2', startTime: '2026-03-09T03:50:00Z' },
        }),
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Reschedule' }))
    const dialog = screen.getByRole('dialog', { name: 'Reschedule appointment' })
    await userEvent.type(within(dialog).getByLabelText('Date'), '2026-03-09')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Find slots' }))
    await userEvent.click(await within(dialog).findByRole('button', { name: '09:20' }))

    await vi.waitFor(() =>
      expect(calls.find((c) => c.path.endsWith('/reschedule'))?.body).toEqual({
        newStartTime: '2026-03-09T03:50:00Z',
      }),
    )
    expect(await screen.findByText('Mon 9 Mar 2026, 09:20')).toBeInTheDocument()
    const slotRequest = calls.find((c) => c.path.startsWith('/api/v1/slots'))!
    expect(slotRequest.path).toContain('doctorId=d1')
    expect(slotRequest.path).not.toContain('includeEmergency')
  })

  it('reports a cutoff rejection', async () => {
    open(
      api(ADMIN, 'booked', {
        'POST /api/v1/appointments/a1/reschedule': () => ({
          status: 422,
          body: { code: 'CANCELLATION_WINDOW_CLOSED', message: 'raw' },
        }),
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Reschedule' }))
    const dialog = screen.getByRole('dialog', { name: 'Reschedule appointment' })
    await userEvent.type(within(dialog).getByLabelText('Date'), '2026-03-09')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Find slots' }))
    await userEvent.click(await within(dialog).findByRole('button', { name: '09:00' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      ERROR_MESSAGES.CANCELLATION_WINDOW_CLOSED,
    )
  })
})

describe('Follow-up', () => {
  it('limits the date to the follow-up window and books for the same doctor', async () => {
    const { calls } = open(
      api(ADMIN, 'completed', {
        'POST /api/v1/appointments/a1/follow-up': () => ({
          status: 201,
          body: { ...base('booked'), id: 'a3', followUpOfAppointmentId: 'a1' },
        }),
        'GET /api/v1/appointments/a3': () => ({ body: { ...base('booked'), id: 'a3' } }),
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Book follow-up' }))
    const dialog = screen.getByRole('dialog', { name: 'Book follow-up' })
    const date = within(dialog).getByLabelText('Date')
    expect(date).toHaveAttribute('max', '2026-04-01') // 2026-03-02 + 30 days
    expect(date).toHaveAttribute('min', '2026-03-02')
    await userEvent.type(date, '2026-03-09')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Find slots' }))
    await userEvent.click(await within(dialog).findByRole('button', { name: '09:00' }))

    await vi.waitFor(() =>
      expect(calls.find((c) => c.path.endsWith('/follow-up'))?.body).toEqual({
        startTime: '2026-03-09T03:30:00Z',
      }),
    )
    expect(calls.find((c) => c.path.startsWith('/api/v1/slots'))!.path).toContain('doctorId=d1')
  })

  it('shows the server message when the follow-up is outside the window', async () => {
    open(
      api(ADMIN, 'completed', {
        'POST /api/v1/appointments/a1/follow-up': () => ({
          status: 422,
          body: { code: 'FOLLOW_UP_WINDOW_EXCEEDED', message: 'raw' },
        }),
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Book follow-up' }))
    const dialog = screen.getByRole('dialog', { name: 'Book follow-up' })
    await userEvent.type(within(dialog).getByLabelText('Date'), '2026-03-09')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Find slots' }))
    await userEvent.click(await within(dialog).findByRole('button', { name: '09:00' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      ERROR_MESSAGES.FOLLOW_UP_WINDOW_EXCEEDED,
    )
  })
})
