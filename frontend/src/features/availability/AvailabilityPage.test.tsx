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
const OTHER_DOCTOR = { ...DR_DAN, id: 'd2', userId: 'u-other', name: 'Dr Other' }
const MONDAY_MORNING = {
  id: 'r1',
  doctorId: 'd1',
  dayOfWeek: 'monday',
  startTime: '09:00',
  endTime: '12:00',
}
const HOLIDAY = {
  id: 'e1',
  doctorId: 'd1',
  date: '2026-03-09',
  type: 'unavailable',
  startTime: null,
  endTime: null,
}
const EXTRA = {
  id: 'e2',
  doctorId: 'd1',
  date: '2026-03-10',
  type: 'extra_hours',
  startTime: '13:00',
  endTime: '15:00',
}

function api(user: typeof ADMIN, extra: Handlers = {}, doctor = DR_DAN) {
  return {
    'GET /api/v1/auth/me': () => ({ body: user }),
    [`GET /api/v1/doctors/${doctor.id}`]: () => ({ body: doctor }),
    [`GET /api/v1/doctors/${doctor.id}/availability`]: () => ({ body: [MONDAY_MORNING] }),
    [`GET /api/v1/doctors/${doctor.id}/availability-exceptions`]: () => ({
      body: [HOLIDAY, EXTRA],
    }),
    ...extra,
  } satisfies Handlers
}

const open = (handlers: Handlers, doctorId = 'd1') =>
  renderApp(handlers, { path: `/doctors/${doctorId}/availability`, token: 't' })

