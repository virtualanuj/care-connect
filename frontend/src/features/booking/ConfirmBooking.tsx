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
}: Props) {
  const [symptoms, setSymptoms] = useState('')
  const [error, setError] = useState<unknown>(null)
  const book = useBook()

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      const appointment = await book.mutateAsync({
        doctorId: slot.doctorId,
        patientId: patient.id,
        startTime: slot.startTime,
        ...(symptoms.trim() ? { reportedSymptoms: symptoms.trim() } : {}),
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
