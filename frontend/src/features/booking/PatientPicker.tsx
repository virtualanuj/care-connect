import { useState, type FormEvent } from 'react'

import RegisterPatientDialog from '../patients/RegisterPatientDialog'
import { usePatients, type Patient } from '../patients/patientsApi'

interface Props {
  /** One line describing what the patient is being chosen for. */
  summary: string
  backLabel?: string
  onBack?: () => void
  onContinue: (patient: Patient) => void
}

export default function PatientPicker({
  summary,
  backLabel = 'Back to slots',
  onBack,
  onContinue,
}: Props) {
  const [phone, setPhone] = useState('')
  const [applied, setApplied] = useState('')
  const [selected, setSelected] = useState<Patient | null>(null)
  const [registering, setRegistering] = useState(false)
  const results = usePatients({ phone: applied, name: '', page: 1 }, applied !== '')

  function search(event: FormEvent) {
    event.preventDefault()
    setSelected(null)
    setApplied(phone.trim())
  }

  return (
    <section>
      <h2>Choose patient</h2>
      <p>{summary}</p>
      <form onSubmit={search} className="search-form">
        <label>
          Patient phone
          <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} required />
        </label>
        <button type="submit">Find patient</button>
      </form>
      {results.isError && <p role="alert">Could not search. Check the phone number.</p>}
      {applied && results.data && results.data.items.length === 0 && (
        <p>No patient has that number yet.</p>
      )}
      {results.data && results.data.items.length > 0 && (
        <fieldset>
          <legend>Patients under this number</legend>
          {results.data.items.map((p) => (
            <label key={p.id}>
              <input
                type="radio"
                name="patient"
                checked={selected?.id === p.id}
                onChange={() => setSelected(p)}
              />
              {p.name} — {p.phone}
            </label>
          ))}
        </fieldset>
      )}
      <div className="dialog-actions">
        {onBack && (
          <button type="button" onClick={onBack}>
            {backLabel}
          </button>
        )}
        <button type="button" onClick={() => setRegistering(true)}>
          Register new patient
        </button>
        <button type="button" disabled={!selected} onClick={() => selected && onContinue(selected)}>
          Continue
        </button>
      </div>
      {registering && (
        <RegisterPatientDialog
          initialPhone={applied || phone}
          onClose={() => setRegistering(false)}
          onRegistered={onContinue}
        />
      )}
    </section>
  )
}
