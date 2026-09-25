import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { messageForError } from '../../api/errorMessages'
import Modal from '../../components/Modal'
import { useRegisterPatient, type PatientCreate } from './patientsApi'

export default function RegisterPatientDialog({
  initialPhone,
  onClose,
}: {
  initialPhone: string
  onClose: () => void
}) {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [phone, setPhone] = useState(initialPhone)
  const [dob, setDob] = useState('')
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const register = useRegisterPatient()

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    const body: PatientCreate = {
      name,
      phone,
      ...(dob ? { dob } : {}),
      ...(email ? { email } : {}),
    }
    try {
      const patient = await register.mutateAsync(body)
      onClose()
      navigate(`/patients/${patient.id}`)
    } catch (caught) {
      setError(messageForError(caught))
    }
  }

  return (
    <Modal title="Register patient" onClose={onClose}>
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
          Date of birth (optional)
          <input type="date" value={dob} onChange={(e) => setDob(e.target.value)} />
        </label>
        <label>
          Email (optional)
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        {error && <p role="alert">{error}</p>}
        <div className="dialog-actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" disabled={register.isPending}>
            Register
          </button>
        </div>
      </form>
    </Modal>
  )
}
