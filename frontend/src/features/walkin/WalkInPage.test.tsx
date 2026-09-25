import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { tokenStore } from '../../auth/tokenStore'
import { ADMIN, DOCTOR, renderApp, type Handlers } from '../../test/renderApp'

afterEach(() => {
  tokenStore.clear()
  vi.unstubAllGlobals()
})

const SPECIALTIES = [{ id: 's1', name: 'General Medicine', defaultSlotLengthMinutes: 20 }]
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
const ASHA = {
  id: 'p1',
  name: 'Asha Rao',
  phone: '+919876543210',
  dob: null,
  email: null,
  createdAt: '2026-03-01T00:00:00Z',
}
const BOOKED = {
  id: 'a1',
  doctorId: 'd1',
  patientId: 'p1',
  startTime: '2026-03-02T03:30:00Z',
  endTime: '2026-03-02T03:50:00Z',
  status: 'booked',
  source: 'walk_in',
  isEmergencySlot: false,
  reportedSymptoms: null,
  createdAt: '2026-03-01T00:00:00Z',
}
const slot = (doctorId: string, start: string, isEmergency = false) => ({
  doctorId,
  specialtyId: 's1',
  startTime: start,
  endTime: start,
  isEmergency,
})
const DAN_0900 = slot('d1', '2026-03-02T03:30:00Z')
const EVE_0920 = slot('d2', '2026-03-02T03:50:00Z')
const EVE_EMERGENCY = slot('d2', '2026-03-02T04:10:00Z', true) // 09:40 IST

/** Slot responses per search shape: doctor / specialty / specialty + emergency. */
function api(
  slots: { doctor?: unknown[]; specialty?: unknown[]; emergency?: unknown[] },
  extra: Handlers = {},
) {
  return {
    'GET /api/v1/auth/me': () => ({ body: ADMIN }),
    'GET /api/v1/doctors': () => ({ body: [DR_DAN, DR_EVE] }),
    'GET /api/v1/specialties': () => ({ body: SPECIALTIES }),
    'GET /api/v1/clinic-settings': () => ({ body: SETTINGS }),
    'GET /api/v1/patients': () => ({ body: { items: [ASHA], page: 1, pageSize: 20, total: 1 } }),
    'GET /api/v1/slots': ({ url }) => {
      if (url.searchParams.get('doctorId')) return { body: slots.doctor ?? [] }
      if (url.searchParams.get('includeEmergency')) return { body: slots.emergency ?? [] }
      return { body: slots.specialty ?? [] }
    },
    'GET /api/v1/appointments/a1': () => ({ body: BOOKED }),
    'GET /api/v1/patients/p1': () => ({ body: ASHA }),
    'GET /api/v1/patients/p1/triage': () => ({ body: [] }),
    ...extra,
  } satisfies Handlers
}

const open = (handlers: Handlers, user = ADMIN) =>
  renderApp(
    { ...handlers, 'GET /api/v1/auth/me': () => ({ body: user }) },
    { path: '/walk-in', token: 't' },
  )

async function choosePatient() {
  await userEvent.type(await screen.findByLabelText('Patient phone'), '98765 43210')
  await userEvent.click(screen.getByRole('button', { name: 'Find patient' }))
  await userEvent.click(await screen.findByRole('radio', { name: /Asha Rao/ }))
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
}

async function findSlotsFor(doctor = 'd1') {
  fireEvent.change(await screen.findByLabelText('Date'), { target: { value: '2026-03-02' } })
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Requested doctor' }), doctor)
  await userEvent.click(screen.getByRole('button', { name: 'Find slots' }))
}

