import { useState, type FormEvent } from 'react'

import { useDoctors, useSpecialties } from '../../api/referenceHooks'
import { formatTime, todayIn } from '../../lib/time'
import { useSlots, type Slot, type SlotQuery } from '../booking/bookingApi'
import { chooseWalkInTier } from './walkInTier'

interface Props {
  timeZone: string
  onBack: () => void
  onPick: (slot: Slot, doctorName: string) => void
}

/** Finds a walk-in slot: requested doctor, then their specialty, then emergency capacity. */
export default function WalkInSlots({ timeZone, onBack, onPick }: Props) {
  const doctors = useDoctors()
  const specialties = useSpecialties()
  const [date, setDate] = useState(() => todayIn(timeZone))
  const [doctorId, setDoctorId] = useState('')
  const [applied, setApplied] = useState<{ doctorId: string; date: string } | null>(null)

  const doctor = doctors.data?.find((d) => d.id === applied?.doctorId)
  const specialtyId = doctor?.specialtyId ?? ''
  const base = { specialtyId, date: applied?.date ?? '' }

  const doctorQuery: SlotQuery | null = applied && {
    ...base,
    mode: 'doctor',
    doctorId: applied.doctorId,
  }
  const doctorSlots = useSlots(doctorQuery)
  const specialtyQuery: SlotQuery | null =
    applied && doctorSlots.isSuccess && doctorSlots.data.length === 0
      ? { ...base, mode: 'specialty', doctorId: '' }
      : null
  const specialtySlots = useSlots(specialtyQuery)
  const othersFree = (specialtySlots.data ?? []).some((s) => s.doctorId !== applied?.doctorId)
  const emergencyQuery: SlotQuery | null =
    specialtyQuery && specialtySlots.isSuccess && !othersFree
      ? { ...base, mode: 'specialty', doctorId: '', includeEmergency: true }
      : null
  const emergencySlots = useSlots(emergencyQuery)

  const settled =
    applied !== null &&
    doctorSlots.isSuccess &&
    (doctorSlots.data.length > 0 ||
      (specialtySlots.isSuccess && (othersFree || emergencySlots.isSuccess)))
  const result = settled
    ? chooseWalkInTier({
        doctorId: applied.doctorId,
        doctorSlots: doctorSlots.data ?? [],
        specialtySlots: specialtySlots.data ?? [],
        emergencySlots: emergencySlots.data ?? [],
      })
    : null

  const nameOf = (id: string) => doctors.data?.find((d) => d.id === id)?.name ?? 'Doctor'
  const specialtyName = specialties.data?.find((s) => s.id === specialtyId)?.name ?? 'the specialty'

  function search(event: FormEvent) {
    event.preventDefault()
    setApplied({ doctorId, date })
  }

  const groups = new Map<string, Slot[]>()
  for (const slot of result?.slots ?? []) {
    groups.set(slot.doctorId, [...(groups.get(slot.doctorId) ?? []), slot])
  }

  return (
    <section>
      <h2>Find a slot for the walk-in</h2>
      <form onSubmit={search} className="search-form">
        <label>
          Date
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </label>
        <label>
          Requested doctor
          <select value={doctorId} onChange={(e) => setDoctorId(e.target.value)} required>
            <option value="">Choose…</option>
            {(doctors.data ?? [])
              .filter((d) => d.active)
              .map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
          </select>
        </label>
        <button type="submit">Find slots</button>
      </form>

      {applied && !result && <p role="status">Checking availability…</p>}
      {result?.tier === 'doctor' && <p>{nameOf(applied!.doctorId)} has open slots.</p>}
      {result?.tier === 'specialty' && (
        <p>
          {nameOf(applied!.doctorId)} has no open slots on this day. Other doctors in{' '}
          {specialtyName}:
        </p>
      )}
      {result?.tier === 'emergency' && (
        <p>
          No regular slots are available. Emergency-held slots (front-desk authorization required):
        </p>
      )}
      {result?.tier === 'none' && <p>No slots or emergency capacity are available for that day.</p>}

      {[...groups.entries()].map(([id, list]) => (
        <section key={id} className="slot-group">
          <h3>{nameOf(id)}</h3>
          <div className="slots">
            {list.map((slot) => (
              <button
                key={slot.startTime}
                type="button"
                onClick={() => onPick(slot, nameOf(slot.doctorId))}
              >
                {formatTime(slot.startTime, timeZone)}
                {slot.isEmergency ? ' · emergency' : ''}
              </button>
            ))}
          </div>
        </section>
      ))}

      <div className="dialog-actions">
        <button type="button" onClick={onBack}>
          Back
        </button>
      </div>
    </section>
  )
}
