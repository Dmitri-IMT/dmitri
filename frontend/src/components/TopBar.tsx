import { NavLink } from 'react-router'
import { cn } from '@/lib/utils'
import { useSession } from '@/auth/useSession'
import { Button } from '@/components/ui/button'

function TopBar() {
  const { signOut } = useSession()

  return (
    <header data-testid="top-bar" className="border-b border-rule bg-card">
      {/* Three tracks with equal 1fr sides, so the nav sits at the true centre of the bar
          rather than the midpoint between the wordmark and [Log out], whose widths differ.
          The nav is centred ONLY because it holds a single item — see SCREENS.md §App shell.
          Whichever feature adds the second nav item reverts this to left-adjacent: drop the
          grid for `flex justify-between` and give the nav `flex-1`. */}
      <div className="mx-auto grid max-w-[45rem] grid-cols-[1fr_auto_1fr] items-center gap-4 px-4 py-3">
        <span className="font-title text-title-xs tracking-wide">DMITRI</span>
        <nav className="flex min-w-0 items-center justify-center gap-4">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              cn(
                'border-b-2 border-transparent py-1 text-body-md',
                isActive
                  ? 'border-accent text-foreground'
                  : 'text-muted-foreground',
              )
            }
          >
            Home
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
