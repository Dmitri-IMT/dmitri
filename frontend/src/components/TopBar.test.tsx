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

function renderTopBarAs(profile: typeof adminProfile | typeof viewerProfile) {
  server.use(http.get(`${baseURL}/users/me`, () => HttpResponse.json(profile)))
  return renderWithProviders(<TopBar />)
}

describe('TopBar', () => {
  it('renders an identical tree for an admin and a viewer profile (AC 7)', async () => {
    const admin = renderTopBarAs(adminProfile)
    await screen.findByTestId('top-bar')
    const adminMarkup = admin.container.innerHTML
    admin.unmount()

    const viewer = renderTopBarAs(viewerProfile)
    await screen.findByTestId('top-bar')
    const viewerMarkup = viewer.container.innerHTML

    expect(viewerMarkup).toBe(adminMarkup)
  })

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
      }

      expect(screen.queryByTestId('nav-users')).not.toBeInTheDocument()

      for (const link of screen.getAllByRole('link')) {
        expect(link).toHaveAttribute('href', '/')
      }
    },
  )

  it('the Log out control calls signOut', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TopBar />)
    await screen.findByTestId('top-bar')
    expect(getAccessToken()).not.toBeNull()

    await user.click(screen.getByRole('button', { name: 'Log out' }))

    await waitFor(() => expect(getAccessToken()).toBeNull())
  })
})
