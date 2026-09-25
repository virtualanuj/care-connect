import { Link, useParams } from 'react-router-dom'

import { useDoctors } from '../../api/referenceHooks'
import { useAuth } from '../../auth/useAuth'
import { formatDateTime } from '../../lib/time'
import { useClinicSettings } from '../settings/settingsApi'
import PreVisitSummaryPanel from '../visitnotes/PreVisitSummaryPanel'
import VisitNoteEditor from '../visitnotes/VisitNoteEditor'
import AppointmentActions from './AppointmentActions'
import { STATUS_LABELS, useAppointment, usePatientNames } from './appointmentsApi'

export default function AppointmentDetailPage() {
  const { appointmentId = '' } = useParams()
  const appointment = useAppointment(appointmentId)
  const doctors = useDoctors()
  const settings = useClinicSettings()
  const { user } = useAuth()
  const timeZone = settings.data?.clinicTimezone ?? 'UTC'
  const names = usePatientNames(appointment.data ? [appointment.data.patientId] : [])

  if (appointment.isPending) return <p role="status">Loading…</p>
  if (appointment.isError) return <p role="alert">Appointment not found.</p>
  const a = appointment.data
  const doctor = doctors.data?.find((d) => d.id === a.doctorId)

  return (
    <section>
      <p>
        <Link to="/appointments">← Appointments</Link>
      </p>
      <h1>Appointment</h1>
      <dl>
        <dt>When</dt>
        <dd>{formatDateTime(a.startTime, timeZone)}</dd>
        <dt>Patient</dt>
        <dd>
          <Link to={`/patients/${a.patientId}`}>{names.get(a.patientId) ?? 'Patient'}</Link>
        </dd>
        <dt>Doctor</dt>
        <dd>{doctor?.name ?? '—'}</dd>
        <dt>Status</dt>
        <dd>{STATUS_LABELS[a.status]}</dd>
        <dt>Source</dt>
        <dd>{a.source === 'walk_in' ? 'Walk-in' : 'Scheduled'}</dd>
        <dt>Emergency slot</dt>
        <dd>{a.isEmergencySlot ? 'Yes' : 'No'}</dd>
        <dt>Reported symptoms</dt>
        <dd>{a.reportedSymptoms ?? '—'}</dd>
      </dl>
      <AppointmentActions appointment={a} />
      {a.status !== 'cancelled' && (
        <PreVisitSummaryPanel appointmentId={a.id} timeZone={timeZone} />
      )}
      {a.status !== 'cancelled' && a.status !== 'no_show' && (
        <VisitNoteEditor
          appointmentId={a.id}
          status={a.status}
          canFinalize={user?.role === 'doctor' && doctor?.userId === user.id}
          timeZone={timeZone}
        />
      )}
    </section>
  )
}