describe('Walk-in registration', () => {
  it('offers the requested doctor first when they have regular slots', async () => {
    const { calls } = open(api({ doctor: [DAN_0900], specialty: [EVE_0920] }))

    await choosePatient()
    await findSlotsFor('d1')

    expect(await screen.findByText('Dr Dan has open slots.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '09:00' })).toBeInTheDocument()
    expect(calls.filter((c) => c.path.startsWith('/api/v1/slots'))).toHaveLength(1) // no fallback needed
  })

  it('falls back to other doctors of the specialty and says why', async () => {
    const { calls } = open(api({ doctor: [], specialty: [EVE_0920] }))

    await choosePatient()
    await findSlotsFor('d1')

    expect(
      await screen.findByText(
        'Dr Dan has no open slots on this day. Other doctors in General Medicine:',
      ),
    ).toBeInTheDocument()
    const eve = screen.getByRole('heading', { name: 'Dr Eve' }).closest('section')!
    expect(within(eve).getByRole('button', { name: '09:20' })).toBeInTheDocument()
    const paths = calls.filter((c) => c.path.startsWith('/api/v1/slots')).map((c) => c.path)
    expect(paths[0]).toContain('doctorId=d1')
    expect(paths[1]).toContain('specialtyId=s1')
    expect(paths[1]).not.toContain('includeEmergency')
  })

  it('uses emergency-held capacity only when there is no regular slot anywhere', async () => {
    const { calls } = open(api({ doctor: [], specialty: [], emergency: [EVE_EMERGENCY] }))

    await choosePatient()
    await findSlotsFor('d1')

    expect(
      await screen.findByText(/No regular slots are available.*Emergency-held slots/),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /09:40/ })).toBeInTheDocument()
    const last = calls.filter((c) => c.path.startsWith('/api/v1/slots')).at(-1)!
    expect(last.path).toContain('includeEmergency=true')
  })

  it('says so when nothing at all is available', async () => {
    open(api({}))

    await choosePatient()
    await findSlotsFor('d1')

    expect(
      await screen.findByText('No slots or emergency capacity are available for that day.'),
    ).toBeInTheDocument()
  })

  it('books a regular walk-in with source walk_in and opens the appointment', async () => {
    const { calls } = open(
      api(
        { doctor: [DAN_0900] },
        { 'POST /api/v1/appointments': () => ({ status: 201, body: BOOKED }) },
      ),
    )

    await choosePatient()
    await findSlotsFor('d1')
    await userEvent.click(await screen.findByRole('button', { name: '09:00' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Confirm booking' }))

    expect(await screen.findByRole('heading', { name: 'Appointment' })).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      doctorId: 'd1',
      patientId: 'p1',
      startTime: '2026-03-02T03:30:00Z',
      source: 'walk_in',
    })
  })

  it('requires a reason for emergency capacity and sends the front-desk judgment', async () => {
    const { calls } = open(
      api(
        { doctor: [], specialty: [], emergency: [EVE_EMERGENCY] },
        {
          'POST /api/v1/appointments': () => ({
            status: 201,
            body: { ...BOOKED, isEmergencySlot: true },
          }),
        },
      ),
    )

    await choosePatient()
    await findSlotsFor('d1')
    await userEvent.click(await screen.findByRole('button', { name: /09:40/ }))
    expect(await screen.findByText(/held for emergencies/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Confirm booking' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('reason is required')
    expect(calls.some((c) => c.method === 'POST')).toBe(false)

    await userEvent.type(screen.getByLabelText('Reason for using emergency capacity'), 'Chest pain')
    await userEvent.click(screen.getByRole('button', { name: 'Confirm booking' }))

    await vi.waitFor(() =>
      expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
        doctorId: 'd2',
        patientId: 'p1',
        startTime: '2026-03-02T04:10:00Z',
        source: 'walk_in',
        emergencyJustification: 'front_desk_judgment',
        emergencyReason: 'Chest pain',
      }),
    )
  })

  it('is available to front-desk only', async () => {
    open(api({}), DOCTOR)

    expect(await screen.findByRole('heading', { name: 'Not permitted' })).toBeInTheDocument()
  })

  const triageResult = (effectiveUrgency: string) => ({
    id: 't9',
    patientId: 'p1',
    reportedSymptoms: 'collapsed',
    urgency: effectiveUrgency,
    effectiveUrgency,
    suggestedSpecialtyId: 's1',
    confidenceScore: 0.9,
    source: 'model',
    disclaimer: 'AI suggestion only.',
    createdAt: '2026-03-01T12:00:00Z',
  })

  async function toEmergencyConfirm() {
    await choosePatient()
    await findSlotsFor('d1')
    await userEvent.click(await screen.findByRole('button', { name: /09:40/ }))
    await userEvent.type(await screen.findByLabelText('Symptoms for triage'), 'collapsed')
    await userEvent.click(screen.getByRole('button', { name: 'Run triage' }))
    await screen.findByText('AI suggestion only.')
  }

  it('offers authorization by an emergency triage result and sends it without a typed reason', async () => {
    const { calls } = open(
      api(
        { doctor: [], specialty: [], emergency: [EVE_EMERGENCY] },
        {
          'POST /api/v1/patients/p1/triage': () => ({
            status: 201,
            body: triageResult('emergency'),
          }),
          'POST /api/v1/appointments': () => ({
            status: 201,
            body: { ...BOOKED, isEmergencySlot: true },
          }),
        },
      ),
    )

    await toEmergencyConfirm()
    await userEvent.selectOptions(screen.getByLabelText('Authorization'), 'triage')
    expect(screen.queryByLabelText('Reason for using emergency capacity')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Confirm booking' }))

    await vi.waitFor(() =>
      expect(calls.find((c) => c.path === '/api/v1/appointments')?.body).toEqual({
        doctorId: 'd2',
        patientId: 'p1',
        startTime: '2026-03-02T04:10:00Z',
        source: 'walk_in',
        triageResultId: 't9',
        emergencyJustification: 'triage',
      }),
    )
  })

  it('does not offer triage authorization unless the effective urgency is emergency', async () => {
    open(
      api(
        { doctor: [], specialty: [], emergency: [EVE_EMERGENCY] },
        {
          'POST /api/v1/patients/p1/triage': () => ({ status: 201, body: triageResult('routine') }),
        },
      ),
    )

    await toEmergencyConfirm()

    const authorization = screen.getByLabelText('Authorization')
    const options = within(authorization)
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(options).toEqual(['Front-desk judgment'])
    expect(screen.getByLabelText('Reason for using emergency capacity')).toBeInTheDocument()
  })
})
