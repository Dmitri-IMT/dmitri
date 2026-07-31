import { Navigate, Outlet } from 'react-router'
import { useSession } from './useSession'

export function RequireSession() {
  const { status } = useSession()

  if (status === 'booting') {
    return null
  }

  if (status === 'anonymous') {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
