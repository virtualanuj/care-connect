import { useState } from 'react'

import { messageForError } from '../../api/errorMessages'
import { formatDateTime } from '../../lib/time'
import { useGenerateSummary, useSummary } from './visitNotesApi'

interface Props {
  appointmentId: string
  timeZone?: string
}

/** The stored pre-visit summary. Opening the page never calls the AI; only the button does. */
export default function PreVisitSummaryPanel({ appointmentId, timeZone = 'UTC' }: Props) {
  const summary = useSummary(appointmentId)
  const generate = useGenerateSummary(appointmentId)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    setError(null)
    try {
      await generate.mutateAsync()
    } catch (caught) {
      setError(messageForError(caught))
    }
  }

  const stored = summary.data
  return (
    <section aria-label="Pre-visit summary" className="summary-panel">
      <h2>Pre-visit summary</h2>
      {summary.isPending && <p role="status">Loading…</p>}
      {summary.isError && <p role="alert">{messageForError(summary.error)}</p>}
      {summary.isSuccess && !stored && <p>No pre-visit summary yet.</p>}
      {stored && (
        <>
          {stored.stale && (
            <p className="badge badge-warning">
              This summary is out of date: history, symptoms or triage changed since it was
              generated.
            </p>
          )}
          <p className="summary-text">{stored.summary}</p>
          <p className="disclaimer">{stored.disclaimer}</p>
          <p className="muted">Generated {formatDateTime(stored.generatedAt, timeZone)}</p>
        </>
      )}
      {error && <p role="alert">{error}</p>}
      {summary.isSuccess && (
        <button type="button" onClick={run} disabled={generate.isPending}>
          {stored ? 'Refresh summary' : 'Generate summary'}
        </button>
      )}
    </section>
  )
}
