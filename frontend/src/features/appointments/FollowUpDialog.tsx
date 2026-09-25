import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { messageForError } from '../../api/errorMessages'
import Modal from '../../components/Modal'
import { addDays, todayIn } from '../../lib/time'
import type { Slot } from '../booking/bookingApi'
import { useAppointmentAction } from './actionsApi'
import type { Appointment } from './appointmentsApi'
import SlotPicker from './SlotPicker'

export default function FollowUpDialog({
  appointment,
  timeZone,
  maxDays,
  onClose,
}: {
  appointment: Appointment
  timeZone: string
  maxDays: number | undefined
  onClose: () => void
}) {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const act = useAppointmentAction(appointment.id)

  // The server measures the window from the *first* visit of a chain; this hint uses this visit.
  const visitDay = todayIn(timeZone, new Date(appointment.startTime))
  const maxDate = maxDays === undefined ? undefined : addDays(visitDay, maxDays)

  async function pick(slot: Slot) {
    setError(null)
    try {
      const followUp = await act.mutateAsync({
        action: 'follow-up',
        body: { startTime: slot.startTime },
      })
      onClose()
      navigate(`/appointments/${followUp.id}`)
    } catch (caught) {
      setError(messageForError(caught))
    }
  }

  return (
    <Modal title="Book follow-up" onClose={onClose}>
      <p>Follow-ups are booked with the same doctor within the follow-up window.</p>
      <SlotPicker
        doctorId={appointment.doctorId}
        timeZone={timeZone}
        minDate={visitDay}
        maxDate={maxDate}
        disabled={act.isPending}
        onPick={pick}
      />
      {error && <p role="alert">{error}</p>}
      <div className="dialog-actions">
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
    </Modal>
  )
}
