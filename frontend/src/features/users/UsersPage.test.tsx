import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ERROR_MESSAGES } from '../../api/errorMessages'
import { tokenStore } from '../../auth/tokenStore'
import { ADMIN, DOCTOR, renderApp, type Handlers } from '../../test/renderApp'

afterEach(() => {
  tokenStore.clear()
  vi.unstubAllGlobals()
})

function usersApi(initial = [ADMIN, DOCTOR], total = initial.length, extra: Handlers = {}) {
  const users = [...initial]
  const handlers: Handlers = {
    'GET /api/v1/auth/me': () => ({ body: ADMIN }),
    'GET /api/v1/users': ({ url }) => ({
      body: {
        items: users,
        page: Number(url.searchParams.get('page') ?? 1),
        pageSize: 10,
        total,
      },
    }),
    ...extra,
  }
  return { users, handlers }
}

const openUsers = (handlers: Handlers) => renderApp(handlers, { path: '/users', token: 't' })

describe('Users page', () => {
  it('lists users with name, email, role and status', async () => {
    openUsers(usersApi().handlers)

    const row = (await screen.findByText('doc@clinic.test')).closest('tr')!
    expect(within(row).getByText('Dan Doctor')).toBeInTheDocument()
    expect(within(row).getByText('doctor')).toBeInTheDocument()
    expect(within(row).getByText('Active')).toBeInTheDocument()
  })

  it('paginates: shows the page count and requests the next page', async () => {
    const { calls } = openUsers(usersApi([ADMIN, DOCTOR], 25).handlers)

    expect(await screen.findByText('Page 1 of 3')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByText('Page 2 of 3')).toBeInTheDocument()
    expect(calls.some((c) => c.path === '/api/v1/users?page=2&pageSize=10')).toBe(true)
  })

  it('creates a user through the dialog and refreshes the list', async () => {
    const created = { ...DOCTOR, id: 'u-new', email: 'new@clinic.test', name: 'New Doc' }
    const { users, handlers } = usersApi([ADMIN], 1, {
      'POST /api/v1/users': ({ body }) => {
        users.push(created)
        return { status: 201, body: { ...created, ...(body as object) } }
      },
    })
    const { calls } = openUsers(handlers)

    await userEvent.click(await screen.findByRole('button', { name: 'New user' }))
    const dialog = screen.getByRole('dialog', { name: 'New user' })
    await userEvent.type(within(dialog).getByLabelText('Email'), 'new@clinic.test')
    await userEvent.type(within(dialog).getByLabelText('Name'), 'New Doc')
    await userEvent.selectOptions(within(dialog).getByLabelText('Role'), 'doctor')
    await userEvent.type(within(dialog).getByLabelText('Password'), 'a long enough passphrase')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }))

    expect(await screen.findByText('new@clinic.test')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST' && c.path === '/api/v1/users')?.body).toEqual({
      email: 'new@clinic.test',
      name: 'New Doc',
      role: 'doctor',
      password: 'a long enough passphrase',
    })
  })

  it('blocks a too-short password before calling the API', async () => {
    const { calls } = openUsers(usersApi().handlers)

    await userEvent.click(await screen.findByRole('button', { name: 'New user' }))
    const dialog = screen.getByRole('dialog', { name: 'New user' })
    await userEvent.type(within(dialog).getByLabelText('Email'), 'x@clinic.test')
    await userEvent.type(within(dialog).getByLabelText('Name'), 'X')
    await userEvent.type(within(dialog).getByLabelText('Password'), 'short')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }))

    expect(within(dialog).getByRole('alert')).toHaveTextContent('at least 12 characters')
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('shows the duplicate-email message from the API and keeps the dialog open', async () => {
    const { handlers } = usersApi([ADMIN], 1, {
      'POST /api/v1/users': () => ({
        status: 409,
        body: { code: 'USER_ALREADY_EXISTS', message: 'raw' },
      }),
    })
    openUsers(handlers)

    await userEvent.click(await screen.findByRole('button', { name: 'New user' }))
    const dialog = screen.getByRole('dialog', { name: 'New user' })
    await userEvent.type(within(dialog).getByLabelText('Email'), 'dup@clinic.test')
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Dup')
    await userEvent.type(within(dialog).getByLabelText('Password'), 'a long enough passphrase')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      ERROR_MESSAGES.USER_ALREADY_EXISTS,
    )
  })

  it('deactivates another user and offers no way to deactivate yourself', async () => {
    const { users, handlers } = usersApi([ADMIN, DOCTOR], 2, {
      [`PATCH /api/v1/users/${DOCTOR.id}`]: ({ body }) => {
        users[1] = { ...DOCTOR, ...(body as object) }
        return { body: users[1] }
      },
    })
    const { calls } = openUsers(handlers)

    const doctorRow = (await screen.findByText('doc@clinic.test')).closest('tr')!
    const adminRow = screen.getByText('admin@clinic.test').closest('tr')!
    expect(within(adminRow).getByRole('button', { name: 'Deactivate' })).toBeDisabled()

    await userEvent.click(within(doctorRow).getByRole('button', { name: 'Deactivate' }))

    expect(await screen.findByText('Inactive')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ active: false })
  })

  it('edits name and role', async () => {
    const { users, handlers } = usersApi([ADMIN, DOCTOR], 2, {
      [`PATCH /api/v1/users/${DOCTOR.id}`]: ({ body }) => {
        users[1] = { ...DOCTOR, ...(body as object) }
        return { body: users[1] }
      },
    })
    const { calls } = openUsers(handlers)

    const doctorRow = (await screen.findByText('doc@clinic.test')).closest('tr')!
    await userEvent.click(within(doctorRow).getByRole('button', { name: 'Edit' }))
    const dialog = screen.getByRole('dialog', { name: 'Edit user' })
    const name = within(dialog).getByLabelText('Name')
    await userEvent.clear(name)
    await userEvent.type(name, 'Dr Renamed')
    await userEvent.selectOptions(within(dialog).getByLabelText('Role'), 'front_desk_admin')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Dr Renamed')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({
      name: 'Dr Renamed',
      role: 'front_desk_admin',
    })
  })

  it('resets a password with client-side length validation', async () => {
    const { handlers } = usersApi([ADMIN, DOCTOR], 2, {
      [`POST /api/v1/users/${DOCTOR.id}/reset-password`]: () => ({ status: 204 }),
    })
    const { calls } = openUsers(handlers)

    const doctorRow = (await screen.findByText('doc@clinic.test')).closest('tr')!
    await userEvent.click(within(doctorRow).getByRole('button', { name: 'Reset password' }))
    const dialog = screen.getByRole('dialog', { name: 'Reset password' })
    await userEvent.type(within(dialog).getByLabelText('New password'), 'tiny')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Reset' }))
    expect(within(dialog).getByRole('alert')).toHaveTextContent('at least 12 characters')

    await userEvent.clear(within(dialog).getByLabelText('New password'))
    await userEvent.type(within(dialog).getByLabelText('New password'), 'a brand new passphrase')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Reset' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(calls.find((c) => c.path.endsWith('/reset-password'))?.body).toEqual({
      newPassword: 'a brand new passphrase',
    })
  })
})
