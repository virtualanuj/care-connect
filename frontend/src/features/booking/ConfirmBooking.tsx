import { useState, type FormEvent } from 'react'

import { ApiError } from '../../api/client'
import { messageForError } from '../../api/errorMessages'
import { formatDateTime } from '../../lib/time'
import type { Patient } from '../patients/patientsApi'
import { useBook, type Appointment, type Slot } from './bookingApi'

interface Props {
  slot: Slot
  doctorName: string
  patient: Patient
  timeZone: string
  onBack: () => void
  onRefresh: () => void
  onBooked: (appointment: Appointment) => void
  /** Register as a walk-in (source = walk_in). */
  walkIn?: boolean
}

/** Errors after which the slot list is stale and should be refreshed. */
const STALE_SLOT_CODES = ['SLOT_ALREADY_BOOKED', 'INVALID_SLOT']

export default function ConfirmBooking({
  slot,
  doctorName,
  patient,
  timeZone,
  onBack,
  onRefresh,
  onBooked,
  walkIn = false,
}: Props) {
  const [symptoms, setSymptoms] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [clientError, setClientError] = useState<string | null>(null)
  const book = useBook()

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setClientError(null)
    if (slot.isEmergency && !reason.trim()) {
      setClientError('A reason is required to use emergency capacity.')
      return
    }
    try {
      const appointment = await book.mutateAsync({
        doctorId: slot.doctorId,
        patientId: patient.id,
        startTime: slot.startTime,
        ...(walkIn ? { source: 'walk_in' as const } : {}),
        ...(symptoms.trim() ? { reportedSymptoms: symptoms.trim() } : {}),
        ...(slot.isEmergency
          ? {
              emergencyJustification: 'front_desk_judgment' as const,
              emergencyReason: reason.trim(),
            }
          : {}),
      })
      onBooked(appointment)
    } catch (caught) {
      setError(caught)
    }
  }

  const stale = error instanceof ApiError && STALE_SLOT_CODES.includes(error.code)

  return (
    <section>
      <h2>Confirm booking</h2>
      <dl>
        <dt>Doctor</dt>
        <dd>{doctorName}</dd>
        <dt>When</dt>
        <dd>{formatDateTime(slot.startTime, timeZone)}</dd>
        <dt>Patient</dt>
        <dd>
          {patient.name} ({patient.phone})
        </dd>
      </dl>
      <form onSubmit={submit}>
        <label>
          Reported symptoms (optional)
          <textarea value={symptoms} onChange={(e) => setSymptoms(e.target.value)} />
        </label>
        {slot.isEmergency && (
          <>
            <p>
              This slot is held for emergencies. Using it is recorded as authorized by front-desk
              judgment.
            </p>
            <label>
              Reason for using emergency capacity
              <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
            </label>
          </>
        )}
        {clientError && <p role="alert">{clientError}</p>}
        {error !== null && <p role="alert">{messageForError(error)}</p>}
        <div className="dialog-actions">
          <button type="button" onClick={onBack}>
            Back
          </button>
          {stale && (
            <button type="button" onClick={onRefresh}>
              Refresh slots
            </button>
          )}
          <button type="submit" disabled={book.isPending}>
            Confirm booking
          </button>
        </div>
      </form>
    </section>
  )
}
