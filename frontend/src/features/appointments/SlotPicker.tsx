import { useState, type FormEvent } from 'react'

import { formatTime } from '../../lib/time'
import { useSlots, type Slot, type SlotQuery } from '../booking/bookingApi'

interface Props {
  doctorId: string
  timeZone: string
  minDate?: string
  maxDate?: string
  disabled?: boolean
  onPick: (slot: Slot) => void
}

/** Find open (regular) slots of one doctor on a chosen date and pick one. */
export default function SlotPicker({
  doctorId,
  timeZone,
  minDate,
  maxDate,
  disabled,
  onPick,
}: Props) {
  const [date, setDate] = useState('')
  const [applied, setApplied] = useState<SlotQuery | null>(null)
  const slots = useSlots(applied)

  function search(event: FormEvent) {
    event.preventDefault()
    setApplied({ mode: 'doctor', doctorId, specialtyId: '', date })
  }

  return (
    <div>
      <form onSubmit={search} className="search-form">
        <label>
          Date
          <input
            type="date"
            value={date}
            min={minDate}
            max={maxDate}
            onChange={(e) => setDate(e.target.value)}
            required
          />
        </label>
        <button type="submit">Find slots</button>
      </form>
      {slots.isFetching && <p role="status">Loading slots…</p>}
      {slots.data && slots.data.length === 0 && <p>No open slots for that day.</p>}
      <div className="slots">
        {(slots.data ?? []).map((slot) => (
          <button
            key={slot.startTime}
            type="button"
            disabled={disabled}
            onClick={() => onPick(slot)}
          >
            {formatTime(slot.startTime, timeZone)}
          </button>
        ))}
      </div>
    </div>
  )
}
