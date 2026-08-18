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
import Login from './Login'

type UserProfileResponse = components['schemas']['UserProfileResponse']

const baseURL = 'http://localhost:8000/api/v1'
const CURRENT = 'old-long-enough-password'
const NEXT = 'new-long-enough-password'
const ACTIVITY_NOTE =
  "Your organization's admins can see when you last used Dmitri and when you last signed in. We record only these times — not what you viewed or did."

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

function captureDeleteRequests() {
  const urls: string[] = []
  server.use(
    http.delete(`${baseURL}/users/me`, ({ request }) => {
      urls.push(request.url)
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return urls
}

function refuseDelete(status: number, code: string) {
  const urls: string[] = []
  server.use(
    http.delete(`${baseURL}/users/me`, ({ request }) => {
      urls.push(request.url)
      return HttpResponse.json({ error: { code, message: 'nope' } }, { status })
    }),
  )
  return urls
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
  return (
    <>
      <div data-testid="location-probe">{location.pathname}</div>
      <div data-testid="location-state">{JSON.stringify(location.state)}</div>
    </>
  )
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

const LAST_ADMIN_REFUSAL =
  "You're the only admin. Make someone else an admin first, then you can leave."
const GENERIC_LEAVE_FAILURE = "Couldn't delete your account."

async function openLeave() {
  const user = userEvent.setup()
  await user.click(await screen.findByTestId('settings-leave-trigger'))
  await screen.findByTestId('confirm-by-typing-dialog')
  return user
}

async function confirmLeave(user: ReturnType<typeof userEvent.setup>) {
  await user.type(
    screen.getByTestId('confirm-by-typing-input'),
    adminProfile.email,
  )
  await user.click(screen.getByTestId('confirm-by-typing-submit'))
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

  it.each([
    ['admin', adminProfile],
    ['viewer', viewerProfile],
  ])(
    'shows the same collapsed activity disclosure to a %s',
    async (_role, profile) => {
      signedInAs(profile)
      renderSettings()

      const activity = await screen.findByTestId('settings-activity')
      const disclosure = within(activity)
      const label = disclosure.getByTestId('settings-activity-label')
      const button = disclosure.getByRole('button', {
        name: "What's recorded?",
      })
      const note = disclosure.getByTestId('settings-activity-note')

      expect(label).toBeVisible()
      expect(label.textContent).toBe('Activity')
      expect(button).toBeVisible()
      expect(button).not.toHaveAttribute('aria-label')
      expect(button.textContent).toBe("What's recorded?")
      expect(button).toHaveAttribute('type', 'button')
      expect(button).toHaveAttribute('aria-expanded', 'false')
      expect(button).toHaveAttribute('aria-controls', note.id)
      expect(note.id).not.toBe('')
      expect(note).toBeInTheDocument()
      expect(note).not.toBeVisible()
      expect(note).toHaveAttribute('hidden')
      expect(note.textContent).toBe(ACTIVITY_NOTE)
      expect(disclosure.queryByRole('switch', { hidden: true })).toBeNull()
      expect(disclosure.queryByRole('checkbox', { hidden: true })).toBeNull()
      expect(activity.querySelector('time, [datetime]')).toBeNull()
      expect(activity.textContent).toBe(
        `ActivityWhat's recorded?${ACTIVITY_NOTE}`,
      )
    },
  )

  it('reveals and hides the exact activity note by click without moving focus', async () => {
    signedInAs(viewerProfile)
    renderSettings()
    const user = userEvent.setup()

    const button = await screen.findByRole('button', {
      name: "What's recorded?",
    })
    const note = screen.getByTestId('settings-activity-note')

    await user.click(button)

    expect(button).toHaveFocus()
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(button).toHaveAttribute('aria-controls', note.id)
    expect(note.textContent).toBe(ACTIVITY_NOTE)
    expect(note).toBeVisible()

    await user.click(button)

    expect(button).toHaveFocus()
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(button).toHaveAttribute('aria-controls', note.id)
    expect(note).toBeInTheDocument()
    expect(note).not.toBeVisible()
  })

  it('reaches the disclosure by Tab and reveals and hides it with Enter and Space', async () => {
    signedInAs(adminProfile)
    renderSettings()
    const user = userEvent.setup()

    await screen.findByTestId('settings-form')
    await waitFor(() =>
      expect(screen.getByTestId('settings-current')).toHaveFocus(),
    )
    await user.tab()
    await user.tab()
    await user.tab()
    await user.tab()

    const button = screen.getByRole('button', {
      name: "What's recorded?",
    })
    const note = screen.getByTestId('settings-activity-note')
    expect(button).toHaveFocus()
    expect(button).toHaveAttribute('aria-controls', note.id)

    await user.keyboard('{Enter}')

    expect(button).toHaveFocus()
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(button).toHaveAttribute('aria-controls', note.id)
    expect(note.textContent).toBe(ACTIVITY_NOTE)
    expect(note).toBeVisible()

    await user.keyboard('{Enter}')

    expect(button).toHaveFocus()
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(button).toHaveAttribute('aria-controls', note.id)
    expect(note).toBeInTheDocument()
    expect(note).not.toBeVisible()

    await user.keyboard(' ')

    expect(button).toHaveFocus()
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(button).toHaveAttribute('aria-controls', note.id)
    expect(note.textContent).toBe(ACTIVITY_NOTE)
    expect(note).toBeVisible()

    await user.keyboard(' ')

    expect(button).toHaveFocus()
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(button).toHaveAttribute('aria-controls', note.id)
    expect(note).toBeInTheDocument()
    expect(note).not.toBeVisible()
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
  describe('leaving the organization', () => {
    it.each([
      ['admin', adminProfile],
      ['viewer', viewerProfile],
    ])(
      'offers the same leaving section, last on the page, to a %s',
      async (_role, profile) => {
        signedInAs(profile)
        renderSettings()

        const section = within(await screen.findByTestId('settings-leave'))
        expect(section.getByText('Leave this organization')).toBeVisible()
        expect(screen.getByTestId('settings-leave-body')).toHaveTextContent(
          "Your account is deleted and you lose access to this organization's scans, hosts and findings straight away. This can't be undone — an admin would have to invite you again.",
        )
        expect(section.getByRole('button', { name: 'Delete my account' })).toBe(
          screen.getByTestId('settings-leave-trigger'),
        )
        expect(
          screen
            .getByTestId('settings-idle')
            .textContent?.endsWith('Delete my account'),
        ).toBe(true)
        expect(screen.queryByTestId('confirm-by-typing-dialog')).toBeNull()
      },
    )

    it.each(['', 'admin@', 'someone.else@dmitri.dev'])(
      'requests nothing while the typed value is %s',
      async (typed) => {
        const deletes = captureDeleteRequests()
        renderSettings()

        const user = await openLeave()
        const input = screen.getByTestId('confirm-by-typing-input')
        if (typed !== '') {
          await user.type(input, typed)
        }

        expect(screen.getByTestId('confirm-by-typing-submit')).toBeDisabled()
        await user.click(screen.getByTestId('confirm-by-typing-submit'))
        await user.type(input, '{Enter}')

        expect(deletes).toEqual([])
        expect(
          screen.getByTestId('confirm-by-typing-dialog'),
        ).toBeInTheDocument()
      },
    )

    it('requests the removal exactly once on an exact match', async () => {
      const deletes = captureDeleteRequests()
      renderSettings()

      const user = await openLeave()
      await user.type(
        screen.getByTestId('confirm-by-typing-input'),
        adminProfile.email,
      )
      expect(screen.getByTestId('confirm-by-typing-submit')).toBeEnabled()
      await user.click(screen.getByTestId('confirm-by-typing-submit'))

      await screen.findByTestId('login-route')
      expect(deletes).toHaveLength(1)
    })

    it('drops the session and lands on Login with the deletion note on 204', async () => {
      renderSettings()

      const user = await openLeave()
      await confirmLeave(user)

      await screen.findByTestId('login-route')
      expect(getAccessToken()).toBeNull()
      expect(screen.getByTestId('location-probe')).toHaveTextContent('/login')
      expect(screen.getByTestId('location-state')).toHaveTextContent(
        '{"accountDeleted":true}',
      )
      expect(screen.queryByTestId('settings-leave')).toBeNull()
    })

    it('leaves focus on the arrival note once the route settles', async () => {
      renderWithProviders(
        <>
          <LocationProbe />
          <Routes>
            <Route path="/settings" element={<Settings />} />
            <Route path="/login" element={<Login />} />
          </Routes>
        </>,
        { route: '/settings' },
      )

      const user = await openLeave()
      await confirmLeave(user)

      const note = await screen.findByTestId('login-success')
      expect(note).toHaveTextContent('Your account has been deleted.')
      await waitFor(() => expect(document.activeElement).toBe(note))
    })

    it('refuses the only admin, keeps the session, and announces the refusal again on a retry', async () => {
      const refreshes = countRefreshes()
      const deletes = refuseDelete(409, 'last_admin')
      renderSettings()

      await screen.findByTestId('settings-leave-trigger')
      const tokenBefore = getAccessToken()
      const refreshesBefore = refreshes.length
      const user = await openLeave()
      await confirmLeave(user)

      const region = screen.getByTestId('confirm-by-typing-error')
      await waitFor(() => expect(region).toHaveTextContent(LAST_ADMIN_REFUSAL))
      expect(getAccessToken()).toBe(tokenBefore)
      expect(refreshes.length).toBe(refreshesBefore)
      expect(screen.getByTestId('location-probe')).toHaveTextContent(
        '/settings',
      )
      expect(screen.getByTestId('confirm-by-typing-dialog')).toBeInTheDocument()
      expect(screen.getByTestId('confirm-by-typing-input')).toHaveValue(
        adminProfile.email,
      )

      await user.click(screen.getByTestId('confirm-by-typing-submit'))

      await waitFor(() => expect(deletes).toHaveLength(2))
      await waitFor(() => expect(region).toHaveTextContent(LAST_ADMIN_REFUSAL))
    })

    it.each([
      ['a 500', () => refuseDelete(500, 'internal_error')],
      [
        'a network failure',
        () => {
          const urls: string[] = []
          server.use(
            http.delete(`${baseURL}/users/me`, ({ request }) => {
              urls.push(request.url)
              return HttpResponse.error()
            }),
          )
          return urls
        },
      ],
    ])('offers another attempt after %s', async (_label, arrange) => {
      const deletes = arrange()
      renderSettings()

      const user = await openLeave()
      await confirmLeave(user)

      const region = screen.getByTestId('confirm-by-typing-error')
      await waitFor(() =>
        expect(region).toHaveTextContent(GENERIC_LEAVE_FAILURE),
      )
      expect(region).not.toHaveTextContent(LAST_ADMIN_REFUSAL)
      expect(screen.getByTestId('location-probe')).toHaveTextContent(
        '/settings',
      )
      expect(getAccessToken()).not.toBeNull()

      const submitButton = screen.getByRole('button', {
        name: 'Delete my account',
      })
      expect(submitButton).toBeEnabled()
      await user.click(submitButton)

      await waitFor(() => expect(deletes).toHaveLength(2))
    })

    it('requests nothing when the confirmation is cancelled', async () => {
      const deletes = captureDeleteRequests()
      renderSettings()

      const user = await openLeave()
      await user.type(
        screen.getByTestId('confirm-by-typing-input'),
        adminProfile.email,
      )
      await user.click(screen.getByTestId('confirm-by-typing-cancel'))

      await waitFor(() =>
        expect(screen.queryByTestId('confirm-by-typing-dialog')).toBeNull(),
      )
      expect(deletes).toEqual([])
      expect(screen.getByTestId('location-probe')).toHaveTextContent(
        '/settings',
      )
      expect(screen.getByTestId('settings-form')).toBeInTheDocument()
      expect(screen.getByTestId('settings-activity')).toBeInTheDocument()
      expect(screen.getByTestId('settings-leave-trigger')).toHaveFocus()
    })
  })
})
