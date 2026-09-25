import { Outlet } from 'react-router-dom'

import ForbiddenPage from '../routes/ForbiddenPage'
import type { Role } from './authContext'
import { useAuth } from './useAuth'

export default function RequireRole({ roles }: { roles: Role[] }) {
  const { user } = useAuth()
  if (!user || !roles.includes(user.role)) return <ForbiddenPage />
  return <Outlet />
}
