import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
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
      expect(screen.getByTestId('nav-settings')).toHaveAttribute(
        'href',
        '/settings',
      )
      expect(screen.getByTestId('nav-settings')).toHaveAccessibleName(
        'Settings',
      )
      expect(
        screen.getByRole('button', { name: 'Log out' }),
      ).toBeInTheDocument()
    },
  )

  it('uses the frame typography and three direct grid columns', async () => {
    renderTopBarAs(adminProfile)
    const topBar = await screen.findByTestId('top-bar')
    const wordmark = screen.getByText('DMITRI')
    const nav = screen.getByRole('navigation')
    const logOut = screen.getByRole('button', { name: 'Log out' })
    const frame = nav.parentElement

    expect(frame).not.toBeNull()
    expect(frame).toBe(topBar.firstElementChild)
    expect(frame).toHaveClass('grid', 'max-w-frame', 'grid-cols-bar')
    expect(frame?.children).toHaveLength(3)
    expect(frame?.children.item(0)).toBe(wordmark)
    expect(frame?.children.item(1)).toBe(nav)
    expect(frame?.children.item(2)).toBe(logOut)
    expect(wordmark).toHaveClass(
      'justify-self-start',
      'font-title',
      'text-title-xs',
    )
    expect(nav).toHaveClass('justify-self-center', 'gap-4')
    for (const link of within(nav).getAllByRole('link')) {
      const label = link.firstElementChild
      expect(label).toBeInstanceOf(HTMLSpanElement)
      expect(label).toHaveClass('text-nav')
    }
    expect(logOut).toHaveClass('justify-self-end')
    expect(logOut).toHaveAttribute('data-variant', 'ghost')
  })

  it('keeps the navigation centred when it grows to four destinations', async () => {
    renderTopBarAs(adminProfile)
    await screen.findByTestId('nav-users')
    const nav = screen.getByRole('navigation')
    const fourthDestination = screen
      .getByTestId('nav-settings')
      .cloneNode(true) as HTMLAnchorElement
    fourthDestination.setAttribute('href', '/fourth')
    fourthDestination.dataset.testid = 'nav-fourth'

    nav.append(fourthDestination)
    expect(within(nav).getByTestId('nav-fourth')).toHaveAttribute(
      'href',
      '/fourth',
    )

    const links = within(nav).getAllByRole('link')
    expect(links).toHaveLength(4)
    for (const link of links) {
      const label = link.firstElementChild
      expect(label).toBeInstanceOf(HTMLSpanElement)
      expect(label).toHaveClass('text-nav')
    }
    expect(nav).toHaveClass('justify-self-center')
    expect(nav.parentElement).toHaveClass('grid', 'grid-cols-bar')
  })

  it('shows the Users nav item, pointing at /users, for an admin', async () => {
    renderTopBarAs(adminProfile)
    await screen.findByTestId('top-bar')

    const users = await screen.findByTestId('nav-users')
    expect(users).toHaveAttribute('href', '/users')
    expect(users).toHaveAccessibleName('Users')
    expect(screen.getAllByRole('link')).toHaveLength(3)
  })

  it('renders no Users nav item at all for a viewer', async () => {
    renderTopBarAs(viewerProfile)
    await screen.findByTestId('top-bar')
    await screen.findByTestId('nav-settings')

    expect(screen.queryByTestId('nav-users')).toBeNull()
    expect(
      screen.queryByRole('link', { name: 'Users' }),
    ).not.toBeInTheDocument()
    expect(screen.getAllByRole('link')).toHaveLength(2)
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
    await user.tab()
    expect(logOut).toHaveFocus()

    await user.keyboard('{Enter}')

    await waitFor(() => expect(getAccessToken()).toBeNull())
  })
})
