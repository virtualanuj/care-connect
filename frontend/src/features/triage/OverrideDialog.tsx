import { useState, type FormEvent } from 'react'

import { messageForError } from '../../api/errorMessages'
import type { SpecialtyItem } from '../../api/referenceHooks'
import Modal from '../../components/Modal'
import { useOverrideTriage, type TriageResult, type Urgency } from './triageApi'

const URGENCIES: Urgency[] = ['emergency', 'urgent', 'routine']

export default function OverrideDialog({
  result,
  specialties,
  onClose,
  onSaved,
}: {
  result: TriageResult
  specialties: SpecialtyItem[]
  onClose: () => void
  onSaved: (updated: TriageResult) => void
}) {
  const [urgency, setUrgency] = useState<Urgency>(result.effectiveUrgency)
  const [specialtyId, setSpecialtyId] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const override = useOverrideTriage(result.id, result.patientId)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!reason.trim()) {
      setError('A reason is required to override a triage result.')
      return
    }
    try {
      const updated = await override.mutateAsync({
        overriddenUrgency: urgency,
        overrideReason: reason.trim(),
        ...(specialtyId ? { overriddenSpecialtyId: specialtyId } : {}),
      })
      onSaved(updated)
      onClose()
    } catch (caught) {
      setError(messageForError(caught))
    }
  }

  return (
    <Modal title="Override triage result" onClose={onClose}>
      <p>
        Your override wins for this patient. The AI&apos;s original suggestion is kept and the
        change is recorded in the audit log.
      </p>
      <form onSubmit={submit}>
        <label>
          Urgency
          <select value={urgency} onChange={(e) => setUrgency(e.target.value as Urgency)}>
            {URGENCIES.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </label>
        <label>
          Specialty
          <select value={specialtyId} onChange={(e) => setSpecialtyId(e.target.value)}>
            <option value="">Keep the suggestion</option>
            {specialties.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Reason
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
        {error && <p role="alert">{error}</p>}
        <div className="dialog-actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" disabled={override.isPending}>
            Save override
          </button>
        </div>
      </form>
    </Modal>
  )
}
