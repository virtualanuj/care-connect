import { useState } from 'react'

import { messageForError } from '../../api/errorMessages'
import type { components } from '../../api/schema'
import { formatDateTime } from '../../lib/time'
import { useDraftNote, useFinalizeNote, useSaveNotes, useVisitNote } from './visitNotesApi'

type Status = components['schemas']['AppointmentStatus']

interface Props {
  appointmentId: string
  status: Status
  /** Only the appointment's own doctor may finalize; the server enforces it too. */
  canFinalize: boolean
  timeZone?: string
}

const WRITABLE: Status[] = ['in_consultation', 'completed']

export default function VisitNoteEditor({
  appointmentId,
  status,
  canFinalize,
  timeZone = 'UTC',
}: Props) {
  const writable = WRITABLE.includes(status)
  const query = useVisitNote(appointmentId, writable)
  const save = useSaveNotes(appointmentId)
  const draftNote = useDraftNote(appointmentId)
  const finalize = useFinalizeNote(appointmentId)
  const [typed, setTyped] = useState<string | null>(null)
  const [finalText, setFinalText] = useState('')
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!writable) {
    return (
      <section aria-label="Visit notes">
        <h2>Visit notes</h2>
        <p>Notes can be written once the consultation has started.</p>
      </section>
    )
  }
  if (query.isPending) return <p role="status">Loading…</p>
  if (query.isError) return <p role="alert">{messageForError(query.error)}</p>

  const note = query.data
  const locked = note?.locked ?? false
  const stored = note?.doctorNotes ?? ''
  const value = typed ?? stored
  const dirty = value !== stored

  async function attempt(action: () => Promise<unknown>) {
    setError(null)
    try {
      await action()
      return true
    } catch (caught) {
      setError(messageForError(caught))
      return false
    }
  }

  async function autosave() {
    if (locked || !dirty || !value.trim()) return
    if (await attempt(() => save.mutateAsync(value))) {
      setTyped(null)
      setSaved(true)
    }
  }

  async function submitFinal() {
    if (!finalText.trim()) {
      setError('Write the final summary before finalizing.')
      return
    }
    await attempt(() => finalize.mutateAsync(finalText.trim()))
  }

  return (
    <section className="visit-note">
      <h2>Visit notes</h2>
      <label>
        Visit notes
        <textarea
          value={value}
          readOnly={locked}
          onChange={(e) => {
            setTyped(e.target.value)
            setSaved(false)
          }}
          onBlur={autosave}
        />
      </label>
      {saved && !dirty && <p role="status">Saved</p>}
      {error && <p role="alert">{error}</p>}

      {!locked && (
        <button
          type="button"
          disabled={!note || dirty || draftNote.isPending}
          onClick={() => attempt(() => draftNote.mutateAsync())}
        >
          Generate AI draft
        </button>
      )}
      {note?.aiDraftSummary && (
        <section aria-label="AI draft">
          <h3>AI draft</h3>
          <p className="summary-text">{note.aiDraftSummary}</p>
          <p className="disclaimer">{note.aiDraftDisclaimer}</p>
          {!locked && canFinalize && (
            <button type="button" onClick={() => setFinalText(note.aiDraftSummary ?? '')}>
              Use draft as final summary
            </button>
          )}
        </section>
      )}

      {locked ? (
        <section aria-label="Final summary">
          <h3>Final summary</h3>
          <p className="summary-text">{note?.finalSummary}</p>
          <p className="muted">
            Finalized {note?.finalizedAt ? formatDateTime(note.finalizedAt, timeZone) : ''}
          </p>
        </section>
      ) : canFinalize ? (
        <div>
          <label>
            Final summary
            <textarea value={finalText} onChange={(e) => setFinalText(e.target.value)} />
          </label>
          <button type="button" disabled={finalize.isPending || dirty} onClick={submitFinal}>
            Finalize summary
          </button>
        </div>
      ) : (
        <p className="muted">Only the appointment&apos;s doctor can finalize the summary.</p>
      )}
    </section>
  )
}
