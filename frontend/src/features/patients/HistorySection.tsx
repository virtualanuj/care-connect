import { useState, type FormEvent } from 'react'

import { messageForError } from '../../api/errorMessages'
import Modal from '../../components/Modal'
import { useAddHistory, useHistory, type HistoryEntry } from './patientsApi'

function AmendDialog({
  patientId,
  entry,
  onClose,
}: {
  patientId: string
  entry: HistoryEntry
  onClose: () => void
}) {
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const add = useAddHistory(patientId)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      await add.mutateAsync({ kind: 'amendment', amendsEntryId: entry.id, description: text })
      onClose()
    } catch (caught) {
      setError(messageForError(caught))
    }
  }

  return (
    <Modal title="Amend history entry" onClose={onClose}>
      <p>The original entry is kept; your correction is added beside it.</p>
      <blockquote>{entry.description}</blockquote>
      <form onSubmit={onSubmit}>
        <label>
          Correction
          <textarea value={text} onChange={(e) => setText(e.target.value)} required />
        </label>
        {error && <p role="alert">{error}</p>}
        <div className="dialog-actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" disabled={add.isPending}>
            Add amendment
          </button>
        </div>
      </form>
    </Modal>
  )
}

/** Append-only: there is deliberately no edit or delete control. */
export default function HistorySection({ patientId }: { patientId: string }) {
  const history = useHistory(patientId)
  const add = useAddHistory(patientId)
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [amending, setAmending] = useState<HistoryEntry | null>(null)

  const byId = new Map((history.data ?? []).map((e) => [e.id, e]))

  async function onAdd(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      await add.mutateAsync({ description: text })
      setText('')
    } catch (caught) {
      setError(messageForError(caught))
    }
  }

  return (
    <section>
      <h2>Medical history</h2>
      {history.isPending && <p role="status">Loading…</p>}
      {history.isError && <p role="alert">Could not load medical history.</p>}
      {history.data && history.data.length === 0 && <p>No history recorded.</p>}
      <ul className="history">
        {(history.data ?? []).map((entry, index) => (
          <li key={entry.id} aria-label={`History entry ${index + 1}`}>
            <div>
              {entry.kind === 'amendment' && <strong>Amendment</strong>}
              <p>{entry.description}</p>
              {entry.amendsEntryId && (
                <small>
                  Amends: {byId.get(entry.amendsEntryId)?.description ?? 'an earlier entry'}
                </small>
              )}
              <small> {new Date(entry.recordedAt).toLocaleString()}</small>
            </div>
            <button type="button" onClick={() => setAmending(entry)}>
              Amend
            </button>
          </li>
        ))}
      </ul>

      <form onSubmit={onAdd}>
        <label>
          New history entry
          <textarea value={text} onChange={(e) => setText(e.target.value)} required />
        </label>
        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={add.isPending}>
          Add entry
        </button>
      </form>

      {amending && (
        <AmendDialog patientId={patientId} entry={amending} onClose={() => setAmending(null)} />
      )}
    </section>
  )
}
