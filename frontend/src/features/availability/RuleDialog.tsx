import { useState, type FormEvent } from 'react'

import { messageForError } from '../../api/errorMessages'
import Modal from '../../components/Modal'
import {
  DAYS,
  useAddRule,
  useUpdateRule,
  type DayOfWeek,
  type Rule,
  type RuleUpdate,
} from './availabilityApi'

export default function RuleDialog({
  doctorId,
  rule,
  onClose,
}: {
  doctorId: string
  rule?: Rule
  onClose: () => void
}) {
  const editing = rule !== undefined
  const [day, setDay] = useState<DayOfWeek>(rule?.dayOfWeek ?? 'monday')
  const [start, setStart] = useState(rule?.startTime ?? '')
  const [end, setEnd] = useState(rule?.endTime ?? '')
  const [error, setError] = useState<string | null>(null)
  const add = useAddRule(doctorId)
  const update = useUpdateRule(doctorId)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!start || !end) {
      setError('Enter a start and end time.')
      return
    }
    if (start >= end) {
      setError('Start must be before end.')
      return
    }
    try {
      if (editing) {
        const changes: RuleUpdate = {}
        if (day !== rule.dayOfWeek) changes.dayOfWeek = day
        if (start !== rule.startTime) changes.startTime = start
        if (end !== rule.endTime) changes.endTime = end
        if (Object.keys(changes).length > 0)
          await update.mutateAsync({ id: rule.id, body: changes })
      } else {
        await add.mutateAsync({ dayOfWeek: day, startTime: start, endTime: end })
      }
      onClose()
    } catch (caught) {
      setError(messageForError(caught))
    }
  }

  return (
    <Modal title={editing ? 'Edit working hours' : 'Add working hours'} onClose={onClose}>
      <form onSubmit={onSubmit} noValidate>
        <label>
          Day
          <select value={day} onChange={(e) => setDay(e.target.value as DayOfWeek)}>
            {DAYS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
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
        {error && <p role="alert">{error}</p>}
        <div className="dialog-actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" disabled={add.isPending || update.isPending}>
            {editing ? 'Save' : 'Add'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
