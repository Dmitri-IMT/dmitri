import type { ReactNode } from 'react'
import { useSession } from '@/auth/useSession'

function AdminOnly({ children }: { children: ReactNode }) {
  const { user } = useSession()

  if (user?.role !== 'admin') {
    return null
  }

  return children
}

export default AdminOnly
