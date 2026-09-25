import { Route, Routes } from 'react-router-dom'

import RequireAuth from './auth/RequireAuth'
import RequireRole from './auth/RequireRole'
import Layout from './components/Layout'
import SettingsPage from './features/settings/SettingsPage'
import AvailabilityPage from './features/availability/AvailabilityPage'
import DoctorsPage from './features/doctors/DoctorsPage'
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
          <Route path="doctors" element={<DoctorsPage />} />
          <Route path="doctors/:doctorId/availability" element={<AvailabilityPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route element={<RequireRole roles={['front_desk_admin']} />}>
            <Route path="users" element={<UsersPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
