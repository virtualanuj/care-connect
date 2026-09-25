import { useState, type FormEvent } from 'react'

import { messageForError } from '../../api/errorMessages'
import Modal from '../../components/Modal'
import { useUpdatePatient, type Patient, type PatientUpdate } from './patientsApi'

export default function EditPatientDialog({
  patient,
  onClose,
}: {
  patient: Patient
  onClose: () => void
}) {
  const [name, setName] = useState(patient.name)
  const [phone, setPhone] = useState(patient.phone)
  const [dob, setDob] = useState(patient.dob ?? '')
  const [email, setEmail] = useState(patient.email ?? '')
  const [error, setError] = useState<string | null>(null)
  const update = useUpdatePatient(patient.id)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    const changes: PatientUpdate = {}
    if (name !== patient.name) changes.name = name
    if (phone !== patient.phone) changes.phone = phone
    if (dob !== (patient.dob ?? '')) changes.dob = dob || null
    if (email !== (patient.email ?? '')) changes.email = email || null
    try {
      if (Object.keys(changes).length > 0) await update.mutateAsync(changes)
      onClose()
    } catch (caught) {
      setError(messageForError(caught))
    }
  }

  return (
    <Modal title="Edit patient" onClose={onClose}>
      <form onSubmit={onSubmit}>
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label>
          Phone
          <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} required />
        </label>
        <label>
          Date of birth
          <input type="date" value={dob} onChange={(e) => setDob(e.target.value)} />
        </label>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        {error && <p role="alert">{error}</p>}
        <div className="dialog-actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" disabled={update.isPending}>
            Save
          </button>
        </div>
      </form>
    </Modal>
  )
}
