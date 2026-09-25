import { useState, type FormEvent } from 'react'

import { messageForError } from '../../api/errorMessages'
import type { SpecialtyItem } from '../../api/referenceHooks'
import Modal from '../../components/Modal'
import { useCreateSpecialty, useUpdateSpecialty, type SpecialtyUpdate } from './doctorsApi'

export default function SpecialtyDialog({
  specialty,
  onClose,
}: {
  specialty?: SpecialtyItem
  onClose: () => void
}) {
  const editing = specialty !== undefined
  const [name, setName] = useState(specialty?.name ?? '')
  const [slot, setSlot] = useState(specialty ? String(specialty.defaultSlotLengthMinutes) : '')
  const [error, setError] = useState<string | null>(null)
  const create = useCreateSpecialty()
  const update = useUpdateSpecialty()

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      if (editing) {
        const changes: SpecialtyUpdate = {}
        if (name !== specialty.name) changes.name = name
        if (Number(slot) !== specialty.defaultSlotLengthMinutes) {
          changes.defaultSlotLengthMinutes = Number(slot)
        }
        if (Object.keys(changes).length > 0) {
          await update.mutateAsync({ id: specialty.id, body: changes })
        }
      } else {
        await create.mutateAsync({ name, defaultSlotLengthMinutes: Number(slot) })
      }
      onClose()
    } catch (caught) {
      setError(messageForError(caught))
    }
  }

  return (
    <Modal title={editing ? 'Edit specialty' : 'New specialty'} onClose={onClose}>
      <form onSubmit={onSubmit}>
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label>
          Default slot length (minutes)
          <input
            type="number"
            min={5}
            value={slot}
            onChange={(e) => setSlot(e.target.value)}
            required
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
