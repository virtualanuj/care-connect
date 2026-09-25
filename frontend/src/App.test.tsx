import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { DOCTOR, renderApp } from './test/renderApp'

const signedInAs = (path: string) =>
  renderApp({ 'GET /api/v1/auth/me': () => ({ body: DOCTOR }) }, { path, token: 't' })

describe('App shell', () => {
  it('renders the layout with a brand, navigation and the home page', async () => {
    signedInAs('/')

    expect(await screen.findByRole('heading', { name: 'Welcome' })).toBeInTheDocument()
    expect(screen.getByText('CareConnect')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
  })

  it('shows a not-found page for unknown routes', async () => {
    signedInAs('/does-not-exist')

    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })
})
