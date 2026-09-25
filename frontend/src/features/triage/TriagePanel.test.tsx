import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ERROR_MESSAGES } from '../../api/errorMessages'
import { tokenStore } from '../../auth/tokenStore'
import { ToastProvider } from '../../components/Toast'
import { mockFetch, type Handlers } from '../../test/renderApp'
import TriagePanel from './TriagePanel'
import TriageResultCard from './TriageResultCard'
import type { TriageResult } from './triageApi'

afterEach(() => {
  tokenStore.clear()
  vi.unstubAllGlobals()
})

const DISCLAIMER = 'This is an AI-generated suggestion. It is not a diagnosis.'
const SPECIALTIES = [
  { id: 's1', name: 'General Medicine', defaultSlotLengthMinutes: 20 },
  { id: 's2', name: 'Cardiology', defaultSlotLengthMinutes: 30 },
]
const result = (over: Partial<TriageResult> = {}): TriageResult => ({
  id: 't1',
  patientId: 'p1',
  reportedSymptoms: 'cough',
  urgency: 'urgent',
  effectiveUrgency: 'urgent',
  suggestedSpecialtyId: 's2',
  confidenceScore: 0.66,
  source: 'model',
  modelVersion: 'm',
  promptVersion: 'p',
  disclaimer: DISCLAIMER,
  overriddenBy: null,
  overriddenAt: null,
  overriddenUrgency: null,
  overriddenSpecialtyId: null,
  overrideReason: null,
  createdAt: '2026-03-01T12:00:00Z',
  ...over,
})

function renderPanel(handlers: Handlers, onCurrent = vi.fn()) {
  const mocked = mockFetch({
    'GET /api/v1/specialties': () => ({ body: SPECIALTIES }),
    'GET /api/v1/patients/p1/triage': () => ({ body: [] }),
    ...handlers,
  })
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <TriagePanel patientId="p1" onCurrentChange={onCurrent} />
      </ToastProvider>
    </QueryClientProvider>,
  )
  return { ...mocked, onCurrent }
}

describe('TriageResultCard', () => {
  it.each(['emergency', 'urgent', 'routine'] as const)(
    'never shows a %s urgency without the safety disclaimer',
    (urgency) => {
      render(
        <TriageResultCard
          result={result({ urgency, effectiveUrgency: urgency })}
          specialtyName="Cardiology"
        />,
      )

      const card = screen.getByRole('region', { name: 'Triage result' })
      expect(within(card).getByText(urgency, { exact: false })).toBeInTheDocument()
      expect(within(card).getByText(DISCLAIMER)).toBeInTheDocument()
    },
  )

  it('shows the disclaimer after an override too, with original and override side by side', () => {
    render(
      <TriageResultCard
        result={result({
          urgency: 'emergency',
          effectiveUrgency: 'routine',
          overriddenUrgency: 'routine',
          overrideReason: 'ECG normal',
          overriddenBy: 'u1',
        })}
        specialtyName="Cardiology"
      />,
    )

    const card = screen.getByRole('region', { name: 'Triage result' })
    expect(within(card).getByText(DISCLAIMER)).toBeInTheDocument()
    expect(within(card).getByText('AI suggestion: emergency')).toBeInTheDocument()
    expect(within(card).getByText('Staff override: routine')).toBeInTheDocument()
    expect(within(card).getByText(/ECG normal/)).toBeInTheDocument()
  })

  it('labels a safety-rule result and shows confidence and specialty', () => {
    render(
      <TriageResultCard
        result={result({ source: 'red_flag', urgency: 'emergency', effectiveUrgency: 'emergency' })}
        specialtyName="Cardiology"
      />,
    )

    expect(screen.getByText('Safety rule')).toBeInTheDocument()
    expect(screen.getByText('Cardiology')).toBeInTheDocument()
    expect(screen.getByText('66%')).toBeInTheDocument()
  })
})

