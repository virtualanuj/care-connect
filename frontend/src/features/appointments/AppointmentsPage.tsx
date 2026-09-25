import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { useDoctors } from '../../api/referenceHooks'
import { useAuth } from '../../auth/useAuth'
import { formatDateTime } from '../../lib/time'
import { useClinicSettings } from '../settings/settingsApi'
import {
  PAGE_SIZE,
  STATUS_LABELS,
  useAppointments,
  usePatientNames,
  type AppointmentFilters,
  type AppointmentStatus,
} from './appointmentsApi'

export default function AppointmentsPage() {
  const { user } = useAuth()
  const isDoctor = user?.role === 'doctor'
  const doctors = useDoctors()
  const settings = useClinicSettings()
  const timeZone = settings.data?.clinicTimezone ?? 'UTC'
  const [form, setForm] = useState({ date: '', doctorId: '', status: '' })
  const [applied, setApplied] = useState<AppointmentFilters>({
    date: '',
    doctorId: '',
    status: '',
    page: 1,
  })
  const appointments = useAppointments(applied)
  const names = usePatientNames((appointments.data?.items ?? []).map((a) => a.patientId))
  const doctorName = (id: string) => doctors.data?.find((d) => d.id === id)?.name ?? '—'

  const total = appointments.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  function apply(event: FormEvent) {
    event.preventDefault()
    setApplied({ ...form, page: 1 })
  }

  return (
    <section>
      <div className="page-header">
        <h1>Appointments</h1>
        <Link to="/book">Book appointment</Link>
      </div>

      <form onSubmit={apply} className="search-form">
        <label>
          Date
          <input
            type="date"
            value={form.date}
            onChange={(e) => setForm({ ...form, date: e.target.value })}
          />
        </label>
        {!isDoctor && (
          <label>
            Doctor
            <select
              value={form.doctorId}
              onChange={(e) => setForm({ ...form, doctorId: e.target.value })}
            >
              <option value="">All doctors</option>
              {(doctors.data ?? []).map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Status
          <select
            value={form.status}
            onChange={(e) => setForm({ ...form, status: e.target.value })}
          >
            <option value="">All statuses</option>
            {(Object.keys(STATUS_LABELS) as AppointmentStatus[]).map((s) => (
              <option key={s} value={s}>
                {STATUS_LABELS[s]}
              </option>
            ))}
          </select>
        </label>
        <button type="submit">Apply filters</button>
      </form>

      {appointments.isError && <p role="alert">Could not load appointments.</p>}
      {appointments.isPending && <p role="status">Loading…</p>}
      {appointments.data && appointments.data.items.length === 0 && <p>No appointments match.</p>}
      {appointments.data && appointments.data.items.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Patient</th>
              <th>Doctor</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {appointments.data.items.map((a) => (
              <tr key={a.id}>
                <td>{formatDateTime(a.startTime, timeZone)}</td>
                <td>{names.get(a.patientId) ?? '…'}</td>
                <td>{doctorName(a.doctorId)}</td>
                <td>{STATUS_LABELS[a.status]}</td>
                <td>
                  <Link to={`/appointments/${a.id}`}>View</Link>
                </td>
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
    </section>
  )
}
