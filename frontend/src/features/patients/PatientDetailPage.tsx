import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import EditPatientDialog from './EditPatientDialog'
import HistorySection from './HistorySection'
import { usePatient } from './patientsApi'

export default function PatientDetailPage() {
  const { patientId = '' } = useParams()
  const patient = usePatient(patientId)
  const [editing, setEditing] = useState(false)

  if (patient.isPending) return <p role="status">Loading…</p>
  if (patient.isError) return <p role="alert">Patient not found.</p>
  const p = patient.data

  return (
    <section>
      <p>
        <Link to="/patients">← Patients</Link>
      </p>
      <div className="page-header">
        <h1>{p.name}</h1>
        <button type="button" onClick={() => setEditing(true)}>
          Edit details
        </button>
      </div>
      <dl>
        <dt>Phone</dt>
        <dd>{p.phone}</dd>
        <dt>Date of birth</dt>
        <dd>{p.dob ?? '—'}</dd>
        <dt>Email</dt>
        <dd>{p.email ?? '—'}</dd>
      </dl>

      <HistorySection patientId={patientId} />

      {editing && <EditPatientDialog patient={p} onClose={() => setEditing(false)} />}
    </section>
  )
}
