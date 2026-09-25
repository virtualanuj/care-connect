import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ERROR_MESSAGES } from '../../api/errorMessages'
import { tokenStore } from '../../auth/tokenStore'
import { mockFetch, type Handlers } from '../../test/renderApp'
import PreVisitSummaryPanel from './PreVisitSummaryPanel'
import VisitNoteEditor from './VisitNoteEditor'
import type { PreVisitSummary, VisitNote } from './visitNotesApi'

afterEach(() => {
  tokenStore.clear()
  vi.unstubAllGlobals()
})

const AI_DISCLAIMER = 'AI-generated text. Review before relying on it.'
const notFound = { status: 404, body: { code: 'NOT_FOUND', message: 'none' } }
const summary = (over: Partial<PreVisitSummary> = {}): PreVisitSummary => ({
  appointmentId: 'a1',
  summary: 'Week-long cough; penicillin allergy.',
  disclaimer: AI_DISCLAIMER,
  stale: false,
  generatedAt: '2026-03-01T12:00:00Z',
  ...over,
})
const note = (over: Partial<VisitNote> = {}): VisitNote => ({
  id: 'n1',
  appointmentId: 'a1',
  doctorNotes: 'Cough for a week.',
  aiDraftSummary: null,
  aiDraftDisclaimer: null,
  finalSummary: null,
  finalizedBy: null,
  finalizedAt: null,
  locked: false,
  createdAt: '2026-03-02T09:00:00Z',
  updatedAt: '2026-03-02T09:00:00Z',
  ...over,
})

function renderWith(ui: React.ReactElement, handlers: Handlers) {
  const mocked = mockFetch(handlers)
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
  return mocked
}

