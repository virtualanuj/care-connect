import { useState, type FormEvent } from 'react'

import { messageForError } from '../../api/errorMessages'
import Modal from '../../components/Modal'
import { useAddException, type ExceptionCreate } from './availabilityApi'

type ExceptionType = ExceptionCreate['type']

export default function ExceptionDialog({
  doctorId,
  onClose,
}: {
  doctorId: string
  onClose: () => void
}) {
  const [date, setDate] = useState('')
  const [type, setType] = useState<ExceptionType>('unavailable')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [error, setError] = useState<string | null>(null)
  const add = useAddException(doctorId)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!date) {
      setError('Choose a date.')
      return
    }
    if (type === 'extra_hours' && (!start || !end)) {
      setError('Extra hours need a start and end time.')
      return
    }
    if (Boolean(start) !== Boolean(end)) {
      setError('Enter both times, or neither for the whole day.')
      return
    }
    if (start && end && start >= end) {
      setError('Start must be before end.')
      return
    }
    try {
      await add.mutateAsync({
        date,
        type,
        ...(start && end ? { startTime: start, endTime: end } : {}),
      })
      onClose()
    } catch (caught) {
      setError(messageForError(caught))
    }
  }

  return (
    <Modal title="Add exception" onClose={onClose}>
      <form onSubmit={onSubmit} noValidate>
        <label>
          Date
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label>
          Type
          <select value={type} onChange={(e) => setType(e.target.value as ExceptionType)}>
            <option value="unavailable">Unavailable (holiday, leave)</option>
            <option value="extra_hours">Extra hours</option>
          </select>
        </label>
        <label>
          Start
          <input type="time" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          End
          <input type="time" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        {type === 'unavailable' && <p>Leave the times empty to block the whole day.</p>}
        {error && <p role="alert">{error}</p>}
        <div className="dialog-actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" disabled={add.isPending}>
            Add
          </button>
        </div>
      </form>
    </Modal>
  )
}
