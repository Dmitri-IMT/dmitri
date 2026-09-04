import { NavLink } from 'react-router'
import { cn } from '@/lib/utils'
import { useSession } from '@/auth/useSession'
import AdminOnly from '@/components/AdminOnly'
import { Button } from '@/components/ui/button'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'text-body-md no-underline hover:font-bold',
    isActive ? 'font-bold text-foreground' : 'text-muted-foreground',
  )

function TopBar() {
  const { signOut, user } = useSession()

  return (
    <header data-testid="top-bar" className="border-b border-rule bg-card">
      <div className="mx-auto grid max-w-frame grid-cols-bar items-center px-4 py-3">
        <span className="justify-self-start text-title-xs">Dmitri</span>
        <nav className="flex min-w-0 items-center gap-4 justify-self-center">
          <NavLink to="/" end data-testid="nav-home" className={navLinkClass}>
            Home
          </NavLink>
          <NavLink to="/scans" data-testid="nav-scans" className={navLinkClass}>
            Scans
          </NavLink>
          <NavLink
            to="/network"
            data-testid="nav-network"
            className={navLinkClass}
          >
            Network
          </NavLink>
          <NavLink
            to="/devices"
            data-testid="nav-devices"
            className={navLinkClass}
          >
            Devices
          </NavLink>
          <AdminOnly>
            <NavLink
              to="/users"
              data-testid="nav-users"
              className={navLinkClass}
            >
              Users
            </NavLink>
          </AdminOnly>
          <NavLink
            to="/settings"
            data-testid="nav-settings"
            className={navLinkClass}
          >
            Settings
          </NavLink>
        </nav>
        <div className="flex min-w-0 items-center gap-4 justify-self-end">
          {user && (
            <span
              data-testid="user-identity"
              title={user.email}
              className="min-w-0 truncate text-body-md text-muted-foreground"
            >
              {user.email}
            </span>
          )}
          <Button
            type="button"
            variant="ghost"
            className="shrink-0"
            data-testid="log-out"
            onClick={() => void signOut()}
          >
            Log out
          </Button>
        </div>
      </div>
    </header>
  )
}

export default TopBar
