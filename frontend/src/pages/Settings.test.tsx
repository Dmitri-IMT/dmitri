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

  it('carries account, AI usage and organisation groups in order', async () => {
    renderSettings()

    const details = await screen.findByTestId('settings-details')
    const page = screen.getByTestId('settings-idle')
    const leave = screen.getByTestId('settings-leave')
    const usage = screen.getByTestId('settings-ai-usage')

    const headings = screen.getAllByRole('heading', { level: 2 })
    expect(headings.map((heading) => heading.textContent)).toEqual([
      'Your account',
      'AI usage',
      'Leave this organisation',
    ])
    expect(details).toContainElement(headings[0])
    expect(usage).toContainElement(headings[1])
    expect(leave).toContainElement(headings[2])
    expect(Array.from(page.querySelectorAll('section'))).toEqual([
      details,
      usage,
      leave,
    ])
    expect(details).toContainElement(
      screen.getByTestId('settings-password-trigger'),
    )
    expect(details).toContainElement(screen.getByTestId('settings-activity'))
    expect(screen.queryByRole('heading', { name: 'Password' })).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Activity' })).toBeNull()
  })

  it('paginates AI usage at 10 rows per page, padded to a stable height', async () => {
    const user = userEvent.setup()
    const entries = Array.from({ length: 12 }, (_, index) => ({
      operation: `op-${index}`,
      provider: 'groq',
      model: 'openai/gpt-oss-120b',
      status: 'ok',
      input_tokens: 10,
      output_tokens: 20,
      total_tokens: 30,
      latency_ms: 100,
      http_status: 200,
      request_id: null,
      error_code: null,
      scan_id: null,
      created_at: new Date(Date.now() - index * 1000).toISOString(),
    }))
    server.use(
      http.get(`${baseURL}/ai/usage`, () =>
        HttpResponse.json({
          summary: {
            requests: 12,
            input_tokens: 120,
            output_tokens: 240,
            total_tokens: 360,
            errors: 0,
          },
          data: entries,
        }),
      ),
    )
    renderSettings()

    const usage = within(await screen.findByTestId('settings-ai-usage'))
    await usage.findByText('op-0')
    expect(usage.getByText('op-9')).toBeInTheDocument()
    expect(usage.queryByText('op-10')).not.toBeInTheDocument()
    const rowsPage1 = usage.getByRole('table').querySelectorAll('tbody tr')
    expect(rowsPage1).toHaveLength(10)

    await user.click(usage.getByTestId('settings-ai-usage-page-2'))

    expect(usage.getByText('op-10')).toBeInTheDocument()
    expect(usage.getByText('op-11')).toBeInTheDocument()
    expect(usage.queryByText('op-0')).not.toBeInTheDocument()
    const rowsPage2 = usage.getByRole('table').querySelectorAll('tbody tr')
    expect(rowsPage2).toHaveLength(10)
  })

  it('carries the change-password button alone, with no Password label and outside the value list', async () => {
    renderSettings()

    await screen.findByText(adminProfile.email)
    expect(
      screen.getByTestId('settings-password-trigger').closest('dl'),
    ).toBeNull()
    expect(
      screen.getByTestId('settings-details').querySelector('dl')?.textContent,
    ).toBe(`Email${adminProfile.email}RoleAdmin`)
    expect(screen.queryByText('Password')).toBeNull()
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
    expect(screen.getByTestId('settings-leave-trigger')).toBeDisabled()

    await waitFor(() =>
      expect(screen.getByTestId('settings-details-email')).toHaveTextContent(
        adminProfile.email,
      ),
    )
    expect(screen.getByTestId('settings-leave-trigger')).toBeEnabled()
    expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(3)
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
