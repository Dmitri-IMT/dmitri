import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { adminProfile, viewerProfile } from '@/test/mswHandlers'
import {
  ACTIVITY_NOTE,
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
      expect(details.getByTestId('settings-details-email')).toHaveTextContent(
        profile.email,
      )
      expect(details.getByTestId('settings-details-email')).toBeVisible()
      expect(details.getByTestId('settings-details-role')).toHaveTextContent(
        roleLabel,
      )
      expect(details.getByTestId('settings-details-role')).toBeVisible()
      expect(details.queryByRole('textbox')).toBeNull()
      expect(screen.queryByLabelText('Display name')).toBeNull()
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

  it('orders the four sections as details, password, activity, then leave', async () => {
    renderSettings()

    const details = await screen.findByTestId('settings-details')
    const page = screen.getByTestId('settings-idle')
    const password = screen
      .getByRole('heading', { name: 'Password' })
      .closest('section')
    const activity = screen.getByTestId('settings-activity')
    const leave = screen.getByTestId('settings-leave')

    expect(password).not.toBeNull()
    expect(Array.from(page.querySelectorAll('section'))).toEqual([
      details,
      password,
      activity,
      leave,
    ])
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
    'shows the same collapsed activity disclosure to a %s',
    async (_role, profile) => {
      signedInAs(profile)
      renderSettings()

      const activity = await screen.findByTestId('settings-activity')
      const disclosure = within(activity)
      const label = disclosure.getByTestId('settings-activity-label')
      const trigger = disclosure.getByTestId('settings-activity-disclosure')
      const button = disclosure.getByRole('button', {
        name: "What's recorded?",
      })
      const note = disclosure.getByTestId('settings-activity-note')
      const caret = disclosure.getByTestId('settings-activity-caret')

      expect(label).toBeVisible()
      expect(label.textContent).toBe('Activity')
      expect(button).toBeVisible()
      expect(trigger).toBe(button)
      expect(caret).toHaveAttribute('aria-hidden', 'true')
      expect(button).not.toHaveAttribute('aria-label')
      expect(button.textContent).toBe("What's recorded?")
      expect(activity.firstElementChild).toBe(label)
      expect(label.nextElementSibling).toContainElement(trigger)
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

    const passwordTrigger = await screen.findByTestId(
      'settings-password-trigger',
    )
    expect(document.activeElement).toBe(document.body)
    await user.tab()
    expect(passwordTrigger).toHaveFocus()
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
})
