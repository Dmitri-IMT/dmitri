import { Link } from 'react-router'
import { useSession } from '@/auth/useSession'
import AdminOnly from '@/components/AdminOnly'
import { Button } from '@/components/ui/button'

export function FirstScanCta() {
  return (
    <AdminOnly>
      <Button asChild data-testid="first-scan-cta">
        <Link to="/devices">Run first scan</Link>
      </Button>
    </AdminOnly>
  )
}

export function FirstScanNote() {
  const { user } = useSession()

  if (user?.role !== 'viewer') {
    return null
  }

  return (
    <p
      data-testid="first-scan-note"
      className="text-body-md text-muted-foreground"
    >
      Ask your admin to run the first scan.
    </p>
  )
}
