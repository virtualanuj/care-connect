import { useState, type FormEvent } from 'react'

import { useDoctors, useSpecialties } from '../../api/referenceHooks'
import { useAuth } from '../../auth/useAuth'
import { formatTime } from '../../lib/time'
import { useSlots, type Slot, type SlotQuery } from './bookingApi'

interface Props {
  applied: SlotQuery | null
  timeZone: string
  onSearch: (query: SlotQuery) => void
  onPick: (slot: Slot, doctorName: string) => void
}

export default function SlotSearch({ applied, timeZone, onSearch, onPick }: Props) {
  const { user } = useAuth()
  const isDoctor = user?.role === 'doctor'
  const doctors = useDoctors()
  const specialties = useSpecialties()
  const [mode, setMode] = useState<SlotQuery['mode']>('doctor')
  const [doctorId, setDoctorId] = useState('')
  const [specialtyId, setSpecialtyId] = useState('')
  const [date, setDate] = useState(applied?.date ?? '')
  const slots = useSlots(applied)

  const selectable = (doctors.data ?? []).filter(
    (d) => d.active && (!isDoctor || d.userId === user?.id),
  )
  const nameOf = (id: string) => doctors.data?.find((d) => d.id === id)?.name ?? 'Doctor'

  function submit(event: FormEvent) {
    event.preventDefault()
    onSearch({ mode, doctorId, specialtyId, date })
  }

  const groups = new Map<string, Slot[]>()
  for (const slot of slots.data ?? []) {
    groups.set(slot.doctorId, [...(groups.get(slot.doctorId) ?? []), slot])
  }

  return (
    <section>
      <h2>Find a slot</h2>
      <form onSubmit={submit} className="search-form">
        <label>
          Date
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </label>
        <fieldset>
          <legend>Search by</legend>
          <label>
            <input
              type="radio"
              name="mode"
              checked={mode === 'doctor'}
              onChange={() => setMode('doctor')}
            />
            Specific doctor
          </label>
          {!isDoctor && (
            <label>
              <input
                type="radio"
                name="mode"
                checked={mode === 'specialty'}
                onChange={() => setMode('specialty')}
              />
              Any doctor in a specialty
            </label>
          )}
        </fieldset>
        {mode === 'doctor' ? (
          <label>
            Doctor
            <select value={doctorId} onChange={(e) => setDoctorId(e.target.value)} required>
              <option value="">Choose…</option>
              {selectable.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <label>
            Specialty
            <select value={specialtyId} onChange={(e) => setSpecialtyId(e.target.value)} required>
              <option value="">Choose…</option>
              {(specialties.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <button type="submit">Find slots</button>
      </form>

      {slots.isFetching && <p role="status">Loading slots…</p>}
      {slots.isError && <p role="alert">Could not load slots.</p>}
      {slots.data && slots.data.length === 0 && <p>No open slots for that day.</p>}
      {[...groups.entries()].map(([id, list]) => (
        <section key={id} className="slot-group">
          <h3>{nameOf(id)}</h3>
          <div className="slots">
            {list.map((slot) => (
              <button
                key={`${slot.doctorId}-${slot.startTime}`}
                type="button"
                onClick={() => onPick(slot, nameOf(slot.doctorId))}
              >
                {formatTime(slot.startTime, timeZone)}
              </button>
            ))}
          </div>
        </section>
      ))}
    </section>
  )
}
