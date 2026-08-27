import { NavLink } from 'react-router'
import { cn } from '@/lib/utils'
import { useSession } from '@/auth/useSession'
import AdminOnly from '@/components/AdminOnly'
import { Button } from '@/components/ui/button'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'border-b-2 border-transparent py-1',
    isActive ? 'border-accent text-foreground' : 'text-muted-foreground',
  )

function TopBar() {
  const { signOut } = useSession()

  return (
    <header data-testid="top-bar" className="border-b border-rule bg-card">
      <div className="mx-auto grid max-w-frame grid-cols-bar items-center px-4 py-3">
        <span className="justify-self-start font-title text-title-xs tracking-wide">
          DMITRI
        </span>
        <nav className="flex min-w-0 items-center gap-4 justify-self-center">
          <NavLink to="/" end data-testid="nav-home" className={navLinkClass}>
            <span className="text-nav">Home</span>
          </NavLink>
          <NavLink to="/scans" data-testid="nav-scans" className={navLinkClass}>
            <span className="text-nav">Scans</span>
          </NavLink>
          <NavLink to="/hosts" data-testid="nav-hosts" className={navLinkClass}>
            <span className="text-nav">Hosts</span>
          </NavLink>
          <NavLink
            to="/agents"
            data-testid="nav-agents"
            className={navLinkClass}
          >
            <span className="text-nav">Agents</span>
          </NavLink>
          <AdminOnly>
            <NavLink
              to="/users"
              data-testid="nav-users"
              className={navLinkClass}
            >
              <span className="text-nav">Users</span>
            </NavLink>
          </AdminOnly>
          <NavLink
            to="/settings"
            data-testid="nav-settings"
            className={navLinkClass}
          >
            <span className="text-nav">Settings</span>
          </NavLink>
        </nav>
        <Button
          type="button"
          variant="ghost"
          className="min-w-0 justify-self-end"
          data-testid="log-out"
          onClick={() => void signOut()}
        >
          Log out
        </Button>
      </div>
    </header>
  )
}

export default TopBar
