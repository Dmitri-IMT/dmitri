import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { adminProfile, viewerProfile } from '@/test/mswHandlers'
import { server } from '@/test/setup'
import { baseURL, renderSettings, signedInAs } from '@/test/settingsHarness'

describe('DeleteDataPanel', () => {
  it('keeps confirm disabled until the org name is typed, then reports skipped scans', async () => {
    let requests = 0
    server.use(
      http.delete(`${baseURL}/scans`, () => {
        requests += 1
        return HttpResponse.json({
          deleted: 3,
          skipped: 1,
          machines_removed: 2,
        })
      }),
    )
    const user = userEvent.setup()
    renderSettings()

    await user.click(await screen.findByTestId('settings-delete-scans-trigger'))
    const dialog = screen.getByTestId('confirm-by-typing-dialog')
    const confirm = within(dialog).getByTestId('confirm-by-typing-submit')
    const input = within(dialog).getByTestId('confirm-by-typing-input')
    expect(confirm).toBeDisabled()

    await user.type(input, 'Acme')
    expect(confirm).toBeDisabled()
    await user.clear(input)
    await user.type(input, adminProfile.org_name)
    expect(confirm).toBeEnabled()
    await user.click(confirm)

    expect(await screen.findByTestId('toast')).toHaveTextContent(
      'Scans deleted: 3. Running scans skipped: 1.',
    )
    expect(
      screen.queryByTestId('confirm-by-typing-dialog'),
    ).not.toBeInTheDocument()
    expect(requests).toBe(1)
  })

  it('deletes all machines', async () => {
    server.use(
      http.delete(`${baseURL}/hosts`, () => HttpResponse.json({ deleted: 5 })),
    )
    const user = userEvent.setup()
    renderSettings()

    await user.click(
      await screen.findByTestId('settings-delete-machines-trigger'),
    )
    await user.type(
      screen.getByTestId('confirm-by-typing-input'),
      adminProfile.org_name,
    )
    await user.click(screen.getByTestId('confirm-by-typing-submit'))

    expect(await screen.findByTestId('toast')).toHaveTextContent(
      'Machines deleted: 5.',
    )
  })

  it('is absent for a viewer', async () => {
    signedInAs(viewerProfile)
    renderSettings()

    await waitFor(() =>
      expect(screen.getByTestId('settings-details-email')).toHaveTextContent(
        viewerProfile.email,
      ),
    )
    expect(screen.queryByTestId('settings-delete-data')).not.toBeInTheDocument()
  })
})
