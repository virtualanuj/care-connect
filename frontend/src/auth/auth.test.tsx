import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ERROR_MESSAGES } from '../api/errorMessages'
import { ADMIN, DOCTOR, renderApp, type Handlers } from '../test/renderApp'
import { tokenStore } from './tokenStore'

const loginOk = (role: string) => ({
  'POST /api/v1/auth/login': () => ({
    body: { accessToken: 'tok-1', tokenType: 'bearer', expiresIn: 1800, role },
  }),
})

afterEach(() => {
  tokenStore.clear()
  vi.unstubAllGlobals()
})

async function signIn(email = 'a@clinic.test', password = 'correct horse battery') {
  await userEvent.type(await screen.findByLabelText('Email'), email)
  await userEvent.type(screen.getByLabelText('Password'), password)
  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
}

describe('authentication', () => {
  it('redirects an unauthenticated visitor to the login page', async () => {
    renderApp({}, { path: '/' })

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('shows a friendly message for wrong credentials and stores no token', async () => {
    renderApp(
      {
        'POST /api/v1/auth/login': () => ({
          status: 401,
          body: { code: 'INVALID_CREDENTIALS', message: 'raw' },
        }),
      },
      { path: '/login' },
    )

    await signIn()

    expect(await screen.findByRole('alert')).toHaveTextContent(ERROR_MESSAGES.INVALID_CREDENTIALS)
    expect(tokenStore.get()).toBeNull()
  })

  it('shows the rate-limit message after too many attempts', async () => {
    renderApp(
      {
        'POST /api/v1/auth/login': () => ({
          status: 429,
          body: { code: 'RATE_LIMITED', message: 'raw' },
        }),
      },
      { path: '/login' },
    )

    await signIn()

    expect(await screen.findByRole('alert')).toHaveTextContent(ERROR_MESSAGES.RATE_LIMITED)
  })

  it('signs in, keeps the token, loads the user and shows the app', async () => {
    const { calls } = renderApp(
      { ...loginOk('front_desk_admin'), 'GET /api/v1/auth/me': () => ({ body: ADMIN }) },
      { path: '/login' },
    )

    await signIn('admin@clinic.test')

    expect(await screen.findByRole('heading', { name: 'Welcome' })).toBeInTheDocument()
    expect(tokenStore.get()).toBe('tok-1')
    expect(screen.getByText('Ada Admin')).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/api/v1/auth/me')?.headers.Authorization).toBe(
      'Bearer tok-1',
    )
  })

  it('restores the session from a stored token on load', async () => {
    renderApp({ 'GET /api/v1/auth/me': () => ({ body: DOCTOR }) }, { path: '/', token: 'saved' })

    expect(await screen.findByText('Dan Doctor')).toBeInTheDocument()
  })

  it('logs out: clears the token and returns to the login page', async () => {
    renderApp({ 'GET /api/v1/auth/me': () => ({ body: DOCTOR }) }, { path: '/', token: 'saved' })

    await userEvent.click(await screen.findByRole('button', { name: 'Sign out' }))

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(tokenStore.get()).toBeNull()
  })

  it('sends the user back to login when the API says the session expired (401)', async () => {
    const handlers: Handlers = {
      'GET /api/v1/auth/me': () => ({
        status: 401,
        body: { code: 'UNAUTHENTICATED', message: 'raw' },
      }),
    }
    renderApp(handlers, { path: '/', token: 'expired' })

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    await waitFor(() => expect(tokenStore.get()).toBeNull())
  })
})

describe('authorization in the UI', () => {
  it('shows Users navigation to front-desk but not to doctors', async () => {
    const first = renderApp(
      { 'GET /api/v1/auth/me': () => ({ body: ADMIN }) },
      { path: '/', token: 't' },
    )
    expect(await screen.findByRole('link', { name: 'Users' })).toBeInTheDocument()
    first.unmount()

    renderApp({ 'GET /api/v1/auth/me': () => ({ body: DOCTOR }) }, { path: '/', token: 't' })
    await screen.findByText('Dan Doctor')
    expect(screen.queryByRole('link', { name: 'Users' })).not.toBeInTheDocument()
  })

  it('shows a permission page when a doctor opens /users', async () => {
    renderApp({ 'GET /api/v1/auth/me': () => ({ body: DOCTOR }) }, { path: '/users', token: 't' })

    expect(await screen.findByRole('heading', { name: 'Not permitted' })).toBeInTheDocument()
  })
})
