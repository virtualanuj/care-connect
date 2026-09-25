import { NavLink, Outlet } from 'react-router-dom'

export default function Layout() {
  return (
    <div className="app">
      <header className="app-header">
        <span className="brand">CareConnect</span>
        <nav aria-label="Main">
          <NavLink to="/" end>
            Home
          </NavLink>
          {/* Role-aware entries are added per milestone (M1+). */}
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  )
}
