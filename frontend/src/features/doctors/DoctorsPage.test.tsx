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

const SPECIALTIES = [
  { id: 's1', name: 'General Medicine', defaultSlotLengthMinutes: 20 },
  { id: 's2', name: 'Cardiology', defaultSlotLengthMinutes: 30 },
]
const DR_DAN = {
  id: 'd1',
  userId: DOCTOR.id,
  name: 'Dr Dan',
  specialtyId: 's1',
  slotLengthMinutes: 20,
  active: true,
}
const DR_OTHER = { ...DR_DAN, id: 'd2', userId: 'u-other', name: 'Dr Other', specialtyId: 's2' }
const USERS = {
  items: [
    ADMIN,
    DOCTOR,
    { id: 'u-other', email: 'other@clinic.test', name: 'Other', role: 'doctor', active: true },
    { id: 'u-new', email: 'new@clinic.test', name: 'New Doc', role: 'doctor', active: true },
  ],
  page: 1,
  pageSize: 100,
  total: 4,
}

function api(user: typeof ADMIN, extra: Handlers = {}) {
  return {
    'GET /api/v1/auth/me': () => ({ body: user }),
    'GET /api/v1/doctors': () => ({ body: [DR_DAN, DR_OTHER] }),
    'GET /api/v1/specialties': () => ({ body: SPECIALTIES }),
    'GET /api/v1/users': () => ({ body: USERS }),
    ...extra,
  } satisfies Handlers
}

const open = (handlers: Handlers) => renderApp(handlers, { path: '/doctors', token: 't' })
const rowOf = async (name: string) => (await screen.findByText(name)).closest('tr')!

describe('Doctors page', () => {
  it('lists doctors with their specialty, slot length and status', async () => {
    open(api(ADMIN))

    const row = await rowOf('Dr Other')
    expect(within(row).getByText('Cardiology')).toBeInTheDocument()
    expect(within(row).getByText('20 min')).toBeInTheDocument()
    expect(within(row).getByText('Active')).toBeInTheDocument()
  })

  it('lets a doctor edit only their own row and hides admin actions', async () => {
    open(api(DOCTOR))

    const own = await rowOf('Dr Dan')
    const other = await rowOf('Dr Other')
    expect(within(own).getByRole('button', { name: 'Edit' })).toBeInTheDocument()
    expect(within(other).queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'New doctor' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'New specialty' })).not.toBeInTheDocument()
    expect(within(own).queryByRole('button', { name: 'Deactivate' })).not.toBeInTheDocument()
    expect(within(own).getByRole('link', { name: 'Availability' })).toBeInTheDocument()
  })

  it('creates a doctor from a doctor account that has no profile yet', async () => {
    const { calls } = open(
      api(ADMIN, {
        'POST /api/v1/doctors': () => ({ status: 201, body: { ...DR_DAN, id: 'd3' } }),
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'New doctor' }))
    const dialog = screen.getByRole('dialog', { name: 'New doctor' })
    const accounts = within(dialog).getByLabelText('Doctor account')
    const options = within(accounts)
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(options.join(' ')).toContain('New Doc')
    expect(options.join(' ')).not.toContain('Dan Doctor') // already has a profile
    expect(options.join(' ')).not.toContain('Ada Admin') // not a doctor account

    await userEvent.selectOptions(accounts, 'u-new')
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Dr New')
    await userEvent.selectOptions(within(dialog).getByLabelText('Specialty'), 's2')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }))

    await vi.waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      userId: 'u-new',
      name: 'Dr New',
      specialtyId: 's2',
    })
  })

  it('sends a slot length only when one is entered', async () => {
    const { calls } = open(
      api(ADMIN, { 'POST /api/v1/doctors': () => ({ status: 201, body: DR_DAN }) }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'New doctor' }))
    const dialog = screen.getByRole('dialog', { name: 'New doctor' })
    await userEvent.selectOptions(within(dialog).getByLabelText('Doctor account'), 'u-new')
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Dr New')
    await userEvent.selectOptions(within(dialog).getByLabelText('Specialty'), 's1')
    await userEvent.type(within(dialog).getByLabelText('Slot length (minutes)'), '45')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }))

    await vi.waitFor(() =>
      expect(calls.find((c) => c.method === 'POST')?.body).toMatchObject({ slotLengthMinutes: 45 }),
    )
  })

  it('edits a doctor and sends only the changed fields', async () => {
    const { calls } = open(
      api(ADMIN, {
        'PATCH /api/v1/doctors/d2': () => ({ body: { ...DR_OTHER, name: 'Dr Renamed' } }),
      }),
    )

    await userEvent.click(within(await rowOf('Dr Other')).getByRole('button', { name: 'Edit' }))
    const dialog = screen.getByRole('dialog', { name: 'Edit doctor' })
    const name = within(dialog).getByLabelText('Name')
    await userEvent.clear(name)
    await userEvent.type(name, 'Dr Renamed')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))

    await vi.waitFor(() =>
      expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ name: 'Dr Renamed' }),
    )
  })

  it('explains why a doctor with upcoming appointments cannot be deactivated', async () => {
    open(
      api(ADMIN, {
        'PATCH /api/v1/doctors/d2': () => ({
          status: 409,
          body: { code: 'AVAILABILITY_CONFLICTS_WITH_APPOINTMENTS', message: 'raw' },
        }),
      }),
    )

    await userEvent.click(
      within(await rowOf('Dr Other')).getByRole('button', { name: 'Deactivate' }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(
      ERROR_MESSAGES.AVAILABILITY_CONFLICTS_WITH_APPOINTMENTS,
    )
  })

  it('creates a specialty and reports a duplicate name', async () => {
    const { calls } = open(
      api(ADMIN, {
        'POST /api/v1/specialties': ({ body }) =>
          (body as { name: string }).name === 'Dermatology'
            ? { status: 201, body: { id: 's3', ...(body as object) } }
            : { status: 409, body: { code: 'SPECIALTY_ALREADY_EXISTS', message: 'raw' } },
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'New specialty' }))
    const dialog = screen.getByRole('dialog', { name: 'New specialty' })
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Cardiology')
    await userEvent.type(within(dialog).getByLabelText('Default slot length (minutes)'), '30')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      ERROR_MESSAGES.SPECIALTY_ALREADY_EXISTS,
    )

    const name = within(dialog).getByLabelText('Name')
    await userEvent.clear(name)
    await userEvent.type(name, 'Dermatology')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }))

    await vi.waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(calls.filter((c) => c.method === 'POST').at(-1)?.body).toEqual({
      name: 'Dermatology',
      defaultSlotLengthMinutes: 30,
    })
  })
})
