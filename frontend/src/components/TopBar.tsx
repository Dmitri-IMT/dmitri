import { NavLink } from 'react-router'
import { cn } from '@/lib/utils'
import { useSession } from '@/auth/useSession'
import { Button } from '@/components/ui/button'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'border-b-2 border-transparent py-1 text-body-md',
    isActive ? 'border-accent text-foreground' : 'text-muted-foreground',
  )

function TopBar() {
  const { signOut } = useSession()

  return (
    <header data-testid="top-bar" className="border-b border-rule bg-card">
      <div className="mx-auto flex max-w-[45rem] items-center justify-between gap-4 px-4 py-3">
        <span className="font-title text-title-xs tracking-wide">DMITRI</span>
        <nav className="flex min-w-0 flex-1 items-center gap-4">
          <NavLink to="/" end className={navLinkClass}>
            Home
          </NavLink>
          <NavLink to="/settings" data-testid="nav-settings" className={navLinkClass}>
            Settings
          </NavLink>
        </nav>
        <Button
          type="button"
          variant="ghost"
          className="min-w-0"
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
