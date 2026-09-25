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
const slot = (doctorId: string, start: string, end: string) => ({
  doctorId,
  specialtyId: 's1',
  startTime: start,
  endTime: end,
  isEmergency: false,
})
// 03:30Z is 09:00 in Asia/Kolkata (the clinic zone), not in the test's browser zone.
const D1_SLOTS = [
  slot('d1', '2026-03-02T03:30:00Z', '2026-03-02T03:50:00Z'),
  slot('d1', '2026-03-02T03:50:00Z', '2026-03-02T04:10:00Z'),
]
const D2_SLOTS = [slot('d2', '2026-03-02T03:30:00Z', '2026-03-02T03:50:00Z')]
const ASHA = {
  id: 'p1',
  name: 'Asha Rao',
  phone: '+919876543210',
  dob: null,
  email: null,
  createdAt: '2026-03-01T00:00:00Z',
}
const KIRAN = { ...ASHA, id: 'p2', name: 'Kiran Rao' }
const BOOKED = {
  id: 'a1',
  doctorId: 'd1',
  patientId: 'p1',
  startTime: '2026-03-02T03:30:00Z',
  endTime: '2026-03-02T03:50:00Z',
  status: 'booked',
  source: 'scheduled',
  isEmergencySlot: false,
  reportedSymptoms: 'cough',
  createdAt: '2026-03-01T00:00:00Z',
}

function api(user: typeof ADMIN, extra: Handlers = {}) {
  return {
    'GET /api/v1/auth/me': () => ({ body: user }),
    'GET /api/v1/doctors': () => ({ body: [DR_DAN, DR_EVE] }),
    'GET /api/v1/specialties': () => ({ body: SPECIALTIES }),
    'GET /api/v1/clinic-settings': () => ({ body: SETTINGS }),
    'GET /api/v1/slots': ({ url }) => {
      if (url.searchParams.get('specialtyId')) return { body: [...D1_SLOTS, ...D2_SLOTS] }
      return { body: url.searchParams.get('doctorId') === 'd1' ? D1_SLOTS : [] }
    },
    'GET /api/v1/patients': ({ url }) => ({
      body: {
        items: url.searchParams.get('phone') ? [ASHA, KIRAN] : [],
        page: 1,
        pageSize: 20,
        total: 2,
      },
    }),
    'GET /api/v1/appointments/a1': () => ({ body: BOOKED }),
    'GET /api/v1/patients/p1': () => ({ body: ASHA }),
    'GET /api/v1/patients/p1/triage': () => ({ body: [] }),
    ...extra,
  } satisfies Handlers
}

const open = (handlers: Handlers) => renderApp(handlers, { path: '/book', token: 't' })

async function searchDoctor(doctor = 'd1') {
  await userEvent.type(await screen.findByLabelText('Date'), '2026-03-02')
  await userEvent.selectOptions(await screen.findByLabelText('Doctor'), doctor)
  await userEvent.click(screen.getByRole('button', { name: 'Find slots' }))
}

async function pickSlotAndPatient() {
  await searchDoctor()
  const [first] = await screen.findAllByRole('button', { name: '09:00' })
  await userEvent.click(first)
  await userEvent.type(await screen.findByLabelText('Patient phone'), '98765 43210')
  await userEvent.click(screen.getByRole('button', { name: 'Find patient' }))
  await userEvent.click(await screen.findByRole('radio', { name: /Asha Rao/ }))
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
}

describe('Slot search', () => {
  it('searches one doctor and shows times in the clinic time zone', async () => {
    const { calls } = open(api(ADMIN))

    await searchDoctor('d1')

    expect(await screen.findByRole('button', { name: '09:00' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '09:20' })).toBeInTheDocument()
    const request = calls.find((c) => c.path.startsWith('/api/v1/slots'))!
    expect(request.path).toContain('doctorId=d1')
    expect(request.path).toContain('date=2026-03-02')
    expect(request.path).not.toContain('includeEmergency') // emergency slots are never offered here
  })

  it('a specialty search lists every doctor as a choice and selects nothing', async () => {
    const { calls } = open(api(ADMIN))

    await userEvent.click(await screen.findByLabelText('Any doctor in a specialty'))
    await userEvent.type(screen.getByLabelText('Date'), '2026-03-02')
    await userEvent.selectOptions(screen.getByLabelText('Specialty'), 's1')
    await userEvent.click(screen.getByRole('button', { name: 'Find slots' }))

    const dan = (await screen.findByRole('heading', { name: 'Dr Dan' })).closest('section')!
    const eve = screen.getByRole('heading', { name: 'Dr Eve' }).closest('section')!
    expect(within(dan).getAllByRole('button')).toHaveLength(2)
    expect(within(eve).getAllByRole('button')).toHaveLength(1)
    expect(screen.queryByRole('heading', { name: 'Choose patient' })).not.toBeInTheDocument()
    expect(calls.find((c) => c.path.startsWith('/api/v1/slots'))!.path).toContain('specialtyId=s1')
  })

  it('says so when there are no open slots', async () => {
    open(api(ADMIN))

    await searchDoctor('d2')

    expect(await screen.findByText('No open slots for that day.')).toBeInTheDocument()
  })

  it('lets a doctor search only their own slots', async () => {
    open(api(DOCTOR))

    const select = await screen.findByLabelText('Doctor')
    await within(select).findByRole('option', { name: 'Dr Dan' })
    const options = within(select)
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(options.join(' ')).not.toContain('Dr Eve')
    expect(screen.queryByLabelText('Any doctor in a specialty')).not.toBeInTheDocument()
  })
})