describe('TriagePanel', () => {
  it('runs triage and shows the result with specialty, confidence and disclaimer together', async () => {
    const { calls, onCurrent } = renderPanel({
      'POST /api/v1/patients/p1/triage': () => ({ status: 201, body: result() }),
    })

    await userEvent.type(await screen.findByLabelText('Symptoms for triage'), 'cough and fever')
    await userEvent.click(screen.getByRole('button', { name: 'Run triage' }))

    const card = await screen.findByRole('region', { name: 'Triage result' })
    expect(within(card).getByText('Cardiology')).toBeInTheDocument()
    expect(within(card).getByText('66%')).toBeInTheDocument()
    expect(within(card).getByText(DISCLAIMER)).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      reportedSymptoms: 'cough and fever',
    })
    expect(onCurrent).toHaveBeenLastCalledWith(expect.objectContaining({ id: 't1' }))
  })

  it('does not call the API for empty symptoms', async () => {
    const { calls } = renderPanel({})

    await userEvent.click(await screen.findByRole('button', { name: 'Run triage' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Describe the symptoms')
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('says the AI is unavailable but that booking can continue, and shows no result', async () => {
    const { onCurrent } = renderPanel({
      'POST /api/v1/patients/p1/triage': () => ({
        status: 503,
        body: { code: 'AI_SERVICE_UNAVAILABLE', message: 'raw' },
      }),
    })

    await userEvent.type(await screen.findByLabelText('Symptoms for triage'), 'sore throat')
    await userEvent.click(screen.getByRole('button', { name: 'Run triage' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      ERROR_MESSAGES.AI_SERVICE_UNAVAILABLE,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('continue')
    expect(screen.queryByRole('region', { name: 'Triage result' })).not.toBeInTheDocument()
    expect(onCurrent).not.toHaveBeenCalledWith(expect.objectContaining({ id: 't1' }))
  })

  it('lists earlier results for the patient, newest first, each with its disclaimer', async () => {
    renderPanel({
      'GET /api/v1/patients/p1/triage': () => ({
        body: [
          result({
            id: 't2',
            reportedSymptoms: 'second visit cough',
            createdAt: '2026-03-02T09:00:00Z',
          }),
          result({
            id: 't1',
            reportedSymptoms: 'first visit fever',
            urgency: 'routine',
            effectiveUrgency: 'routine',
          }),
        ],
      }),
    })

    const history = await screen.findByRole('list', { name: 'Earlier triage results' })
    const items = within(history).getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(within(items[0]).getByText(/second visit cough/)).toBeInTheDocument()
    expect(within(items[1]).getByText(/first visit fever/)).toBeInTheDocument()
    expect(within(items[0]).getByText(DISCLAIMER)).toBeInTheDocument()
    expect(within(items[1]).getByText(DISCLAIMER)).toBeInTheDocument()
  })

  it('overrides a result with a mandatory reason and shows original and override', async () => {
    const overridden = result({
      urgency: 'emergency',
      effectiveUrgency: 'routine',
      overriddenUrgency: 'routine',
      overrideReason: 'Known anxiety, ECG normal',
      overriddenBy: 'u1',
    })
    const { calls, onCurrent } = renderPanel({
      'POST /api/v1/patients/p1/triage': () => ({
        status: 201,
        body: result({ urgency: 'emergency', effectiveUrgency: 'emergency' }),
      }),
      'PATCH /api/v1/triage-results/t1/override': () => ({ body: overridden }),
    })
    await userEvent.type(await screen.findByLabelText('Symptoms for triage'), 'chest pain')
    await userEvent.click(screen.getByRole('button', { name: 'Run triage' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Override' }))

    const dialog = screen.getByRole('dialog', { name: 'Override triage result' })
    await userEvent.selectOptions(within(dialog).getByLabelText('Urgency'), 'routine')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save override' }))
    expect(within(dialog).getByRole('alert')).toHaveTextContent('reason is required')
    expect(calls.some((c) => c.method === 'PATCH')).toBe(false)

    await userEvent.type(within(dialog).getByLabelText('Reason'), 'Known anxiety, ECG normal')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save override' }))

    const card = await screen.findByText('Staff override: routine')
    expect(card).toBeInTheDocument()
    expect(screen.getByText('AI suggestion: emergency')).toBeInTheDocument()
    expect(screen.getByText(DISCLAIMER)).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({
      overriddenUrgency: 'routine',
      overrideReason: 'Known anxiety, ECG normal',
    })
    expect(onCurrent).toHaveBeenLastCalledWith(
      expect.objectContaining({ effectiveUrgency: 'routine' }),
    )
  })

  it('shows a permission error when the override is refused', async () => {
    renderPanel({
      'POST /api/v1/patients/p1/triage': () => ({ status: 201, body: result() }),
      'PATCH /api/v1/triage-results/t1/override': () => ({
        status: 403,
        body: { code: 'FORBIDDEN', message: 'raw' },
      }),
    })
    await userEvent.type(await screen.findByLabelText('Symptoms for triage'), 'cough')
    await userEvent.click(screen.getByRole('button', { name: 'Run triage' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Override' }))
    const dialog = screen.getByRole('dialog', { name: 'Override triage result' })
    await userEvent.type(within(dialog).getByLabelText('Reason'), 'because')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save override' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(ERROR_MESSAGES.FORBIDDEN)
  })
})
