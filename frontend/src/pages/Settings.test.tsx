import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { Route, Routes, useLocation } from 'react-router'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import { adminProfile, viewerProfile } from '@/test/mswHandlers'
import { getAccessToken } from '@/api/tokenStore'
import type { components } from '@/types/openapi'
import Settings from './Settings'

type UserProfileResponse = components['schemas']['UserProfileResponse']

const baseURL = 'http://localhost:8000/api/v1'
const CURRENT = 'old-long-enough-password'
const NEXT = 'new-long-enough-password'

function signedInAs(profile: UserProfileResponse) {
  server.use(http.get(`${baseURL}/users/me`, () => HttpResponse.json(profile)))
}

function captureChangeRequests() {
  const bodies: unknown[] = []
  server.use(
    http.post(`${baseURL}/auth/change-password`, async ({ request }) => {
      bodies.push(await request.json())
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return bodies
}

function countRefreshes() {
  const calls: number[] = []
  server.use(
    http.post(`${baseURL}/auth/refresh`, () => {
      calls.push(1)
      return HttpResponse.json({
        access_token: 'refreshed-token',
        token_type: 'bearer',
        expires_in: 3600,
      })
    }),
  )
  return calls
}

function respond(status: number, code: string) {
  server.use(
    http.post(`${baseURL}/auth/change-password`, () =>
      HttpResponse.json({ error: { code, message: 'nope' } }, { status }),
    ),
  )
}

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location-probe">{location.pathname}</div>
}

function renderSettings() {
  return renderWithProviders(
    <>
      <LocationProbe />
      <Routes>
        <Route path="/settings" element={<Settings />} />
        <Route path="/login" element={<div data-testid="login-route" />} />
      </Routes>
    </>,
    { route: '/settings' },
  )
}

async function submit(current = CURRENT, next = NEXT, confirmation = NEXT) {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('Current password'), current)
  await user.type(screen.getByLabelText('New password'), next)
  await user.type(screen.getByLabelText('Confirm new password'), confirmation)
  await user.click(screen.getByTestId('settings-submit'))
  return user
}

describe('Settings', () => {
  it.each([
    ['admin', adminProfile],
    ['viewer', viewerProfile],
  ])('shows the same change-password form to a %s', async (_role, profile) => {
    signedInAs(profile)
    renderSettings()

    expect(await screen.findByTestId('settings-form')).toBeInTheDocument()
    expect(screen.getByTestId('settings-current')).toBeInTheDocument()
    expect(screen.getByTestId('settings-new')).toBeInTheDocument()
    expect(screen.getByTestId('settings-confirm')).toBeInTheDocument()
    expect(screen.getByTestId('settings-submit')).toHaveTextContent(
      'Change password',
    )
  })

  it('renders the policy hint exactly once', async () => {
    signedInAs(adminProfile)
    renderSettings()

    await screen.findByTestId('settings-form')
    expect(screen.getAllByText(/At least 12 characters/)).toHaveLength(1)
    expect(screen.getByTestId('settings-new-hint')).toHaveTextContent(
      /At least 12 characters/,
    )
  })

  it('focuses Current password and uses the designed autocomplete values', async () => {
    renderSettings()

    await waitFor(() =>
      expect(screen.getByTestId('settings-current')).toHaveFocus(),
    )
    expect(screen.getByTestId('settings-current')).toHaveAttribute(
      'autocomplete',
      'current-password',
    )
    expect(screen.getByTestId('settings-new')).toHaveAttribute(
      'autocomplete',
      'new-password',
    )
    expect(screen.getByTestId('settings-confirm')).toHaveAttribute(
      'autocomplete',
      'new-password',
    )
  })

  it('renders no profile fields, display name, or email input', async () => {
    renderSettings()

    await screen.findByTestId('settings-form')
    const page = within(screen.getByTestId('settings-idle'))
    expect(page.queryAllByRole('textbox')).toEqual([])
    expect(screen.queryByLabelText('Email')).toBeNull()
    expect(screen.queryByLabelText('Display name')).toBeNull()
    expect(screen.getByTestId('settings-idle').textContent).not.toContain(
      adminProfile.email,
    )
  })

  it('mounts every message region empty before any submit, so announcements land', async () => {
    renderSettings()

    await screen.findByTestId('settings-form')
    for (const id of [
      'settings-current-error',
      'settings-new-error',
      'settings-confirm-error',
      'settings-error',
      'settings-success',
    ]) {
      expect(screen.getByTestId(id)).toBeEmptyDOMElement()
    }
    expect(screen.getByTestId('settings-error')).toHaveAttribute(
      'role',
      'alert',
    )
    expect(screen.getByTestId('settings-success')).toHaveAttribute(
      'role',
      'status',
    )
  })

  it('renders nothing disabled at idle', async () => {
    renderSettings()

    await screen.findByTestId('settings-form')
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
  })

  it('sends exactly current_password and new_password', async () => {
    const bodies = captureChangeRequests()
    renderSettings()

    await submit()

    await waitFor(() =>
      expect(screen.getByTestId('settings-success')).toHaveTextContent(
        'Password changed.',
      ),
    )
    expect(bodies).toEqual([{ current_password: CURRENT, new_password: NEXT }])
  })

  it('renders the mismatch error and issues zero requests', async () => {
    const bodies = captureChangeRequests()
    renderSettings()

    await submit(CURRENT, NEXT, 'a-different-password')

    await waitFor(() =>
      expect(screen.getByTestId('settings-confirm-error')).toHaveTextContent(
        "Those two passwords don't match.",
      ),
    )
    expect(bodies).toEqual([])
    expect(screen.getByTestId('settings-confirm')).toHaveFocus()
  })

  it('treats 400 wrong_current_password as a field error without refreshing or navigating', async () => {
    const refreshes = countRefreshes()
    respond(400, 'wrong_current_password')
    renderSettings()

    await screen.findByTestId('settings-form')
    const refreshesBefore = refreshes.length
    const tokenBefore = getAccessToken()

    await submit()

    await waitFor(() =>
      expect(screen.getByTestId('settings-current-error')).toHaveTextContent(
        "That's not your current password.",
      ),
    )
    expect(refreshes.length).toBe(refreshesBefore)
    expect(getAccessToken()).toBe(tokenBefore)
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/settings')
    expect(screen.queryByTestId('login-route')).toBeNull()
    expect(screen.getByTestId('settings-form')).toBeInTheDocument()
    expect(screen.getByTestId('settings-current')).toHaveFocus()
  })

  it('targets New password on 400 password_policy_violation and stays on Settings', async () => {
    respond(400, 'password_policy_violation')
    renderSettings()

    await submit()

    await waitFor(() =>
      expect(screen.getByTestId('settings-new-error')).toHaveTextContent(
        "That password isn't strong enough. Try a longer one that isn't based on a name or a date.",
      ),
    )
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/settings')
    expect(screen.getByTestId('settings-new')).toHaveFocus()
  })

  it('clears the fields and confirms in place on 204', async () => {
    renderSettings()

    await screen.findByTestId('settings-form')
    const tokenBefore = getAccessToken()

    await submit()

    await waitFor(() =>
      expect(screen.getByTestId('settings-success')).toHaveTextContent(
        'Password changed.',
      ),
    )
    expect(screen.getByTestId('settings-success')).toHaveAttribute(
      'role',
      'status',
    )
    expect(screen.getByTestId('settings-current')).toHaveValue('')
    expect(screen.getByTestId('settings-new')).toHaveValue('')
    expect(screen.getByTestId('settings-confirm')).toHaveValue('')
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/settings')
    expect(getAccessToken()).toBe(tokenBefore)
  })

  it('keeps a settled message while editing and clears it when the next submit begins', async () => {
    respond(400, 'wrong_current_password')
    renderSettings()

    const user = await submit()
    await waitFor(() =>
      expect(
        screen.getByTestId('settings-current-error'),
      ).not.toBeEmptyDOMElement(),
    )

    await user.type(screen.getByTestId('settings-current'), 'x')
    expect(
      screen.getByTestId('settings-current-error'),
    ).not.toBeEmptyDOMElement()

    server.use(
      http.post(
        `${baseURL}/auth/change-password`,
        () => new HttpResponse(null, { status: 204 }),
      ),
    )
    await user.click(screen.getByTestId('settings-submit'))

    await waitFor(() =>
      expect(
        screen.getByTestId('settings-current-error'),
      ).toBeEmptyDOMElement(),
    )
  })

  it('clears a settled success line only when the next submit begins', async () => {
    renderSettings()

    const user = await submit()
    await waitFor(() =>
      expect(screen.getByTestId('settings-success')).not.toBeEmptyDOMElement(),
    )

    await user.type(screen.getByTestId('settings-current'), CURRENT)
    expect(screen.getByTestId('settings-success')).not.toBeEmptyDOMElement()

    respond(400, 'wrong_current_password')
    await user.click(screen.getByTestId('settings-submit'))

    await waitFor(() =>
      expect(screen.getByTestId('settings-success')).toBeEmptyDOMElement(),
    )
  })

  it('recovers from a network failure with the approved error and a usable form', async () => {
    server.use(
      http.post(`${baseURL}/auth/change-password`, () => HttpResponse.error()),
    )
    renderSettings()

    await submit()

    await waitFor(() =>
      expect(screen.getByTestId('settings-error')).toHaveTextContent(
        "Couldn't reach Dmitri. Try again in a moment.",
      ),
    )
    expect(screen.getByTestId('settings-submit')).toBeEnabled()
    expect(screen.getByTestId('settings-submit')).toHaveTextContent(
      'Change password',
    )
    expect(screen.getByTestId('settings-current')).toHaveValue(CURRENT)
    expect(screen.getByTestId('settings-success')).toBeEmptyDOMElement()
  })

  it('recovers from a 500 the same way', async () => {
    server.use(
      http.post(
        `${baseURL}/auth/change-password`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    )
    renderSettings()

    await submit()

    await waitFor(() =>
      expect(screen.getByTestId('settings-error')).toHaveTextContent(
        "Couldn't reach Dmitri. Try again in a moment.",
      ),
    )
    expect(screen.getByTestId('settings-form')).toBeInTheDocument()
  })

  it('disables the action in flight and issues no second request', async () => {
    let requestCount = 0
    server.use(
      http.post(`${baseURL}/auth/change-password`, async () => {
        requestCount += 1
        await delay(50)
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderSettings()

    const user = await submit()

    const button = screen.getByTestId('settings-submit')
    expect(button).toHaveTextContent('Changing password…')
    expect(button).toBeDisabled()
    await user.click(button)

    await waitFor(() =>
      expect(screen.getByTestId('settings-success')).not.toBeEmptyDOMElement(),
    )
    expect(requestCount).toBe(1)
  })

  it('drives exactly one refresh and retry on a genuine 401', async () => {
    const refreshes = countRefreshes()
    let attempts = 0
    server.use(
      http.post(`${baseURL}/auth/change-password`, () => {
        attempts += 1
        if (attempts === 1) {
          return new HttpResponse(null, { status: 401 })
        }
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderSettings()

    await screen.findByTestId('settings-form')
    const refreshesBefore = refreshes.length

    await submit()

    await waitFor(() =>
      expect(screen.getByTestId('settings-success')).toHaveTextContent(
        'Password changed.',
      ),
    )
    expect(attempts).toBe(2)
    expect(refreshes.length).toBe(refreshesBefore + 1)
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/settings')
  })

  it('clears the session and navigates to Login when the 401 refresh fails', async () => {
    renderSettings()
    await screen.findByTestId('settings-form')

    server.use(
      http.post(
        `${baseURL}/auth/change-password`,
        () => new HttpResponse(null, { status: 401 }),
      ),
      http.post(
        `${baseURL}/auth/refresh`,
        () => new HttpResponse(null, { status: 401 }),
      ),
    )

    await submit()

    await screen.findByTestId('login-route')
    expect(getAccessToken()).toBeNull()
  })
})
