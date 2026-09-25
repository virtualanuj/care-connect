import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

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
const SETTINGS = {
  cancellationCutoffHours: 2,
  emergencySlotsPerDoctorPerDay: 1,
  followUpMaxDays: 30,
  clinicTimezone: 'Asia/Kolkata',
  defaultTriageSpecialtyId: null,
}
const appointment = (id: string, patientId: string, start: string, status = 'booked') => ({
  id,
  doctorId: 'd1',
  patientId,
  startTime: start,
  endTime: start,
  status,
  source: 'scheduled',
  isEmergencySlot: false,
  reportedSymptoms: null,
  createdAt: '2026-03-01T00:00:00Z',
})
const A1 = appointment('a1', 'p1', '2026-03-02T03:30:00Z')
const A2 = appointment('a2', 'p2', '2026-03-02T03:50:00Z', 'checked_in')
const patient = (id: string, name: string) => ({
  id,
  name,
  phone: '+919876543210',
  dob: null,
  email: null,
  createdAt: '2026-03-01T00:00:00Z',
})

function api(user: typeof ADMIN, total = 2, extra: Handlers = {}) {
  return {
    'GET /api/v1/auth/me': () => ({ body: user }),
    'GET /api/v1/doctors': () => ({ body: [DR_DAN] }),
    'GET /api/v1/clinic-settings': () => ({ body: SETTINGS }),
    'GET /api/v1/appointments': ({ url }) => ({
      body: {
        items: total === 0 ? [] : [A1, A2],
        page: Number(url.searchParams.get('page') ?? 1),
        pageSize: 20,
        total,
      },
    }),
    'GET /api/v1/patients/p1': () => ({ body: patient('p1', 'Asha Rao') }),
    'GET /api/v1/patients/p2': () => ({ body: patient('p2', 'Kiran Rao') }),
    ...extra,
  } satisfies Handlers
}

const open = (handlers: Handlers, path = '/appointments') =>
  renderApp(handlers, { path, token: 't' })

describe('Appointments list', () => {
  it('lists appointments with doctor and patient names and clinic-zone times', async () => {
    open(api(ADMIN))

    const row = (await screen.findByText('Asha Rao')).closest('tr')!
    expect(within(row).getByText('Dr Dan')).toBeInTheDocument()
    expect(within(row).getByText('Mon 2 Mar 2026, 09:00')).toBeInTheDocument()
    expect(within(row).getByText('Booked')).toBeInTheDocument()
    expect(
      within(screen.getByText('Kiran Rao').closest('tr')!).getByText('Checked in'),
    ).toBeInTheDocument()
  })

  it('sends the chosen filters', async () => {
    const { calls } = open(api(ADMIN))

    await userEvent.type(await screen.findByLabelText('Date'), '2026-03-02')
    await userEvent.selectOptions(screen.getByLabelText('Doctor'), 'd1')
    await userEvent.selectOptions(screen.getByLabelText('Status'), 'booked')
    await userEvent.click(screen.getByRole('button', { name: 'Apply filters' }))

    await vi.waitFor(() => {
      const last = calls.filter((c) => c.path.startsWith('/api/v1/appointments')).at(-1)!
      expect(last.path).toContain('date=2026-03-02')
      expect(last.path).toContain('doctorId=d1')
      expect(last.path).toContain('status=booked')
    })
  })

  it('paginates', async () => {
    const { calls } = open(api(ADMIN, 45))

    expect(await screen.findByText('Page 1 of 3')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByText('Page 2 of 3')).toBeInTheDocument()
    expect(calls.some((c) => c.path.includes('page=2'))).toBe(true)
  })

  it('says so when nothing matches', async () => {
    open(api(ADMIN, 0))

    expect(await screen.findByText('No appointments match.')).toBeInTheDocument()
  })

  it('shows a doctor no doctor filter, and never asks for another doctor', async () => {
    const { calls } = open(api(DOCTOR))

    await screen.findByText('Asha Rao')
    expect(screen.queryByLabelText('Doctor')).not.toBeInTheDocument()
    expect(calls.filter((c) => c.path.startsWith('/api/v1/appointments'))[0].path).not.toContain(
      'doctorId',
    )
  })

  it('links to the booking screen', async () => {
    open(api(ADMIN))

    expect(await screen.findByRole('link', { name: 'Book appointment' })).toHaveAttribute(
      'href',
      '/book',
    )
  })
})

describe('Appointment detail', () => {
  it('shows the appointment read-only', async () => {
    open(
      api(ADMIN, 2, {
        'GET /api/v1/appointments/a1': () => ({
          body: { ...A1, reportedSymptoms: 'cough and fever' },
        }),
        'GET /api/v1/doctors/d1': () => ({ body: DR_DAN }),
      }),
      '/appointments/a1',
    )

    expect(await screen.findByRole('heading', { name: 'Appointment' })).toBeInTheDocument()
    expect(await screen.findByText('Mon 2 Mar 2026, 09:00')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Asha Rao' })).toHaveAttribute('href', '/patients/p1')
    expect(screen.getByText('Dr Dan')).toBeInTheDocument()
    expect(screen.getByText('Booked')).toBeInTheDocument()
    expect(screen.getByText('cough and fever')).toBeInTheDocument()
    expect(screen.getByText('Scheduled')).toBeInTheDocument()
  })

  it('shows a not-found message for an unknown appointment', async () => {
    open(
      api(ADMIN, 2, {
        'GET /api/v1/appointments/zzz': () => ({
          status: 404,
          body: { code: 'NOT_FOUND', message: 'raw' },
        }),
      }),
      '/appointments/zzz',
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('Appointment not found')
  })
})
