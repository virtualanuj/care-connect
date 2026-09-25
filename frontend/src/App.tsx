import AuditLogPage from './features/audit/AuditLogPage'
import { Route, Routes } from 'react-router-dom'

import RequireAuth from './auth/RequireAuth'
import RequireRole from './auth/RequireRole'
import Layout from './components/Layout'
import PatientDetailPage from './features/patients/PatientDetailPage'
import PatientsPage from './features/patients/PatientsPage'
import QueuePage from './features/queue/QueuePage'
import SettingsPage from './features/settings/SettingsPage'
import AppointmentDetailPage from './features/appointments/AppointmentDetailPage'
import AppointmentsPage from './features/appointments/AppointmentsPage'
import AvailabilityPage from './features/availability/AvailabilityPage'
import BookingPage from './features/booking/BookingPage'
import DoctorsPage from './features/doctors/DoctorsPage'
import WalkInPage from './features/walkin/WalkInPage'
import UsersPage from './features/users/UsersPage'
import HomePage from './routes/HomePage'
import LoginPage from './routes/LoginPage'
import NotFoundPage from './routes/NotFoundPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="queue" element={<QueuePage />} />
          <Route path="book" element={<BookingPage />} />
          <Route path="appointments" element={<AppointmentsPage />} />
          <Route path="appointments/:appointmentId" element={<AppointmentDetailPage />} />
          <Route path="patients" element={<PatientsPage />} />
          <Route path="patients/:patientId" element={<PatientDetailPage />} />
          <Route path="doctors" element={<DoctorsPage />} />
          <Route path="doctors/:doctorId/availability" element={<AvailabilityPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route element={<RequireRole roles={['front_desk_admin']} />}>
            <Route path="walk-in" element={<WalkInPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="audit" element={<AuditLogPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
