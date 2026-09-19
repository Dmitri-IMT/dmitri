import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import {
  adminProfile,
  criticalFinding,
  latestScan,
  viewerProfile,
} from '@/test/mswHandlers'
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
    'renders every control enabled for the %s profile',
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

      expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute(
        'href',
        '/',
      )
      expect(screen.getByTestId('nav-scans')).toHaveAttribute('href', '/scans')
      expect(screen.getByTestId('nav-network')).toHaveAttribute(
        'href',
        '/network',
      )
      expect(screen.getByTestId('nav-devices')).toHaveAttribute(
        'href',
        '/devices',
      )
      expect(screen.getByTestId('nav-settings')).toHaveAttribute(
        'href',
        '/settings',
      )
      expect(screen.getByTestId('nav-settings')).toHaveAccessibleName(
        'Settings',
      )
      expect(
        screen.queryByRole('button', { name: 'Log out' }),
      ).not.toBeInTheDocument()
      expect(
        await screen.findByRole('button', { name: profile.email }),
      ).toBeInTheDocument()
    },
  )

  it('renders three direct grid columns in order', async () => {
    renderTopBarAs(adminProfile)
    const topBar = await screen.findByTestId('top-bar')
    const wordmark = screen.getByText('Dmitri')
    const nav = screen.getByRole('navigation')
    const identity = await screen.findByTestId('user-identity')
    const frame = nav.parentElement

    expect(frame).not.toBeNull()
    expect(frame).toBe(topBar.firstElementChild)
    expect(frame?.children).toHaveLength(3)
    expect(frame?.children.item(0)).toBe(wordmark)
    expect(frame?.children.item(1)).toBe(nav)
    expect(frame?.children.item(2)).toContainElement(identity)
    expect(identity).toHaveAttribute('data-variant', 'ghost')
    expect(
      screen.queryByRole('button', { name: 'Log out' }),
    ).not.toBeInTheDocument()
  })

  it('shows the Users nav item, pointing at /users, for an admin', async () => {
    renderTopBarAs(adminProfile)
    await screen.findByTestId('top-bar')

    const users = await screen.findByTestId('nav-users')
    expect(users).toHaveAttribute('href', '/users')
    expect(users).toHaveAccessibleName('Users')
    expect(screen.getAllByRole('link')).toHaveLength(6)
  })

  it('renders no Users nav item at all for a viewer', async () => {
    renderTopBarAs(viewerProfile)
    await screen.findByTestId('top-bar')
    await screen.findByTestId('nav-settings')

    expect(screen.queryByTestId('nav-users')).toBeNull()
    expect(
      screen.queryByRole('link', { name: 'Users' }),
    ).not.toBeInTheDocument()
    expect(screen.getAllByRole('link')).toHaveLength(5)
  })

  it.each([
    ['admin', adminProfile],
    ['viewer', viewerProfile],
  ])(
    'shows Scans, Network and Devices for a %s, pointing at their routes',
    async (_label, profile) => {
      renderTopBarAs(profile)
      await screen.findByTestId('nav-devices')

      expect(screen.getByTestId('nav-scans')).toHaveAttribute('href', '/scans')
      expect(screen.getByTestId('nav-scans')).toHaveAccessibleName('Scans')
      expect(screen.getByTestId('nav-network')).toHaveAttribute(
        'href',
        '/network',
      )
      expect(screen.getByTestId('nav-network')).toHaveAccessibleName('Network')
      expect(screen.getByTestId('nav-devices')).toHaveAttribute(
        'href',
        '/devices',
      )
      expect(screen.getByTestId('nav-devices')).toHaveAccessibleName('Devices')
    },
  )

  it('names the six domains in order, with the Dmitri wordmark', async () => {
    renderTopBarAs(adminProfile)
    await screen.findByTestId('nav-users')

    expect(screen.getByText('Dmitri')).toBeInTheDocument()
    expect(screen.queryByText('DMITRI')).not.toBeInTheDocument()
    expect(
      within(screen.getByRole('navigation'))
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual(['Home', 'Scans', 'Network', 'Devices', 'Users', 'Settings'])
  })

  it('shows the email, truncated, with the full value in title', async () => {
    renderTopBarAs(adminProfile)

    const identity = await screen.findByTestId('user-identity')
    expect(identity).toHaveTextContent(adminProfile.email)
    expect(identity).toHaveAttribute('title', adminProfile.email)
    expect(identity).toHaveAccessibleName(adminProfile.email)
  })

  it.each([
    [`/scans/${latestScan.scan_id}`, 'nav-scans', 'Scans'],
    [`/network/${criticalFinding.host_id}`, 'nav-network', 'Network'],
  ])('at %s keeps %s active and Home inactive', async (route, testId, name) => {
    renderTopBarAs(viewerProfile, route)
    await screen.findByTestId(testId)

    const parent = screen.getByTestId(testId)
    expect(parent).toHaveAccessibleName(name)
    expect(parent).toHaveAttribute('aria-current', 'page')
    expect(screen.getByTestId('nav-home')).not.toHaveAttribute('aria-current')
  })

  it.each([
    ['/', 'Home', 'Settings'],
    ['/settings', 'Settings', 'Home'],
  ])('at %s marks %s active and %s muted', async (route, active, muted) => {
    renderTopBarAs(adminProfile, route)
    await screen.findByTestId('top-bar')

    const activeLink = screen.getByRole('link', { name: active })
    const mutedLink = screen.getByRole('link', { name: muted })

    expect(activeLink).toHaveAttribute('aria-current', 'page')
    expect(mutedLink).not.toHaveAttribute('aria-current')
  })

  it('the Log out control calls signOut', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TopBar />)
    await screen.findByTestId('nav-users')
    expect(getAccessToken()).not.toBeNull()

    const identity = screen.getByTestId('user-identity')
    await user.tab()
    await user.tab()
    await user.tab()
    await user.tab()
    await user.tab()
    await user.tab()
    await user.tab()
    await user.tab()
    expect(identity).toHaveFocus()

    await user.keyboard('{Enter}')
    const logOut = await screen.findByRole('menuitem', { name: 'Log out' })
    expect(logOut).toHaveAttribute('data-testid', 'log-out')
    await user.click(logOut)

    await waitFor(() => expect(getAccessToken()).toBeNull())
  })
})