describe('Availability editor', () => {
  it('shows the weekly windows per day and the exceptions', async () => {
    open(api(DOCTOR))

    expect(
      await screen.findByRole('heading', { name: 'Availability — Dr Dan' }),
    ).toBeInTheDocument()
    const monday = (await screen.findByText('Monday')).closest('tr')!
    expect(within(monday).getByText('09:00–12:00')).toBeInTheDocument()
    const tuesday = screen.getByText('Tuesday').closest('tr')!
    expect(within(tuesday).getByText('Not working')).toBeInTheDocument()
    expect(screen.getByText('2026-03-09')).toBeInTheDocument()
    expect(screen.getByText('Unavailable all day')).toBeInTheDocument()
    expect(screen.getByText('Extra hours 13:00–15:00')).toBeInTheDocument()
  })

  it('adds working hours', async () => {
    const { calls } = open(
      api(DOCTOR, {
        'POST /api/v1/doctors/d1/availability': ({ body }) => ({
          status: 201,
          body: { id: 'r2', doctorId: 'd1', ...(body as object) },
        }),
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Add hours' }))
    const dialog = screen.getByRole('dialog', { name: 'Add working hours' })
    await userEvent.selectOptions(within(dialog).getByLabelText('Day'), 'tuesday')
    await userEvent.type(within(dialog).getByLabelText('Start'), '10:00')
    await userEvent.type(within(dialog).getByLabelText('End'), '13:30')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add' }))

    await vi.waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      dayOfWeek: 'tuesday',
      startTime: '10:00',
      endTime: '13:30',
    })
  })

  it('blocks a start time that is not before the end time', async () => {
    const { calls } = open(api(DOCTOR))

    await userEvent.click(await screen.findByRole('button', { name: 'Add hours' }))
    const dialog = screen.getByRole('dialog', { name: 'Add working hours' })
    await userEvent.type(within(dialog).getByLabelText('Start'), '12:00')
    await userEvent.type(within(dialog).getByLabelText('End'), '09:00')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add' }))

    expect(within(dialog).getByRole('alert')).toHaveTextContent('Start must be before end')
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('reports overlapping hours from the server', async () => {
    open(
      api(DOCTOR, {
        'POST /api/v1/doctors/d1/availability': () => ({
          status: 409,
          body: { code: 'AVAILABILITY_OVERLAP', message: 'raw' },
        }),
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Add hours' }))
    const dialog = screen.getByRole('dialog', { name: 'Add working hours' })
    await userEvent.type(within(dialog).getByLabelText('Start'), '10:00')
    await userEvent.type(within(dialog).getByLabelText('End'), '11:00')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      ERROR_MESSAGES.AVAILABILITY_OVERLAP,
    )
  })

  it('edits a window and sends only what changed', async () => {
    const { calls } = open(
      api(DOCTOR, {
        'PATCH /api/v1/doctors/d1/availability/r1': () => ({
          body: { ...MONDAY_MORNING, endTime: '13:00' },
        }),
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Edit Monday 09:00–12:00' }))
    const dialog = screen.getByRole('dialog', { name: 'Edit working hours' })
    const end = within(dialog).getByLabelText('End')
    await userEvent.clear(end)
    await userEvent.type(end, '13:00')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))

    await vi.waitFor(() =>
      expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ endTime: '13:00' }),
    )
  })

  it('removes a window, and explains when appointments depend on it', async () => {
    const deleted = open(
      api(DOCTOR, { 'DELETE /api/v1/doctors/d1/availability/r1': () => ({ status: 204 }) }),
    )
    await userEvent.click(await screen.findByRole('button', { name: 'Remove Monday 09:00–12:00' }))
    await vi.waitFor(() => expect(deleted.calls.some((c) => c.method === 'DELETE')).toBe(true))
    deleted.unmount()

    open(
      api(DOCTOR, {
        'DELETE /api/v1/doctors/d1/availability/r1': () => ({
          status: 409,
          body: { code: 'AVAILABILITY_CONFLICTS_WITH_APPOINTMENTS', message: 'raw' },
        }),
      }),
    )
    await userEvent.click(await screen.findByRole('button', { name: 'Remove Monday 09:00–12:00' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      ERROR_MESSAGES.AVAILABILITY_CONFLICTS_WITH_APPOINTMENTS,
    )
  })

  it('adds an all-day unavailable exception without times', async () => {
    const { calls } = open(
      api(DOCTOR, {
        'POST /api/v1/doctors/d1/availability-exceptions': ({ body }) => ({
          status: 201,
          body: { id: 'e3', doctorId: 'd1', startTime: null, endTime: null, ...(body as object) },
        }),
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Add exception' }))
    const dialog = screen.getByRole('dialog', { name: 'Add exception' })
    await userEvent.type(within(dialog).getByLabelText('Date'), '2026-03-16')
    await userEvent.selectOptions(within(dialog).getByLabelText('Type'), 'unavailable')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add' }))

    await vi.waitFor(() =>
      expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
        date: '2026-03-16',
        type: 'unavailable',
      }),
    )
  })

  it('requires times for extra hours and sends them', async () => {
    const { calls } = open(
      api(DOCTOR, {
        'POST /api/v1/doctors/d1/availability-exceptions': () => ({ status: 201, body: EXTRA }),
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Add exception' }))
    const dialog = screen.getByRole('dialog', { name: 'Add exception' })
    await userEvent.type(within(dialog).getByLabelText('Date'), '2026-03-17')
    await userEvent.selectOptions(within(dialog).getByLabelText('Type'), 'extra_hours')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add' }))
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Extra hours need a start and end')
    expect(calls.some((c) => c.method === 'POST')).toBe(false)

    await userEvent.type(within(dialog).getByLabelText('Start'), '14:00')
    await userEvent.type(within(dialog).getByLabelText('End'), '16:00')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add' }))

    await vi.waitFor(() =>
      expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
        date: '2026-03-17',
        type: 'extra_hours',
        startTime: '14:00',
        endTime: '16:00',
      }),
    )
  })

  it('removes an exception', async () => {
    const { calls } = open(
      api(DOCTOR, {
        'DELETE /api/v1/doctors/d1/availability-exceptions/e1': () => ({ status: 204 }),
      }),
    )

    await userEvent.click(
      await screen.findByRole('button', { name: 'Remove exception 2026-03-09' }),
    )

    await vi.waitFor(() => expect(calls.some((c) => c.method === 'DELETE')).toBe(true))
  })

  it('is read-only for a doctor viewing someone else, but front-desk can edit anyone', async () => {
    const first = open(api(DOCTOR, {}, OTHER_DOCTOR), 'd2')
    expect(
      await screen.findByRole('heading', { name: 'Availability — Dr Other' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add hours' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add exception' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Remove/ })).not.toBeInTheDocument()
    first.unmount()

    open(api(ADMIN, {}, OTHER_DOCTOR), 'd2')
    expect(await screen.findByRole('button', { name: 'Add hours' })).toBeInTheDocument()
  })
})
