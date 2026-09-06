import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { delay, http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { adminProfile } from '@/test/mswHandlers'
import { getAccessToken } from '@/api/tokenStore'
import {
  CURRENT,
  NEXT,
  baseURL,
  captureChangeRequests,
  countRefreshes,
  openPassword,
  renderSettings,
  respond,
  signedInAs,
  submit,
} from '@/test/settingsHarness'

describe('Settings password dialog', () => {
  it('renders the policy hint exactly once inside the dialog', async () => {
    signedInAs(adminProfile)
    renderSettings()

    await openPassword()
    const dialog = within(screen.getByTestId('settings-password-dialog'))
    expect(dialog.getAllByText(/At least 12 characters/)).toHaveLength(1)
    expect(dialog.getByTestId('settings-new-hint')).toHaveTextContent(
      /At least 12 characters/,
    )
  })

  it('focuses Current password on open and uses the designed autocomplete values', async () => {
    renderSettings()

    await openPassword()
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

  it('mounts every message region empty before it receives an announcement', async () => {
    renderSettings()

    await screen.findByTestId('settings-password-trigger')
    const success = screen.getByTestId('settings-success')
    expect(success).toBeEmptyDOMElement()
    expect(success).toHaveAttribute('role', 'status')

    await openPassword()
    const dialog = within(screen.getByTestId('settings-password-dialog'))
    for (const id of [
      'settings-current-error',
      'settings-new-error',
      'settings-confirm-error',
      'settings-error',
    ]) {
      expect(dialog.getByTestId(id)).toBeEmptyDOMElement()
    }
    expect(dialog.getByTestId('settings-current-error')).toHaveAttribute(
      'role',
      'alert',
    )
    expect(dialog.getByTestId('settings-new-error')).toHaveAttribute(
      'role',
      'alert',
    )
    expect(dialog.getByTestId('settings-confirm-error')).toHaveAttribute(
      'role',
      'alert',
    )
    expect(dialog.getByTestId('settings-error')).toHaveAttribute(
      'role',
      'alert',
    )
  })

  it('renders nothing disabled once the screen has settled', async () => {
    renderSettings()

    await screen.findByTestId('settings-password-trigger')
    await waitFor(() =>
      expect(screen.getByTestId('settings-leave-trigger')).toBeEnabled(),
    )
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

  it('flips each field between hidden and revealed, and flips the control name with it', async () => {
    renderSettings()

    const user = await openPassword()
    const dialog = within(screen.getByTestId('settings-password-dialog'))
    const current = screen.getByTestId('settings-current')
    await user.type(current, CURRENT)
    expect(current).toHaveAttribute('type', 'password')
    expect(
      dialog.getAllByRole('button', { name: 'Show password' }),
    ).toHaveLength(3)

    await user.click(
      dialog.getAllByRole('button', { name: 'Show password' })[0],
    )

    expect(current).toHaveAttribute('type', 'text')
    expect(current).toHaveValue(CURRENT)
    expect(
      dialog.getAllByRole('button', { name: 'Show password' }),
    ).toHaveLength(2)
    expect(screen.getByTestId('settings-new')).toHaveAttribute(
      'type',
      'password',
    )

    const hide = dialog.getByRole('button', { name: 'Hide password' })
    expect(hide).toHaveAttribute('type', 'button')
    await user.click(hide)

    expect(current).toHaveAttribute('type', 'password')
    expect(dialog.queryByRole('button', { name: 'Hide password' })).toBeNull()
  })

  it('renders exactly one reveal control on each password field', async () => {
    renderSettings()

    await openPassword()
    for (const id of ['settings-current', 'settings-new', 'settings-confirm']) {
      const shell = screen
        .getByTestId(id)
        .closest('[data-slot="password-input"]')
      expect(shell).not.toBeNull()
      const toggle = within(shell as HTMLElement).getByRole('button', {
        name: 'Show password',
      })
      expect(toggle).toHaveAttribute('data-slot', 'password-input-toggle')
      expect(toggle).not.toHaveAttribute('tabindex', '-1')
    }
  })

  it('hides every field again when the dialog is closed and reopened', async () => {
    renderSettings()

    const user = await openPassword()
    for (const toggle of screen.getAllByRole('button', {
      name: 'Show password',
    })) {
      await user.click(toggle)
    }
    expect(
      screen.getAllByRole('button', { name: 'Hide password' }),
    ).toHaveLength(3)

    await user.click(screen.getByTestId('settings-password-cancel'))
    await waitFor(() =>
      expect(screen.queryByTestId('settings-password-dialog')).toBeNull(),
    )
    await user.click(screen.getByTestId('settings-password-trigger'))
    await screen.findByTestId('settings-password-dialog')

    expect(
      screen.getAllByRole('button', { name: 'Show password' }),
    ).toHaveLength(3)
    expect(screen.queryByRole('button', { name: 'Hide password' })).toBeNull()
    expect(screen.getByTestId('settings-current')).toHaveAttribute(
      'type',
      'password',
    )
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

    await screen.findByTestId('settings-password-trigger')
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

  it('closes the dialog, returns focus, and places the 204 success under the trigger', async () => {
    renderSettings()

    const trigger = await screen.findByTestId('settings-password-trigger')
    const tokenBefore = getAccessToken()

    const user = await submit()

    const success = screen.getByTestId('settings-success')
    await waitFor(() => expect(success).toHaveTextContent('Password changed.'))
    expect(success).toHaveAttribute('role', 'status')
    expect(trigger.nextElementSibling).toBe(success)
    expect(screen.queryByTestId('settings-password-dialog')).toBeNull()
    await waitFor(() => expect(trigger).toHaveFocus())
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/settings')
    expect(getAccessToken()).toBe(tokenBefore)

    await user.click(trigger)
    await screen.findByTestId('settings-password-dialog')
    expect(screen.getByTestId('settings-current')).toHaveValue('')
    expect(screen.getByTestId('settings-new')).toHaveValue('')
    expect(screen.getByTestId('settings-confirm')).toHaveValue('')
    expect(success).toBeEmptyDOMElement()
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

    respond(400, 'password_policy_violation')
    await user.click(screen.getByTestId('settings-submit'))

    await waitFor(() =>
      expect(
        screen.getByTestId('settings-current-error'),
      ).toBeEmptyDOMElement(),
    )
    expect(screen.getByTestId('settings-new-error')).not.toBeEmptyDOMElement()
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

    await screen.findByTestId('settings-password-trigger')
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
    await screen.findByTestId('settings-password-trigger')

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
