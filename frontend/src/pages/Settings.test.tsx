import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { adminProfile, viewerProfile } from '@/test/mswHandlers'
import {
  ACTIVITY_NOTE,
  baseURL,
  captureDeleteRequests,
  openLeave,
  openPassword,
  renderSettings,
  signedInAs,
} from '@/test/settingsHarness'

describe('Settings', () => {
  it.each([
    ['admin', adminProfile, 'Admin'],
    ['viewer', viewerProfile, 'Viewer'],
  ])(
    'shows a %s their read-only identity first without moving focus',
    async (_role, profile, roleLabel) => {
      signedInAs(profile)
      renderSettings()

      const details = within(await screen.findByTestId('settings-details'))
      const email = details.getByTestId('settings-details-email')
      await waitFor(() => expect(email).toHaveTextContent(profile.email))
      expect(email).toBeVisible()
      expect(details.getByTestId('settings-details-role')).toHaveTextContent(
        roleLabel,
      )
      expect(details.getByTestId('settings-details-role')).toBeVisible()
      expect(details.queryByRole('textbox')).toBeNull()
      expect(screen.queryByLabelText('Display name')).toBeNull()
      expect(screen.queryByRole('button', { name: 'Save' })).toBeNull()
      expect(document.activeElement).toBe(document.body)
    },
  )

  it('requires typing your own email before the delete-account action proceeds', async () => {
    const deletes = captureDeleteRequests()
    renderSettings()

    const user = await openLeave()
    const input = screen.getByTestId('confirm-by-typing-input')
    expect(screen.getByTestId('confirm-by-typing-submit')).toBeDisabled()

    await user.type(input, 'wrong@dmitri.dev')
    expect(screen.getByTestId('confirm-by-typing-submit')).toBeDisabled()
    await user.click(screen.getByTestId('confirm-by-typing-submit'))

    expect(deletes).toEqual([])
    expect(screen.getByTestId('confirm-by-typing-dialog')).toBeInTheDocument()
  })

  it('carries two headed groups: Your account, then Leave this organisation', async () => {
    renderSettings()

    const details = await screen.findByTestId('settings-details')
    const page = screen.getByTestId('settings-idle')
    const leave = screen.getByTestId('settings-leave')

    const headings = screen.getAllByRole('heading', { level: 2 })
    expect(headings.map((heading) => heading.textContent)).toEqual([
      'Your account',
      'Leave this organisation',
    ])
    expect(details).toContainElement(headings[0])
    expect(leave).toContainElement(headings[1])
    expect(Array.from(page.querySelectorAll('section'))).toEqual([
      details,
      leave,
    ])
    // The password row and the activity note live inside the account group, not beside it.
    expect(details).toContainElement(
      screen.getByTestId('settings-password-trigger'),
    )
    expect(details).toContainElement(screen.getByTestId('settings-activity'))
    expect(screen.queryByRole('heading', { name: 'Password' })).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Activity' })).toBeNull()
  })

  it('labels the password row and puts nothing between the label and the button', async () => {
    renderSettings()

    const trigger = await screen.findByTestId('settings-password-trigger')
    const row = trigger.closest('dd')?.parentElement
    expect(row?.firstElementChild?.textContent).toBe('Password')
    expect(row?.textContent).toBe('PasswordChange password')
  })

  it('renders the whole screen, not half of it, while the profile is still loading', async () => {
    server.use(
      http.get(`${baseURL}/users/me`, async () => {
        await delay(50)
        return HttpResponse.json(adminProfile)
      }),
    )
    renderSettings()

    expect(
      await screen.findByRole('heading', { name: 'Your account' }),
    ).toBeVisible()
    expect(
      screen.getByRole('heading', { name: 'Leave this organisation' }),
    ).toBeVisible()
    expect(screen.getByTestId('settings-password-trigger')).toBeEnabled()
    expect(screen.getByTestId('settings-activity-disclosure')).toBeVisible()
    expect(screen.getByTestId('settings-leave-body')).toBeVisible()
    expect(screen.getByTestId('settings-details-email')).toHaveTextContent('')
    // Nothing to delete until the account is known.
    expect(screen.getByTestId('settings-leave-trigger')).toBeDisabled()

    await waitFor(() =>
      expect(screen.getByTestId('settings-details-email')).toHaveTextContent(
        adminProfile.email,
      ),
    )
    expect(screen.getByTestId('settings-leave-trigger')).toBeEnabled()
    expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(2)
  })

  it.each([
    ['admin', adminProfile],
    ['viewer', viewerProfile],
  ])(
    'opens the same three-field password dialog for a %s and returns focus on dismissal',
    async (_role, profile) => {
      signedInAs(profile)
      renderSettings()

      const trigger = await screen.findByTestId('settings-password-trigger')
      expect(screen.queryByLabelText('Current password')).toBeNull()

      const user = await openPassword()
      const dialogElement = screen.getByRole('dialog', {
        name: 'Change your password',
      })
      expect(dialogElement).toBe(screen.getByTestId('settings-password-dialog'))
      const dialog = within(dialogElement)
      expect(dialog.getByLabelText('Current password')).toBeVisible()
      expect(dialog.getByLabelText('New password')).toBeVisible()
      expect(dialog.getByLabelText('Confirm new password')).toBeVisible()

      await user.click(dialog.getByRole('button', { name: 'Cancel' }))

      await waitFor(() =>
        expect(screen.queryByTestId('settings-password-dialog')).toBeNull(),
      )
      await waitFor(() => expect(trigger).toHaveFocus())
    },
  )

  it.each([
    ['admin', adminProfile],
    ['viewer', viewerProfile],
  ])(
    'shows the same collapsed activity note to a %s, inside the account group',
    async (_role, profile) => {
      signedInAs(profile)
      renderSettings()

      const activity = within(await screen.findByTestId('settings-activity'))
      const trigger = activity.getByTestId('settings-activity-disclosure')
      const button = activity.getByRole('button', {
        name: "What's recorded about me?",
      })
      const note = activity.getByTestId('settings-activity-note')
      const caret = activity.getByTestId('settings-activity-caret')

      expect(button).toBeVisible()
      expect(trigger).toBe(button)
      expect(caret).toHaveAttribute('aria-hidden', 'true')
      expect(button).not.toHaveAttribute('aria-label')
      expect(button.textContent).toBe("What's recorded about me?")
      expect(button).toHaveAttribute('type', 'button')
      expect(button).toHaveAttribute('aria-expanded', 'false')
      expect(button).toHaveAttribute('aria-controls', note.id)
      expect(note.id).not.toBe('')
      expect(note).toBeInTheDocument()
      expect(note).not.toBeVisible()
      expect(note).toHaveAttribute('hidden')
      expect(note.textContent).toBe(ACTIVITY_NOTE)
      expect(activity.queryByRole('switch', { hidden: true })).toBeNull()
      expect(activity.queryByRole('checkbox', { hidden: true })).toBeNull()
      expect(
        screen
          .getByTestId('settings-activity')
          .querySelector('time, [datetime]'),
      ).toBeNull()
      expect(screen.getByTestId('settings-activity').textContent).toBe(
        `What's recorded about me?${ACTIVITY_NOTE}`,
      )
    },
  )

  it('reveals and hides the exact activity note by click without moving focus', async () => {
    signedInAs(viewerProfile)
    renderSettings()
    const user = userEvent.setup()

    const button = await screen.findByRole('button', {
      name: "What's recorded about me?",
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

    const passwordTrigger = await screen.findByTestId(
      'settings-password-trigger',
    )
    expect(document.activeElement).toBe(document.body)
    await user.tab()
    expect(passwordTrigger).toHaveFocus()
    await user.tab()

    const button = screen.getByRole('button', {
      name: "What's recorded about me?",
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
})
