import { MenuIcon } from 'lucide-react'
import { NavLink } from 'react-router'
import { cn } from '@/lib/utils'
import { useSession } from '@/auth/useSession'
import AdminOnly from '@/components/AdminOnly'
import ThemeToggle from '@/components/ThemeToggle'
import LanguageSelect from '@/components/LanguageSelect'
import useI18n from '@/i18n/useI18n'
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
  const { t } = useI18n()

  return (
    <header data-testid="top-bar" className="border-b border-rule bg-card">
      <div className="mx-auto grid max-w-frame grid-cols-bar items-center px-4 py-3">
        <span className="justify-self-start text-title-xs">Dmitri</span>
        <nav className="flex min-w-0 items-center gap-4 justify-self-center">
          <NavLink to="/" end data-testid="nav-home" className={navLinkClass}>
            {t('nav.home')}
          </NavLink>
          <NavLink to="/scans" data-testid="nav-scans" className={navLinkClass}>
            {t('nav.scans')}
          </NavLink>
          <NavLink
            to="/network"
            data-testid="nav-network"
            className={navLinkClass}
          >
            {t('nav.network')}
          </NavLink>
          <NavLink
            to="/devices"
            data-testid="nav-devices"
            className={navLinkClass}
          >
            {t('nav.devices')}
          </NavLink>
          <AdminOnly>
            <NavLink
              to="/users"
              data-testid="nav-users"
              className={navLinkClass}
            >
              {t('nav.users')}
            </NavLink>
          </AdminOnly>
          <NavLink
            to="/settings"
            data-testid="nav-settings"
            className={navLinkClass}
          >
            {t('nav.settings')}
          </NavLink>
        </nav>
        <div className="flex items-center justify-self-end">
          {user && (
            <span
              className="sr-only"
              data-testid="user-identity"
              title={user.email}
            >
              {user.email}
            </span>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={t('nav.preferences')}
                data-testid="options-menu-toggle"
              >
                <MenuIcon />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="min-w-56 p-3">
              <p className="px-1 pb-2 text-caption-md text-muted-foreground">
                {t('nav.preferences')}
              </p>
              <div className="flex items-center justify-between gap-3 border-b border-rule pb-3">
                <span className="text-body-md">{t('nav.theme')}</span>
                <ThemeToggle />
              </div>
              <div className="flex items-center justify-between gap-3 border-b border-rule py-3">
                <span className="text-body-md">{t('nav.language')}</span>
                <LanguageSelect />
              </div>
              {user && (
                <>
                  <p
                    title={user.email}
                    className="truncate px-1 py-3 text-body-sm text-muted-foreground"
                  >
                    {user.email}
                  </p>
                  <DropdownMenuItem
                    data-testid="log-out"
                    onSelect={() => void signOut()}
                  >
                    {t('nav.logout')}
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}

export default TopBar
