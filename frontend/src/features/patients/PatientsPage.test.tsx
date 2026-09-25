import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ERROR_MESSAGES } from '../../api/errorMessages'
import { tokenStore } from '../../auth/tokenStore'
import { ADMIN, renderApp, type Handlers } from '../../test/renderApp'

afterEach(() => {
  tokenStore.clear()
  vi.unstubAllGlobals()
})

const ASHA = {
  id: 'p1',
  name: 'Asha Rao',
  phone: '+919876543210',
  dob: '1990-05-01',
  email: null,
  createdAt: '2026-03-01T09:00:00Z',
}
const KIRAN = { ...ASHA, id: 'p2', name: 'Kiran Rao', dob: null }
const MEERA = { ...ASHA, id: 'p3', name: 'Meera Iyer', phone: '+919123456789' }

function patientsApi(extra: Handlers = {}) {
  const all = [ASHA, KIRAN, MEERA]
  return {
    'GET /api/v1/auth/me': () => ({ body: ADMIN }),
    'GET /api/v1/patients': ({ url }) => {
      const phone = url.searchParams.get('phone')
      const items = phone
        ? all.filter((p) => p.phone.endsWith(phone.replace(/\D/g, '').slice(-10)))
        : all
      return { body: { items, page: 1, pageSize: 20, total: items.length } }
    },
    ...extra,
  } satisfies Handlers
}

const open = (handlers: Handlers, path = '/patients') => renderApp(handlers, { path, token: 't' })

describe('Patients page', () => {
  it('lists patients and searching by phone shows every family member under that number', async () => {
    const { calls } = open(patientsApi())

    expect(await screen.findByText('Meera Iyer')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Phone'), '98765 43210')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))

    expect(await screen.findByText('2 patients found')).toBeInTheDocument()
    expect(screen.getByText('Asha Rao')).toBeInTheDocument()
    expect(screen.getByText('Kiran Rao')).toBeInTheDocument()
    expect(screen.queryByText('Meera Iyer')).not.toBeInTheDocument()
    expect(calls.some((c) => c.path.includes('phone=98765+43210'))).toBe(true)
  })

  it('offers to register a new patient under the searched phone number', async () => {
    const { calls } = open(
      patientsApi({
        'POST /api/v1/patients': ({ body }) => ({
          status: 201,
          body: { ...ASHA, id: 'p9', ...(body as object), name: 'Zara Rao' },
        }),
        'GET /api/v1/patients/p9': () => ({ body: { ...ASHA, id: 'p9', name: 'Zara Rao' } }),
        'GET /api/v1/patients/p9/medical-history': () => ({ body: [] }),
      }),
    )

    await userEvent.type(await screen.findByLabelText('Phone'), '98765 43210')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Register new patient' }))
    const dialog = screen.getByRole('dialog', { name: 'Register patient' })
    expect(within(dialog).getByLabelText('Phone')).toHaveValue('98765 43210')
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Zara Rao')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Register' }))

    expect(await screen.findByRole('heading', { name: 'Zara Rao' })).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      name: 'Zara Rao',
      phone: '98765 43210',
    })
  })

  it('shows the duplicate message inline', async () => {
    open(
      patientsApi({
        'POST /api/v1/patients': () => ({
          status: 409,
          body: { code: 'PATIENT_ALREADY_EXISTS', message: 'raw' },
        }),
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Register new patient' }))
    const dialog = screen.getByRole('dialog', { name: 'Register patient' })
    await userEvent.type(within(dialog).getByLabelText('Name'), 'asha rao')
    await userEvent.type(within(dialog).getByLabelText('Phone'), '9876543210')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Register' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      ERROR_MESSAGES.PATIENT_ALREADY_EXISTS,
    )
    expect(screen.getByRole('dialog', { name: 'Register patient' })).toBeInTheDocument()
  })

  it('reports an invalid phone number returned by the server', async () => {
    open(
      patientsApi({
        'POST /api/v1/patients': () => ({
          status: 400,
          body: { code: 'VALIDATION_ERROR', message: 'raw' },
        }),
      }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Register new patient' }))
    const dialog = screen.getByRole('dialog', { name: 'Register patient' })
    await userEvent.type(within(dialog).getByLabelText('Name'), 'X')
    await userEvent.type(within(dialog).getByLabelText('Phone'), '123')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Register' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      ERROR_MESSAGES.VALIDATION_ERROR,
    )
  })

  it('links each result to the patient detail page', async () => {
    open(
      patientsApi({
        'GET /api/v1/patients/p1': () => ({ body: ASHA }),
        'GET /api/v1/patients/p1/medical-history': () => ({ body: [] }),
      }),
    )

    await userEvent.click(await screen.findByRole('link', { name: 'Asha Rao' }))

    expect(await screen.findByRole('heading', { name: 'Asha Rao' })).toBeInTheDocument()
  })
})
