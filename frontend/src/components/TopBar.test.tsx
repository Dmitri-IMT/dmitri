import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import { adminProfile, viewerProfile } from '@/test/mswHandlers'
import { getAccessToken } from '@/api/tokenStore'
import TopBar from './TopBar'

const baseURL = 'http://localhost:8000/api/v1'

function renderTopBarAs(
  profile: typeof adminProfile | typeof viewerProfile,
  route = '/',
) {
  server.use(http.get(`${baseURL}/users/me`, () => HttpResponse.json(profile)))
  return renderWithProviders(<TopBar />, { route })
}

describe('TopBar', () => {
  it.each([
    ['admin', adminProfile],
    ['viewer', viewerProfile],
  ])(
    'renders every control enabled, with no nav-users, for the %s profile',
    async (_label, profile) => {
      renderTopBarAs(profile)
      await screen.findByTestId('top-bar')

      const interactive = [
        ...screen.queryAllByRole('button'),
        ...screen.queryAllByRole('link'),
        ...screen.queryAllByRole('textbox'),
      ]
      expect(interactive.length).toBeGreaterThan(0)
      for (const el of interactive) {
        expect(el).toBeEnabled()
        expect(el).not.toHaveAttribute('aria-disabled', 'true')
        expect(el).not.toHaveAttribute('disabled')
      }

      expect(screen.queryByTestId('nav-users')).not.toBeInTheDocument()
      expect(
        screen.queryByRole('link', { name: 'Users' }),
      ).not.toBeInTheDocument()

      expect(screen.getAllByRole('link')).toHaveLength(2)
      expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute(
        'href',
        '/',
      )
      expect(screen.getByTestId('nav-settings')).toHaveAttribute(
        'href',
        '/settings',
      )
      expect(screen.getByTestId('nav-settings')).toHaveAccessibleName(
        'Settings',
      )
      expect(screen.getByRole('button', { name: 'Log out' })).toBeInTheDocument()
    },
  )

  it.each([
    ['/', 'Home', 'Settings'],
    ['/settings', 'Settings', 'Home'],
  ])('at %s marks %s active and %s muted', async (route, active, muted) => {
    renderTopBarAs(adminProfile, route)
    await screen.findByTestId('top-bar')

    const activeLink = screen.getByRole('link', { name: active })
    const mutedLink = screen.getByRole('link', { name: muted })

    expect(activeLink).toHaveAttribute('aria-current', 'page')
    expect(activeLink).toHaveClass('border-accent', 'text-foreground')
    expect(mutedLink).not.toHaveAttribute('aria-current')
    expect(mutedLink).toHaveClass('text-muted-foreground')
  })

  it('the Log out control calls signOut', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TopBar />)
    await screen.findByTestId('top-bar')
    expect(getAccessToken()).not.toBeNull()

    const logOut = screen.getByRole('button', { name: 'Log out' })
    await user.tab()
    await user.tab()
    await user.tab()
    expect(logOut).toHaveFocus()

    await user.keyboard('{Enter}')

    await waitFor(() => expect(getAccessToken()).toBeNull())
  })
})
