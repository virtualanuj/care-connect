import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { messageForError } from '../../api/errorMessages'
import Modal from '../../components/Modal'
import type { Slot } from '../booking/bookingApi'
import { useAppointmentAction } from './actionsApi'
import type { Appointment } from './appointmentsApi'
import SlotPicker from './SlotPicker'

export default function RescheduleDialog({
  appointment,
  timeZone,
  onClose,
}: {
  appointment: Appointment
  timeZone: string
  onClose: () => void
}) {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const act = useAppointmentAction(appointment.id)

  async function pick(slot: Slot) {
    setError(null)
    try {
      const moved = await act.mutateAsync({
        action: 'reschedule',
        body: { newStartTime: slot.startTime },
      })
      onClose()
      navigate(`/appointments/${moved.id}`)
    } catch (caught) {
      setError(messageForError(caught))
    }
  }

  return (
    <Modal title="Reschedule appointment" onClose={onClose}>
      <p>Pick a new time with the same doctor. The current time is released.</p>
      <SlotPicker
        doctorId={appointment.doctorId}
        timeZone={timeZone}
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
