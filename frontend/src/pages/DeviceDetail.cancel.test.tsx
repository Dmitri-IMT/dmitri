import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import { focusManager } from '@tanstack/react-query'
import { renderWithProviders } from '@/test/renderWithProviders'
import { baseURL, withActiveCommand } from '@/test/agentsHarness'
import { defaultAgent, defaultCommand, viewerProfile } from '@/test/mswHandlers'
import { server } from '@/test/setup'
import { signedInAs } from '@/test/usersHarness'
import DeviceDetail from './DeviceDetail'

const agentRoute = `/devices/${defaultAgent.agent_id}`

function renderDeviceDetail() {
  return renderWithProviders(
    <Routes>
      <Route path="/devices/:agentId" element={<DeviceDetail />} />
    </Routes>,
    { route: agentRoute },
  )
}

afterEach(() => {
  focusManager.setFocused(undefined)
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('DeviceDetail stop scan', () => {
  it('shows an admin the stop action beside status and keeps it hidden from viewers', async () => {
    withActiveCommand({ ...defaultCommand, status: 'delivered' })
    const { unmount } = renderDeviceDetail()

    const deliveredStatus = await screen.findByRole('status')
    expect(
      within(deliveredStatus).getByText('Sent to the Pi'),
    ).toBeInTheDocument()
    expect(
      within(deliveredStatus).getByRole('button', { name: 'Stop scan' }),
    ).toBeInTheDocument()
    unmount()

    withActiveCommand({ ...defaultCommand, status: 'running' })
    const { unmount: unmountRunning } = renderDeviceDetail()

    const status = await screen.findByRole('status')
    expect(within(status).getByText('Scanning…')).toBeInTheDocument()
    expect(
      within(status).getByRole('button', { name: 'Stop scan' }),
    ).toBeInTheDocument()
    unmountRunning()

    signedInAs(viewerProfile)
    withActiveCommand({ ...defaultCommand, status: 'running' })
    renderDeviceDetail()

    expect(await screen.findByText('Scanning…')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Stop scan' }),
    ).not.toBeInTheDocument()
  })

  it('confirms the stop copy, dismisses without cancelling, and shows Stopping… until terminal', async () => {
    const user = userEvent.setup()
    const runningCommand = { ...defaultCommand, status: 'running' as const }
    const cancelledCommand = {
      ...defaultCommand,
      status: 'cancelled' as const,
      completed_at: new Date().toISOString(),
    }
    withActiveCommand(runningCommand)
    let cancelCalls = 0
    let terminal = false
    let releaseCancel!: () => void
    const cancelPending = new Promise<void>((resolve) => {
      releaseCancel = resolve
    })
    server.use(
      http.get(`${baseURL}/commands/:commandId`, () =>
        HttpResponse.json(terminal ? cancelledCommand : runningCommand),
      ),
      http.post(`${baseURL}/commands/:commandId/cancel`, async () => {
        cancelCalls += 1
        await cancelPending
        terminal = true
        return HttpResponse.json(cancelledCommand, { status: 200 })
      }),
    )
    renderDeviceDetail()

    const status = await screen.findByRole('status')
    await user.click(within(status).getByRole('button', { name: 'Stop scan' }))

    const dialog = await screen.findByRole('dialog')
    expect(
      within(dialog).getByRole('heading', {
        name: 'Stop the Quick scan on DMITRI-NSPI-01?',
      }),
    ).toBeInTheDocument()
    expect(
      within(dialog).getByText(
        'The Pi stops within a few seconds and saves what it found so far.',
      ),
    ).toBeInTheDocument()
    expect(
      within(dialog).getByRole('button', { name: 'Keep scanning' }),
    ).toBeInTheDocument()
    expect(
      within(dialog).getByRole('button', { name: 'Stop scan' }),
    ).toBeInTheDocument()

    await user.click(
      within(dialog).getByRole('button', { name: 'Keep scanning' }),
    )
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
    )
    await waitFor(() => expect(status).toHaveFocus())
    expect(cancelCalls).toBe(0)
    expect(screen.getByText('Scanning…')).toBeInTheDocument()

    await user.click(within(status).getByRole('button', { name: 'Stop scan' }))
    const confirmDialog = await screen.findByRole('dialog')
    await user.click(
      within(confirmDialog).getByRole('button', { name: 'Stop scan' }),
    )

    expect(await screen.findByText('Stopping…')).toBeInTheDocument()
    await waitFor(() => expect(status).toHaveFocus())
    expect(cancelCalls).toBe(1)
    expect(
      screen.queryByRole('button', { name: 'Stop scan' }),
    ).not.toBeInTheDocument()

    releaseCancel()
    expect(await screen.findByText('Scan stopped')).toBeInTheDocument()
    expect(screen.queryByText('Stopping…')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('explains that a 409 means the Pi is already uploading results', async () => {
    const user = userEvent.setup()
    withActiveCommand({ ...defaultCommand, status: 'running' })
    server.use(
      http.post(`${baseURL}/commands/:commandId/cancel`, () =>
        HttpResponse.json(
          {
            error: {
              code: 'command_not_cancellable',
              message: 'The command is uploading results.',
              details: {},
            },
          },
          { status: 409 },
        ),
      ),
    )
    renderDeviceDetail()

    const status = await screen.findByRole('status')
    await user.click(within(status).getByRole('button', { name: 'Stop scan' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Stop scan' }))

    expect(await screen.findByTestId('toast')).toHaveTextContent(
      'The scan is already uploading its results.',
    )
    expect(screen.getByText('Scanning…')).toBeInTheDocument()
  })

  it('shows Done, View scan, and the finish-before-stop message when completion wins', async () => {
    const user = userEvent.setup()
    const runningCommand = { ...defaultCommand, status: 'running' as const }
    let cancelRequested = false
    withActiveCommand(runningCommand)
    server.use(
      http.get(`${baseURL}/commands/:commandId`, () =>
        HttpResponse.json(
          cancelRequested
            ? {
                ...runningCommand,
                status: 'done' as const,
                completed_at: new Date().toISOString(),
              }
            : runningCommand,
        ),
      ),
      http.post(`${baseURL}/commands/:commandId/cancel`, () => {
        cancelRequested = true
        return HttpResponse.json(runningCommand, { status: 202 })
      }),
    )
    renderDeviceDetail()

    const status = await screen.findByRole('status')
    await user.click(within(status).getByRole('button', { name: 'Stop scan' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Stop scan' }))

    expect(await screen.findByText('Done')).toBeInTheDocument()
    expect(screen.getByTestId('agents-view-scan')).toHaveAttribute(
      'href',
      `/scans/${defaultCommand.scan_id}`,
    )
    expect(await screen.findByTestId('toast')).toHaveTextContent(
      'The scan finished before it could stop.',
    )
  })

  it.each([
    { description: 'saved results', hasResults: true },
    { description: 'no results', hasResults: false },
  ])(
    'offers the right actions for a cancellation with $description',
    async ({ hasResults }) => {
      withActiveCommand({
        ...defaultCommand,
        status: 'cancelled',
        has_results: hasResults,
      })
      renderDeviceDetail()

      expect(await screen.findByText('Scan stopped')).toBeInTheDocument()
      expect(
        await screen.findByRole('button', { name: 'Retry' }),
      ).toBeInTheDocument()
      if (hasResults) {
        expect(screen.getByRole('link', { name: 'View scan' })).toHaveAttribute(
          'href',
          `/scans/${defaultCommand.scan_id}`,
        )
        expect(
          screen.getByText(
            'You stopped this scan. Results found before the stop were saved.',
          ),
        ).toBeInTheDocument()
      } else {
        expect(
          screen.queryByRole('link', { name: 'View scan' }),
        ).not.toBeInTheDocument()
        expect(
          screen.queryByText(/results found before the stop were saved/i),
        ).not.toBeInTheDocument()
      }
    },
  )
})
