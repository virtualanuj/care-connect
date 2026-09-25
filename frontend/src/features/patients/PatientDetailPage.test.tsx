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

const PATIENT = {
  id: 'p1',
  name: 'Asha Rao',
  phone: '+919876543210',
  dob: '1990-05-01',
  email: 'asha@example.com',
  createdAt: '2026-03-01T09:00:00Z',
}
const ORIGINAL = {
  id: 'h1',
  patientId: 'p1',
  kind: 'entry',
  amendsEntryId: null,
  description: 'Allergic to penicillin',
  recordedAt: '2026-03-01T09:00:00Z',
  recordedBy: 'u-admin',
}
const AMENDMENT = {
  id: 'h2',
  patientId: 'p1',
  kind: 'amendment',
  amendsEntryId: 'h1',
  description: 'Correction: allergic to amoxicillin, not penicillin',
  recordedAt: '2026-03-02T09:00:00Z',
  recordedBy: 'u-doc',
}

function api(user = ADMIN, extra: Handlers = {}) {
  return {
    'GET /api/v1/auth/me': () => ({ body: user }),
    'GET /api/v1/patients/p1': () => ({ body: PATIENT }),
    'GET /api/v1/patients/p1/medical-history': () => ({ body: [ORIGINAL, AMENDMENT] }),
    ...extra,
  } satisfies Handlers
}

const open = (handlers: Handlers) => renderApp(handlers, { path: '/patients/p1', token: 't' })

describe('Patient detail', () => {
  it('shows the patient details', async () => {
    open(api())

    expect(await screen.findByRole('heading', { name: 'Asha Rao' })).toBeInTheDocument()
    expect(screen.getByText('+919876543210')).toBeInTheDocument()
    expect(screen.getByText('1990-05-01')).toBeInTheDocument()
    expect(screen.getByText('asha@example.com')).toBeInTheDocument()
  })

  it('edits details, sending only changes, and clears an optional field with null', async () => {
    const { calls } = open(
      api(DOCTOR, { 'PATCH /api/v1/patients/p1': () => ({ body: { ...PATIENT, dob: null } }) }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Edit details' }))
    const dialog = screen.getByRole('dialog', { name: 'Edit patient' })
    await userEvent.clear(within(dialog).getByLabelText('Date of birth'))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))

    await vi.waitFor(() =>
      expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ dob: null }),
    )
  })

  it('shows a name collision on edit', async () => {
    open(
      api(ADMIN, {
        'PATCH /api/v1/patients/p1': () => ({
          status: 409,
          body: { code: 'PATIENT_ALREADY_EXISTS', message: 'raw' },
        }),
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Edit details' }))
    const dialog = screen.getByRole('dialog', { name: 'Edit patient' })
    const name = within(dialog).getByLabelText('Name')
    await userEvent.clear(name)
    await userEvent.type(name, 'Kiran Rao')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      ERROR_MESSAGES.PATIENT_ALREADY_EXISTS,
    )
  })
})

describe('Medical history', () => {
  it('lists entries oldest first and links an amendment to what it corrects', async () => {
    open(api())

    const items = await screen.findAllByRole('listitem', { name: /history entry/i })
    expect(items).toHaveLength(2)
    expect(within(items[0]).getByText('Allergic to penicillin')).toBeInTheDocument()
    expect(within(items[1]).getByText(/Correction: allergic to amoxicillin/)).toBeInTheDocument()
    expect(within(items[1]).getByText('Amends: Allergic to penicillin')).toBeInTheDocument()
    expect(within(items[1]).getByText('Amendment')).toBeInTheDocument()
  })

  it('offers no way to edit or delete an entry', async () => {
    open(api())

    await screen.findAllByRole('listitem', { name: /history entry/i })
    expect(
      screen.queryByRole('button', { name: /edit entry|delete|remove/i }),
    ).not.toBeInTheDocument()
  })

  it('adds a new entry', async () => {
    const { calls } = open(
      api(ADMIN, {
        'POST /api/v1/patients/p1/medical-history': () => ({
          status: 201,
          body: { ...ORIGINAL, id: 'h3', description: 'Asthma' },
        }),
      }),
    )

    await userEvent.type(await screen.findByLabelText('New history entry'), 'Asthma')
    await userEvent.click(screen.getByRole('button', { name: 'Add entry' }))

    await vi.waitFor(() =>
      expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ description: 'Asthma' }),
    )
  })

  it('adds an amendment to a specific entry', async () => {
    const { calls } = open(
      api(ADMIN, {
        'POST /api/v1/patients/p1/medical-history': () => ({ status: 201, body: AMENDMENT }),
      }),
    )

    const first = (await screen.findAllByRole('listitem', { name: /history entry/i }))[0]
    await userEvent.click(within(first).getByRole('button', { name: 'Amend' }))
    const dialog = screen.getByRole('dialog', { name: 'Amend history entry' })
    expect(within(dialog).getByText('Allergic to penicillin')).toBeInTheDocument()
    await userEvent.type(within(dialog).getByLabelText('Correction'), 'Actually amoxicillin')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add amendment' }))

    await vi.waitFor(() =>
      expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
        kind: 'amendment',
        amendsEntryId: 'h1',
        description: 'Actually amoxicillin',
      }),
    )
  })
})
