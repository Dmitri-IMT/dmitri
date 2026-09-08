import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { adminProfile, viewerProfile } from '@/test/mswHandlers'
import { getAccessToken } from '@/api/tokenStore'
import {
  GENERIC_LEAVE_FAILURE,
  LAST_ADMIN_REFUSAL,
  baseURL,
  captureDeleteRequests,
  confirmLeave,
  countRefreshes,
  openLeave,
  refuseDelete,
  renderSettings,
  renderSettingsWithLogin,
  signedInAs,
} from '@/test/settingsHarness'

describe('Settings leave organization', () => {
  it.each([
    ['admin', adminProfile],
    ['viewer', viewerProfile],
  ])(
    'offers the same leaving section, last on the page, to a %s',
    async (_role, profile) => {
      signedInAs(profile)
      renderSettings()

      const section = within(await screen.findByTestId('settings-leave'))
      expect(section.getByText('Leave this organisation')).toBeVisible()
      expect(screen.getByTestId('settings-leave-body')).toHaveTextContent(
        "Your account is deleted and you lose access to this organisation's scans, network and vulnerabilities straight away. This can't be undone — an admin would have to invite you again.",
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
      expect(screen.getByTestId('confirm-by-typing-dialog')).toBeInTheDocument()
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
    renderSettingsWithLogin()

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
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/settings')
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
    await waitFor(() => expect(region).toHaveTextContent(GENERIC_LEAVE_FAILURE))
    expect(region).not.toHaveTextContent(LAST_ADMIN_REFUSAL)
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/settings')
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
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/settings')
    expect(screen.getByTestId('settings-password-trigger')).toBeInTheDocument()
    expect(screen.getByTestId('settings-activity')).toBeInTheDocument()
    expect(screen.getByTestId('settings-leave-trigger')).toHaveFocus()
  })
})
