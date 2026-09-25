import { useState, type FormEvent } from 'react'

import { messageForError } from '../../api/errorMessages'
import type { DoctorItem, SpecialtyItem } from '../../api/referenceHooks'
import Modal from '../../components/Modal'
import { useAccounts, useCreateDoctor, useUpdateDoctor, type DoctorUpdate } from './doctorsApi'

interface Props {
  /** Existing doctor to edit; omit to create a new profile. */
  doctor?: DoctorItem
  doctors: DoctorItem[]
  specialties: SpecialtyItem[]
  onClose: () => void
}

export default function DoctorFormDialog({ doctor, doctors, specialties, onClose }: Props) {
  const editing = doctor !== undefined
  const accounts = useAccounts(!editing)
  const [userId, setUserId] = useState('')
  const [name, setName] = useState(doctor?.name ?? '')
  const [specialtyId, setSpecialtyId] = useState(doctor?.specialtyId ?? '')
  const [slotLength, setSlotLength] = useState(doctor ? String(doctor.slotLengthMinutes) : '')
  const [error, setError] = useState<string | null>(null)
  const create = useCreateDoctor()
  const update = useUpdateDoctor()

  const taken = new Set(doctors.map((d) => d.userId))
  const available = (accounts.data?.items ?? []).filter(
    (u) => u.role === 'doctor' && !taken.has(u.id),
  )

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      if (editing) {
        const changes: DoctorUpdate = {}
        if (name !== doctor.name) changes.name = name
        if (specialtyId !== doctor.specialtyId) changes.specialtyId = specialtyId
        if (Number(slotLength) !== doctor.slotLengthMinutes) {
          changes.slotLengthMinutes = Number(slotLength)
        }
        if (Object.keys(changes).length > 0)
          await update.mutateAsync({ id: doctor.id, body: changes })
      } else {
        await create.mutateAsync({
          userId,
          name,
          specialtyId,
          ...(slotLength ? { slotLengthMinutes: Number(slotLength) } : {}),
        })
      }
      onClose()
    } catch (caught) {
      setError(messageForError(caught))
    }
  }

  return (
    <Modal title={editing ? 'Edit doctor' : 'New doctor'} onClose={onClose}>
      <form onSubmit={onSubmit}>
        {!editing && (
          <label>
            Doctor account
            <select value={userId} onChange={(e) => setUserId(e.target.value)} required>
              <option value="">Choose…</option>
              {available.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name} ({u.email})
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label>
          Specialty
          <select value={specialtyId} onChange={(e) => setSpecialtyId(e.target.value)} required>
            <option value="">Choose…</option>
            {specialties.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Slot length (minutes)
          <input
            type="number"
            min={5}
            value={slotLength}
            placeholder={editing ? undefined : 'Specialty default'}
            onChange={(e) => setSlotLength(e.target.value)}
          />
        </label>
        {error && <p role="alert">{error}</p>}
        <div className="dialog-actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" disabled={create.isPending || update.isPending}>
            {editing ? 'Save' : 'Create'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
