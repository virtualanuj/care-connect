import { useState, type FormEvent } from 'react'

import { ApiError } from '../../api/client'
import { messageForError } from '../../api/errorMessages'
import Modal from '../../components/Modal'
import { useAppointmentAction } from './actionsApi'

export function ForceCancelDialog({
  appointmentId,
  onClose,
}: {
  appointmentId: string
  onClose: () => void
}) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const act = useAppointmentAction(appointmentId)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!reason.trim()) {
      setError('A reason is required to force-cancel.')
      return
    }
    try {
      await act.mutateAsync({ action: 'force-cancel', body: { reason: reason.trim() } })
      onClose()
    } catch (caught) {
      setError(messageForError(caught))
    }
  }

  return (
    <Modal title="Force cancel appointment" onClose={onClose}>
      <p>
        This cancels the appointment even though it is inside the cancellation window. The action
        and reason are recorded in the audit log.
      </p>
      <form onSubmit={submit}>
        <label>
          Reason
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
        {error && <p role="alert">{error}</p>}
        <div className="dialog-actions">
          <button type="button" onClick={onClose}>
            Keep appointment
          </button>
          <button type="submit" disabled={act.isPending}>
            Force cancel
          </button>
        </div>
      </form>
    </Modal>
  )
}

export function CancelDialog({
  appointmentId,
  cutoffHours,
  canForce,
  onClose,
  onForce,
}: {
  appointmentId: string
  cutoffHours: number | undefined
  canForce: boolean
  onClose: () => void
  onForce: () => void
}) {
  const [error, setError] = useState<unknown>(null)
  const act = useAppointmentAction(appointmentId)

  async function confirm() {
    setError(null)
    try {
      await act.mutateAsync({ action: 'cancel' })
      onClose()
    } catch (caught) {
      setError(caught)
    }
  }

  const windowClosed = error instanceof ApiError && error.code === 'CANCELLATION_WINDOW_CLOSED'

  return (
    <Modal title="Cancel appointment" onClose={onClose}>
      {cutoffHours !== undefined && (
        <p>
          Appointments can be cancelled or rescheduled up to {cutoffHours} hours before they start.
        </p>
      )}
      {error !== null && <p role="alert">{messageForError(error)}</p>}
      <div className="dialog-actions">
        <button type="button" onClick={onClose}>
          Keep appointment
        </button>
        {windowClosed && canForce && (
          <button type="button" onClick={onForce}>
            Force cancel instead
          </button>
        )}
        <button type="button" disabled={act.isPending} onClick={confirm}>
          Cancel appointment
        </button>
      </div>
    </Modal>
  )
}
