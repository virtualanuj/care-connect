import { NavLink, Outlet } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'

export default function Layout() {
  const { user, logout } = useAuth()

  return (
    <div className="app">
      <header className="app-header">
        <span className="brand">CareConnect</span>
        <nav aria-label="Main">
          <NavLink to="/" end>
            Home
          </NavLink>
          <NavLink to="/queue">Queue</NavLink>
          <NavLink to="/appointments">Appointments</NavLink>
          <NavLink to="/patients">Patients</NavLink>
          <NavLink to="/doctors">Doctors</NavLink>
          <NavLink to="/settings">Settings</NavLink>
          {user?.role === 'front_desk_admin' && <NavLink to="/users">Users</NavLink>}
        </nav>
        <div className="session">
          <span>{user?.name}</span>
          <button type="button" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  )
}
