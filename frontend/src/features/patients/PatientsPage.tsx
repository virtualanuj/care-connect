import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import RegisterPatientDialog from './RegisterPatientDialog'
import { PAGE_SIZE, usePatients, type PatientSearch } from './patientsApi'

export default function PatientsPage() {
  const [phone, setPhone] = useState('')
  const [name, setName] = useState('')
  const [applied, setApplied] = useState<PatientSearch>({ phone: '', name: '', page: 1 })
  const [registering, setRegistering] = useState(false)
  const patients = usePatients(applied)

  function onSearch(event: FormEvent) {
    event.preventDefault()
    setApplied({ phone: phone.trim(), name: name.trim(), page: 1 })
  }

  const total = patients.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const searching = applied.phone !== '' || applied.name !== ''

  return (
    <section>
      <div className="page-header">
        <h1>Patients</h1>
        <button type="button" onClick={() => setRegistering(true)}>
          Register new patient
        </button>
      </div>

      <form onSubmit={onSearch} className="search-form">
        <label>
          Phone
          <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
        </label>
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <button type="submit">Search</button>
      </form>

      {patients.isError && <p role="alert">Could not load patients. Check the phone number.</p>}
      {patients.isPending && <p role="status">Loading…</p>}

      {patients.data && (
        <>
          {searching && (
            <p role="status">
              {total} {total === 1 ? 'patient' : 'patients'} found
            </p>
          )}
          {patients.data.items.length === 0 && <p>No patients match.</p>}
          {patients.data.items.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Phone</th>
                  <th>Date of birth</th>
                </tr>
              </thead>
              <tbody>
                {patients.data.items.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <Link to={`/patients/${p.id}`}>{p.name}</Link>
                    </td>
                    <td>{p.phone}</td>
                    <td>{p.dob ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="pager">
            <button
              type="button"
              disabled={applied.page <= 1}
              onClick={() => setApplied({ ...applied, page: applied.page - 1 })}
            >
              Previous
            </button>
            <span>
              Page {applied.page} of {totalPages}
            </span>
            <button
              type="button"
              disabled={applied.page >= totalPages}
              onClick={() => setApplied({ ...applied, page: applied.page + 1 })}
            >
              Next
            </button>
          </div>
        </>
      )}

      {registering && (
        <RegisterPatientDialog initialPhone={applied.phone} onClose={() => setRegistering(false)} />
      )}
    </section>
  )
}
