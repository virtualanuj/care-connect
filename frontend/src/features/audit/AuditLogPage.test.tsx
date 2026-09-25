import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { tokenStore } from '../../auth/tokenStore'
import { ADMIN, DOCTOR, renderApp, type Handlers } from '../../test/renderApp'

afterEach(() => {
  tokenStore.clear()
  vi.unstubAllGlobals()
})

const entry = (over: Record<string, unknown> = {}) => ({
  id: 'e1',
  action: 'force_cancel',
  actorId: ADMIN.id,
  targetType: 'appointment',
  targetId: 'a1',
  reason: 'Doctor unwell',
  createdAt: '2026-03-02T03:30:00Z',
  ...over,
})

function auditApi(items = [entry()], total = items.length): Handlers {
  return {
    'GET /api/v1/auth/me': () => ({ body: ADMIN }),
    'GET /api/v1/users': () => ({
      body: { items: [ADMIN, DOCTOR], page: 1, pageSize: 100, total: 2 },
    }),
    'GET /api/v1/clinic-settings': () => ({
      body: {
        cancellationCutoffHours: 2,
        emergencySlotsPerDoctorPerDay: 1,
        followUpMaxDays: 30,
        clinicTimezone: 'Asia/Kolkata',
        defaultTriageSpecialtyId: null,
      },
    }),
    'GET /api/v1/audit-log': ({ url }) => ({
      body: {
        items,
        page: Number(url.searchParams.get('page') ?? 1),
        pageSize: 20,
        total,
      },
    }),
  }
}

describe('Audit log page', () => {
  it('lists entries with a readable action, the actor by name, the target, reason and local time', async () => {
    renderApp(auditApi(), { path: '/audit', token: 't' })

    const row = (await screen.findByText('Doctor unwell')).closest('tr')!
    expect(within(row).getByText('Force cancel')).toBeInTheDocument()
    expect(within(row).getByText(ADMIN.name)).toBeInTheDocument()
    expect(within(row).getByText(/appointment/)).toBeInTheDocument()
    expect(within(row).getByText(/2 Mar 2026, 09:00/)).toBeInTheDocument()
  })

  it('filters by action and returns to the first page', async () => {
    const { calls } = renderApp(auditApi([entry()], 45), { path: '/audit', token: 't' })
    await screen.findByText('Doctor unwell')
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Page 2 of 3')).toBeInTheDocument()

    await userEvent.selectOptions(screen.getByLabelText('Action'), 'Triage override')

    const last = calls.filter((c) => c.path.startsWith('/api/v1/audit-log')).at(-1)!
    expect(last.path).toContain('action=triage_override')
    expect(last.path).toContain('page=1')
  })

  it('pages through the log', async () => {
    const { calls } = renderApp(auditApi([entry()], 45), { path: '/audit', token: 't' })
    expect(await screen.findByText('Page 1 of 3')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()

    await userEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByText('Page 2 of 3')).toBeInTheDocument()
    expect(calls.some((c) => c.path.includes('page=2'))).toBe(true)
  })

  it('shows an empty state', async () => {
    renderApp(auditApi([], 0), { path: '/audit', token: 't' })

    expect(await screen.findByText('No audit entries.')).toBeInTheDocument()
  })

  it('is front-desk only: doctors do not see the link and are redirected away', async () => {
    renderApp(
      { ...auditApi(), 'GET /api/v1/auth/me': () => ({ body: DOCTOR }) },
      { path: '/audit', token: 't' },
    )

    expect(await screen.findByRole('link', { name: 'Queue' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Audit log' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Audit log' })).not.toBeInTheDocument()
  })
})
