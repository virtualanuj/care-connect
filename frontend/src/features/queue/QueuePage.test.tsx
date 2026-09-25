import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

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
const DR_DAN = {
  id: 'd1',
  userId: DOCTOR.id,
  name: 'Dr Dan',
  specialtyId: 's1',
  slotLengthMinutes: 20,
  active: true,
}

const item = (id: string, patientName: string, start: string, status: string, extra = {}) => ({
  id,
  doctorId: 'd1',
  patientId: `p-${id}`,
  patientName,
  doctorName: 'Dr Dan',
  startTime: start,
  endTime: start,
  status,
  source: 'scheduled',
  isEmergencySlot: false,
  reportedSymptoms: null,
  createdAt: '2026-03-01T00:00:00Z',
  ...extra,
})
// 03:30Z = 09:00 in Asia/Kolkata
const BOOKED = item('a1', 'Asha Rao', '2026-03-02T03:30:00Z', 'booked')
const WAITING = item('a2', 'Kiran Rao', '2026-03-02T03:50:00Z', 'checked_in', { source: 'walk_in' })
const IN_ROOM = item('a3', 'Meera Iyer', '2026-03-02T04:10:00Z', 'in_consultation')
const DONE = item('a4', 'Nisha Verma', '2026-03-02T04:30:00Z', 'completed')
const GONE = item('a5', 'Tara Verma', '2026-03-02T04:50:00Z', 'no_show')
const CANCELLED = item('a6', 'Ishaan Menon', '2026-03-02T05:10:00Z', 'cancelled')
const EMERGENCY = item('a7', 'Rohan Das', '2026-03-02T05:30:00Z', 'booked', {
  source: 'walk_in',
  isEmergencySlot: true,
})

const emptyQueue = (date = '2026-03-02') => ({
  date,
  booked: [],
  checkedIn: [],
  inProgress: [],
  completed: [],
  noShows: [],
  cancelled: [],
})

function api(user: typeof ADMIN, queue: Record<string, unknown> = {}, extra: Handlers = {}) {
  return {
    'GET /api/v1/auth/me': () => ({ body: user }),
    'GET /api/v1/clinic-settings': () => ({ body: SETTINGS }),
    'GET /api/v1/doctors': () => ({ body: [DR_DAN] }),
    'GET /api/v1/queue': ({ url }) => ({
      body: {
        ...emptyQueue(url.searchParams.get('date') ?? '2026-03-02'),
        booked: [BOOKED, EMERGENCY],
        checkedIn: [WAITING],
        inProgress: [IN_ROOM],
        completed: [DONE],
        noShows: [GONE],
        cancelled: [CANCELLED],
        ...queue,
      },
    }),
    ...extra,
  } satisfies Handlers
}

const open = (handlers: Handlers) => renderApp(handlers, { path: '/queue', token: 't' })
const column = async (name: RegExp) =>
  (await screen.findByRole('heading', { name })).closest('section')!

describe('Daily queue', () => {
  it('shows every status in its own column with counts, names and clinic-zone times', async () => {
    open(api(ADMIN))

    const booked = await column(/^Booked/)
    expect(within(booked).getByRole('heading', { name: 'Booked (2)' })).toBeInTheDocument()
    expect(within(booked).getByText('Asha Rao')).toBeInTheDocument()
    expect(within(booked).getByText('09:00')).toBeInTheDocument()
    expect(within(await column(/^Checked in/)).getByText('Kiran Rao')).toBeInTheDocument()
    expect(within(await column(/^In consultation/)).getByText('Meera Iyer')).toBeInTheDocument()
    expect(within(await column(/^Completed/)).getByText('Nisha Verma')).toBeInTheDocument()
    expect(within(await column(/^No-show/)).getByText('Tara Verma')).toBeInTheDocument()
    expect(within(await column(/^Cancelled/)).getByText('Ishaan Menon')).toBeInTheDocument()
  })

  it('marks walk-ins and emergency-slot bookings so they are distinguishable', async () => {
    open(api(ADMIN))

    const waiting = (await screen.findByText('Kiran Rao')).closest('li')!
    expect(within(waiting).getByText('Walk-in')).toBeInTheDocument()
    const emergency = screen.getByText('Rohan Das').closest('li')!
    expect(within(emergency).getByText('Walk-in')).toBeInTheDocument()
    expect(within(emergency).getByText('Emergency')).toBeInTheDocument()
    const regular = screen.getByText('Asha Rao').closest('li')!
    expect(within(regular).queryByText('Walk-in')).not.toBeInTheDocument()
  })

  it('says nobody is in an empty column', async () => {
    open(api(ADMIN, { booked: [], checkedIn: [] }))

    const booked = await column(/^Booked/)
    expect(within(booked).getByText('Nobody here')).toBeInTheDocument()
  })

  it('loads another date when the date changes', async () => {
    const { calls } = open(api(ADMIN))

    const date = await screen.findByLabelText('Date')
    fireEvent.change(date, { target: { value: '2026-03-09' } })

    await vi.waitFor(() =>
      expect(calls.some((c) => c.path.includes('/queue?date=2026-03-09'))).toBe(true),
    )
  })

  it('moves a patient between columns from the row actions', async () => {
    let queue = { booked: [BOOKED], checkedIn: [] as unknown[] }
    const { calls } = open(
      api(
        ADMIN,
        {},
        {
          'GET /api/v1/queue': () => ({
            body: {
              ...emptyQueue(),
              booked: queue.booked,
              checkedIn: queue.checkedIn,
            },
          }),
          'POST /api/v1/appointments/a1/check-in': () => {
            queue = { booked: [], checkedIn: [{ ...BOOKED, status: 'checked_in' }] }
            return { body: { ...BOOKED, status: 'checked_in' } }
          },
        },
      ),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Check in Asha Rao' }))

    const waiting = await column(/^Checked in/)
    expect(await within(waiting).findByText('Asha Rao')).toBeInTheDocument()
    expect(within(await column(/^Booked/)).queryByText('Asha Rao')).not.toBeInTheDocument()
    expect(calls.some((c) => c.path === '/api/v1/appointments/a1/check-in')).toBe(true)
  })

  it('offers the next step for each status', async () => {
    open(api(ADMIN))

    expect(await screen.findByRole('button', { name: 'Check in Asha Rao' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'No-show Asha Rao' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start consultation Kiran Rao' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Complete Meera Iyer' })).toBeInTheDocument()
    const done = screen.getByText('Nisha Verma').closest('li')!
    expect(within(done).queryByRole('button')).not.toBeInTheDocument()
  })

  it('links to the walk-in flow for front-desk only', async () => {
    const first = open(api(ADMIN))
    expect(await screen.findByRole('link', { name: 'Register walk-in' })).toHaveAttribute(
      'href',
      '/walk-in',
    )
    first.unmount()

    open(api(DOCTOR))
    await screen.findByText('Asha Rao')
    expect(screen.queryByRole('link', { name: 'Register walk-in' })).not.toBeInTheDocument()
  })

  it('reports a load failure', async () => {
    open(
      api(
        ADMIN,
        {},
        {
          'GET /api/v1/queue': () => ({
            status: 500,
            body: { code: 'INTERNAL_ERROR', message: 'x' },
          }),
        },
      ),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the queue')
  })
})