describe('PreVisitSummaryPanel', () => {
  it('offers to generate when none is stored and shows the result with its disclaimer', async () => {
    const { calls } = renderWith(<PreVisitSummaryPanel appointmentId="a1" />, {
      'GET /api/v1/appointments/a1/summary': () => notFound,
      'POST /api/v1/appointments/a1/summary': () => ({ body: summary() }),
    })

    expect(await screen.findByText(/no pre-visit summary yet/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Generate summary' }))

    expect(await screen.findByText('Week-long cough; penicillin allergy.')).toBeInTheDocument()
    expect(screen.getByText(AI_DISCLAIMER)).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST')).toBe(true)
    expect(screen.queryByText(/out of date/i)).not.toBeInTheDocument()
  })

  it('flags a stale summary and refreshes it on request', async () => {
    let current = summary({ stale: true })
    const { calls } = renderWith(<PreVisitSummaryPanel appointmentId="a1" />, {
      'GET /api/v1/appointments/a1/summary': () => ({ body: current }),
      'POST /api/v1/appointments/a1/summary': () => {
        current = summary({ summary: 'Updated summary.', stale: false })
        return { body: current }
      },
    })

    expect(await screen.findByText(/out of date/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Refresh summary' }))

    expect(await screen.findByText('Updated summary.')).toBeInTheDocument()
    expect(screen.queryByText(/out of date/i)).not.toBeInTheDocument()
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1)
  })

  it('says the AI is unavailable without hiding the panel', async () => {
    renderWith(<PreVisitSummaryPanel appointmentId="a1" />, {
      'GET /api/v1/appointments/a1/summary': () => notFound,
      'POST /api/v1/appointments/a1/summary': () => ({
        status: 503,
        body: { code: 'AI_SERVICE_UNAVAILABLE', message: 'down' },
      }),
    })

    await userEvent.click(await screen.findByRole('button', { name: 'Generate summary' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      ERROR_MESSAGES.AI_SERVICE_UNAVAILABLE,
    )
    expect(screen.getByRole('button', { name: 'Generate summary' })).toBeEnabled()
  })
})

describe('VisitNoteEditor', () => {
  const NOTE_URL = 'GET /api/v1/appointments/a1/visit-note'

  it('is not offered before the consultation has started', () => {
    renderWith(<VisitNoteEditor appointmentId="a1" status="checked_in" canFinalize />, {})

    expect(screen.getByText(/once the consultation has started/i)).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('autosaves the notes when the field loses focus, and only when they changed', async () => {
    const { calls } = renderWith(
      <VisitNoteEditor appointmentId="a1" status="in_consultation" canFinalize />,
      {
        [NOTE_URL]: () => ({ body: note() }),
        'PUT /api/v1/appointments/a1/visit-note': ({ body }) => ({
          body: note({ doctorNotes: (body as { doctorNotes: string }).doctorNotes }),
        }),
      },
    )
    const field = await screen.findByLabelText('Visit notes')
    await screen.findByDisplayValue('Cough for a week.')

    await userEvent.click(field)
    await userEvent.tab() // unchanged: no save
    expect(calls.filter((c) => c.method === 'PUT')).toHaveLength(0)

    await userEvent.type(field, ' Chest clear.')
    await userEvent.tab()

    expect(await screen.findByText('Saved')).toBeInTheDocument()
    const puts = calls.filter((c) => c.method === 'PUT')
    expect(puts).toHaveLength(1)
    expect(puts[0]?.body).toEqual({ doctorNotes: 'Cough for a week. Chest clear.' })
  })

  it('creates the first note from an empty editor', async () => {
    const { calls } = renderWith(
      <VisitNoteEditor appointmentId="a1" status="in_consultation" canFinalize />,
      {
        [NOTE_URL]: () => notFound,
        'PUT /api/v1/appointments/a1/visit-note': () => ({ body: note({ doctorNotes: 'Fever.' }) }),
      },
    )

    await userEvent.type(await screen.findByLabelText('Visit notes'), 'Fever.')
    await userEvent.tab()

    expect(await screen.findByText('Saved')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({ doctorNotes: 'Fever.' })
  })

  it('shows a save error and keeps what was typed', async () => {
    renderWith(<VisitNoteEditor appointmentId="a1" status="in_consultation" canFinalize />, {
      [NOTE_URL]: () => notFound,
      'PUT /api/v1/appointments/a1/visit-note': () => ({
        status: 409,
        body: { code: 'VISIT_NOTE_LOCKED', message: 'locked' },
      }),
    })

    await userEvent.type(await screen.findByLabelText('Visit notes'), 'Fever.')
    await userEvent.tab()

    expect(await screen.findByRole('alert')).toHaveTextContent(ERROR_MESSAGES.VISIT_NOTE_LOCKED)
    expect(screen.getByLabelText('Visit notes')).toHaveValue('Fever.')
  })

  it('drafts with AI only after notes exist, shows the draft with its disclaimer, and can copy it', async () => {
    let current = note()
    const { calls } = renderWith(
      <VisitNoteEditor appointmentId="a1" status="in_consultation" canFinalize />,
      {
        [NOTE_URL]: () => ({ body: current }),
        'POST /api/v1/appointments/a1/visit-note/draft': () => {
          current = note({
            aiDraftSummary: 'Draft: viral cough.',
            aiDraftDisclaimer: AI_DISCLAIMER,
          })
          return { body: current }
        },
      },
    )
    await screen.findByDisplayValue('Cough for a week.')

    await userEvent.click(screen.getByRole('button', { name: 'Generate AI draft' }))

    expect(await screen.findByText('Draft: viral cough.')).toBeInTheDocument()
    expect(screen.getByText(AI_DISCLAIMER)).toBeInTheDocument()
    expect(screen.getByLabelText('Final summary')).toHaveValue('') // never auto-filled
    await userEvent.click(screen.getByRole('button', { name: 'Use draft as final summary' }))
    expect(screen.getByLabelText('Final summary')).toHaveValue('Draft: viral cough.')
    expect(calls.some((c) => c.path.endsWith('/visit-note/finalize'))).toBe(false)
  })

  it('cannot draft until some notes are saved', async () => {
    renderWith(<VisitNoteEditor appointmentId="a1" status="in_consultation" canFinalize />, {
      [NOTE_URL]: () => notFound,
    })

    expect(await screen.findByRole('button', { name: 'Generate AI draft' })).toBeDisabled()
  })

  it('finalizes with the doctor-written summary and then locks the note', async () => {
    let current = note({ aiDraftSummary: 'Draft.', aiDraftDisclaimer: AI_DISCLAIMER })
    const { calls } = renderWith(
      <VisitNoteEditor appointmentId="a1" status="in_consultation" canFinalize />,
      {
        [NOTE_URL]: () => ({ body: current }),
        'POST /api/v1/appointments/a1/visit-note/finalize': ({ body }) => {
          current = note({
            finalSummary: (body as { finalSummary: string }).finalSummary,
            finalizedBy: 'u1',
            finalizedAt: '2026-03-02T09:30:00Z',
            locked: true,
          })
          return { body: current }
        },
      },
    )
    await screen.findByDisplayValue('Cough for a week.')
    await userEvent.type(screen.getByLabelText('Final summary'), 'Viral cough.')

    await userEvent.click(screen.getByRole('button', { name: 'Finalize summary' }))

    expect(await screen.findByText(/finalized/i)).toBeInTheDocument()
    expect(calls.find((c) => c.path.endsWith('/finalize'))?.body).toEqual({
      finalSummary: 'Viral cough.',
    })
    expect(screen.getByText('Viral cough.')).toBeInTheDocument()
    expect(screen.getByLabelText('Visit notes')).toHaveAttribute('readonly')
    expect(screen.queryByRole('button', { name: 'Finalize summary' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Generate AI draft' })).not.toBeInTheDocument()
  })

  it('does not offer finalize to front-desk', async () => {
    renderWith(
      <VisitNoteEditor appointmentId="a1" status="in_consultation" canFinalize={false} />,
      { [NOTE_URL]: () => ({ body: note() }) },
    )

    await screen.findByDisplayValue('Cough for a week.')

    expect(screen.queryByRole('button', { name: 'Finalize summary' })).not.toBeInTheDocument()
    expect(screen.getByText(/only the appointment's doctor can finalize/i)).toBeInTheDocument()
  })

  it('will not finalize an empty summary', async () => {
    const { calls } = renderWith(
      <VisitNoteEditor appointmentId="a1" status="in_consultation" canFinalize />,
      { [NOTE_URL]: () => ({ body: note() }) },
    )
    await screen.findByDisplayValue('Cough for a week.')

    await userEvent.click(screen.getByRole('button', { name: 'Finalize summary' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/write the final summary/i)
    expect(calls.some((c) => c.path.endsWith('/finalize'))).toBe(false)
  })
})
