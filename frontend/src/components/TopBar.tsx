import { NavLink } from 'react-router'
import { cn } from '@/lib/utils'
import { useSession } from '@/auth/useSession'
import AdminOnly from '@/components/AdminOnly'
import ThemeToggle from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

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
        <div className="flex items-center justify-self-end">
          <ThemeToggle />
          {user && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  title={user.email}
                  data-testid="user-identity"
                  className="min-w-0 max-w-full truncate px-2 font-normal text-muted-foreground"
                >
                  {user.email}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem
                  data-testid="log-out"
                  onSelect={() => void signOut()}
                >
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>
    </header>
  )
}

export default TopBar
