import { useState, type FormEvent } from 'react'

import { messageForError } from '../../api/errorMessages'
import { useSpecialties } from '../../api/referenceHooks'
import { formatDateTime } from '../../lib/time'
import OverrideDialog from './OverrideDialog'
import TriageResultCard from './TriageResultCard'
import { useRunTriage, useTriageHistory, type TriageResult } from './triageApi'

interface Props {
  patientId: string
  /** Called with the result created (or overridden) in this panel, or null when cleared. */
  onCurrentChange?: (result: TriageResult | null) => void
  timeZone?: string
}

export default function TriagePanel({ patientId, onCurrentChange, timeZone = 'UTC' }: Props) {
  const specialties = useSpecialties()
  const history = useTriageHistory(patientId)
  const run = useRunTriage(patientId)
  const [symptoms, setSymptoms] = useState('')
  const [current, setCurrent] = useState<TriageResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [overriding, setOverriding] = useState(false)

  const specialtyName = (id: string) => specialties.data?.find((s) => s.id === id)?.name ?? '—'

  function change(result: TriageResult | null) {
    setCurrent(result)
    onCurrentChange?.(result)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!symptoms.trim()) {
      setError('Describe the symptoms to run triage.')
      return
    }
    try {
      change(await run.mutateAsync(symptoms.trim()))
    } catch (caught) {
      change(null)
      setError(messageForError(caught))
    }
  }

  const earlier = (history.data ?? []).filter((r) => r.id !== current?.id)

  return (
    <section className="triage-panel">
      <h3>AI triage (optional)</h3>
      <form onSubmit={submit}>
        <label>
          Symptoms for triage
          <textarea value={symptoms} onChange={(e) => setSymptoms(e.target.value)} />
        </label>
        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={run.isPending}>
          Run triage
        </button>
      </form>

      {current && (
        <>
          <TriageResultCard
            result={current}
            specialtyName={specialtyName(current.suggestedSpecialtyId)}
          />
          <button type="button" onClick={() => setOverriding(true)}>
            Override
          </button>
        </>
      )}

      {earlier.length > 0 && (
        <>
          <h4>Earlier results</h4>
          <ul aria-label="Earlier triage results">
            {earlier.map((r) => (
              <li key={r.id}>
                <small>
                  {formatDateTime(r.createdAt, timeZone)} — {r.reportedSymptoms}
                </small>
                <TriageResultCard
                  result={r}
                  specialtyName={specialtyName(r.suggestedSpecialtyId)}
                  label="Earlier triage result"
                />
              </li>
            ))}
          </ul>
        </>
      )}

      {overriding && current && (
        <OverrideDialog
          result={current}
          specialties={specialties.data ?? []}
          onClose={() => setOverriding(false)}
          onSaved={change}
        />
      )}
    </section>
  )
}
