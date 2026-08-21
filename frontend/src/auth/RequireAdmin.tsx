import { Outlet } from 'react-router'
import { useSession } from './useSession'
import NotFound from '@/pages/NotFound'

export function RequireAdmin() {
  const { status, user } = useSession()

  if (status === 'booting') {
    return null
  }

  if (user?.role !== 'admin') {
    return <NotFound />
  }

  return <Outlet />
}