describe('Booking flow', () => {
  it('books a slot for a patient chosen among those sharing a phone number', async () => {
    const { calls } = open(
      api(ADMIN, { 'POST /api/v1/appointments': () => ({ status: 201, body: BOOKED }) }),
    )

    await searchDoctor()
    await userEvent.click((await screen.findAllByRole('button', { name: '09:00' }))[0])
    expect(await screen.findByRole('heading', { name: 'Choose patient' })).toBeInTheDocument()
    expect(screen.getByText(/Dr Dan/)).toBeInTheDocument()
    expect(screen.getByText(/Mon 2 Mar 2026, 09:00/)).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText('Patient phone'), '98765 43210')
    await userEvent.click(screen.getByRole('button', { name: 'Find patient' }))
    expect(await screen.findByRole('radio', { name: /Kiran Rao/ })).toBeInTheDocument() // both shown
    await userEvent.click(screen.getByRole('radio', { name: /Asha Rao/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))

    await userEvent.type(await screen.findByLabelText('Reported symptoms (optional)'), 'cough')
    await userEvent.click(screen.getByRole('button', { name: 'Confirm booking' }))

    expect(await screen.findByRole('heading', { name: 'Appointment' })).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      doctorId: 'd1',
      patientId: 'p1',
      startTime: '2026-03-02T03:30:00Z',
      reportedSymptoms: 'cough',
    })
  })

  it('cannot continue without choosing a patient', async () => {
    open(api(ADMIN))

    await searchDoctor()
    await userEvent.click((await screen.findAllByRole('button', { name: '09:00' }))[0])

    expect(await screen.findByRole('button', { name: 'Continue' })).toBeDisabled()
  })

  it('shows the earlier results straight away when going back to the slots', async () => {
    open(api(ADMIN))

    await searchDoctor()
    await userEvent.click((await screen.findAllByRole('button', { name: '09:00' }))[0])
    await userEvent.click(await screen.findByRole('button', { name: 'Back to slots' }))

    expect(await screen.findByRole('button', { name: '09:20' })).toBeInTheDocument()
    expect(screen.queryByText('No open slots for that day.')).not.toBeInTheDocument()
  })

  it('reports a slot that was just taken and offers to refresh the slots', async () => {
    const { calls } = open(
      api(ADMIN, {
        'POST /api/v1/appointments': () => ({
          status: 409,
          body: { code: 'SLOT_ALREADY_BOOKED', message: 'raw' },
        }),
      }),
    )
    await pickSlotAndPatient()
    await userEvent.click(await screen.findByRole('button', { name: 'Confirm booking' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(ERROR_MESSAGES.SLOT_ALREADY_BOOKED)
    const before = calls.filter((c) => c.path.startsWith('/api/v1/slots')).length
    await userEvent.click(screen.getByRole('button', { name: 'Refresh slots' }))

    expect(await screen.findByRole('button', { name: '09:20' })).toBeInTheDocument()
    await vi.waitFor(() =>
      expect(calls.filter((c) => c.path.startsWith('/api/v1/slots')).length).toBeGreaterThan(
        before,
      ),
    )
  })

  it('shows the patient-specific and invalid-slot messages distinctly', async () => {
    const patientClash = open(
      api(ADMIN, {
        'POST /api/v1/appointments': () => ({
          status: 409,
          body: { code: 'PATIENT_ALREADY_BOOKED', message: 'raw' },
        }),
      }),
    )
    await pickSlotAndPatient()
    await userEvent.click(await screen.findByRole('button', { name: 'Confirm booking' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      ERROR_MESSAGES.PATIENT_ALREADY_BOOKED,
    )
    expect(screen.queryByRole('button', { name: 'Refresh slots' })).not.toBeInTheDocument()
    patientClash.unmount()

    open(
      api(ADMIN, {
        'POST /api/v1/appointments': () => ({
          status: 422,
          body: { code: 'INVALID_SLOT', message: 'raw' },
        }),
      }),
    )
    await pickSlotAndPatient()
    await userEvent.click(await screen.findByRole('button', { name: 'Confirm booking' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(ERROR_MESSAGES.INVALID_SLOT)
    expect(screen.getByRole('button', { name: 'Refresh slots' })).toBeInTheDocument()
  })

  it('attaches a triage result run during booking to the appointment', async () => {
    const { calls } = open(
      api(ADMIN, {
        'POST /api/v1/patients/p1/triage': () => ({
          status: 201,
          body: {
            id: 't1',
            patientId: 'p1',
            reportedSymptoms: 'cough',
            urgency: 'routine',
            effectiveUrgency: 'routine',
            suggestedSpecialtyId: 's1',
            confidenceScore: 0.8,
            source: 'model',
            disclaimer: 'AI suggestion only.',
            createdAt: '2026-03-01T12:00:00Z',
          },
        }),
        'POST /api/v1/appointments': () => ({ status: 201, body: BOOKED }),
      }),
    )
    await pickSlotAndPatient()

    await userEvent.type(await screen.findByLabelText('Symptoms for triage'), 'cough')
    await userEvent.click(screen.getByRole('button', { name: 'Run triage' }))
    expect(await screen.findByText('AI suggestion only.')).toBeInTheDocument()
    // Running triage must not submit the booking form it sits next to.
    expect(calls.some((c) => c.method === 'POST' && c.path === '/api/v1/appointments')).toBe(false)
    await userEvent.click(screen.getByRole('button', { name: 'Confirm booking' }))

    await vi.waitFor(() =>
      expect(calls.find((c) => c.path === '/api/v1/appointments')?.body).toMatchObject({
        triageResultId: 't1',
      }),
    )
  })
})
