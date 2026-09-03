import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { focusManager } from '@tanstack/react-query'
import { COMMAND_POLL_INTERVAL_MS } from '@/api/commands'
import { renderWithProviders } from '@/test/renderWithProviders'
import {
  baseURL,
  commandRefused,
  withActiveCommand,
} from '@/test/agentsHarness'
import { defaultAgent, defaultCommand, viewerProfile } from '@/test/mswHandlers'
import { server } from '@/test/setup'
import { signedInAs } from '@/test/usersHarness'
import Agents from './Agents'

afterEach(() => {
  focusManager.setFocused(undefined)
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('Agents command lifecycle', () => {
  describe('trigger and polling', () => {
    it('sends quick mode and the stored subnet, then focuses the status', async () => {
      const user = userEvent.setup()
      const focusSpy = vi.spyOn(HTMLElement.prototype, 'focus')
      let body: unknown
      server.use(
        http.post(
          `${baseURL}/agents/:agentId/commands`,
          async ({ request }) => {
            body = await request.json()
            return HttpResponse.json(
              {
                command_id: defaultCommand.command_id,
                scan_id: defaultCommand.scan_id,
                agent_id: defaultAgent.agent_id,
                status: 'queued' as const,
              },
              { status: 202 },
            )
          },
        ),
      )
      renderWithProviders(<Agents />)

      await user.click(await screen.findByTestId('agents-scan-now'))
      expect(await screen.findByText('Queued')).toBeInTheDocument()
      expect(body).toEqual({ scan_mode: 'quick', subnet: '192.168.0.0/24' })
      expect(screen.getByTestId('agents-command-status')).toHaveFocus()
      expect(screen.getByTestId('agents-command-status')).toHaveAttribute(
        'aria-live',
        'polite',
      )
      expect(screen.getByTestId('agents-command-status')).toHaveAttribute(
        'tabindex',
        '-1',
      )
      expect(
        focusSpy.mock.contexts.filter(
          (context) =>
            context instanceof HTMLElement &&
            context.dataset.testid === 'agents-command-status',
        ),
      ).toHaveLength(1)
    })

    it('sends the selected NSPi read-only mapping submode', async () => {
      const user = userEvent.setup()
      let body: unknown
      server.use(
        http.post(
          `${baseURL}/agents/:agentId/commands`,
          async ({ request }) => {
            body = await request.json()
            return HttpResponse.json(
              {
                command_id: defaultCommand.command_id,
                scan_id: defaultCommand.scan_id,
                agent_id: defaultAgent.agent_id,
                status: 'queued' as const,
              },
              { status: 201 },
            )
          },
        ),
      )
      renderWithProviders(<Agents />)

      await user.click(await screen.findByRole('combobox', { name: 'Scan mode' }))
      await user.click(screen.getByRole('option', { name: 'NSPi' }))
      await user.click(screen.getByRole('combobox', { name: 'NSPi submode' }))
      await user.click(
        screen.getByRole('option', { name: 'Read-only mapping' }),
      )
      await user.click(screen.getByTestId('agents-scan-now'))

      await waitFor(() =>
        expect(body).toEqual({
          scan_mode: 'nspi',
          subnet: '192.168.0.0/24',
          nspi_options: {
            version: 1,
            submode: 'read_only_mapping',
            active_risk_acknowledged: false,
          },
        }),
      )
    })

    it('polls through all running states and stops at done', async () => {
      vi.useFakeTimers()
      const focusSpy = vi.spyOn(HTMLElement.prototype, 'focus')
      withActiveCommand()
      let reads = 0
      const statuses = [
        'queued',
        'delivered',
        'running',
        'uploading',
        'done',
      ] as const
      server.use(
        http.get(`${baseURL}/commands/:commandId`, () => {
          const status = statuses[Math.min(reads, statuses.length - 1)]
          reads += 1
          return HttpResponse.json({
            ...defaultCommand,
            status,
            completed_at: status === 'done' ? new Date().toISOString() : null,
          })
        }),
      )
      renderWithProviders(<Agents />)

      await vi.waitFor(() =>
        expect(screen.getByText('Queued')).toBeInTheDocument(),
      )
      const statusRegion = screen.getByTestId('agents-command-status')
      expect(screen.queryByTestId('agents-view-scan')).not.toBeInTheDocument()
      for (const label of [
        'Sent to the Pi',
        'Scanning…',
        'Uploading results…',
      ]) {
        await vi.advanceTimersByTimeAsync(COMMAND_POLL_INTERVAL_MS)
        await vi.waitFor(() =>
          expect(screen.getByText(label)).toBeInTheDocument(),
        )
        expect(screen.getByTestId('agents-command-status')).toBe(statusRegion)
        expect(screen.queryByTestId('agents-view-scan')).not.toBeInTheDocument()
      }
      await vi.advanceTimersByTimeAsync(COMMAND_POLL_INTERVAL_MS)
      await vi.waitFor(() =>
        expect(screen.getByText('Done')).toBeInTheDocument(),
      )
      expect(screen.getByTestId('agents-command-status')).toBe(statusRegion)
      expect(
        focusSpy.mock.contexts.filter(
          (context) =>
            context instanceof HTMLElement &&
            context.dataset.testid === 'agents-command-status',
        ),
      ).toHaveLength(0)
      expect(screen.getByTestId('agents-view-scan')).toHaveAttribute(
        'href',
        `/scans/${defaultCommand.scan_id}`,
      )
      const terminalReads = reads
      await vi.advanceTimersByTimeAsync(COMMAND_POLL_INTERVAL_MS * 3)
      expect(reads).toBe(terminalReads)
    })
  })

  describe('adoption and follow latch', () => {
    it('holds an adopted done command after the agent clears it', async () => {
      let agentReads = 0
      server.use(
        http.get(`${baseURL}/agents`, () =>
          HttpResponse.json({
            data: [
              { ...defaultAgent, active_command_id: defaultCommand.command_id },
            ],
          }),
        ),
        http.get(`${baseURL}/agents/:agentId`, () => {
          agentReads += 1
          return HttpResponse.json({
            ...defaultAgent,
            active_command_id:
              agentReads === 1 ? defaultCommand.command_id : null,
          })
        }),
        http.get(`${baseURL}/commands/:commandId`, () =>
          HttpResponse.json({
            ...defaultCommand,
            status: 'done' as const,
            completed_at: new Date().toISOString(),
          }),
        ),
      )
      renderWithProviders(<Agents />)

      expect(await screen.findByTestId('agents-view-scan')).toHaveAttribute(
        'href',
        `/scans/${defaultCommand.scan_id}`,
      )
      await waitFor(() => expect(agentReads).toBeGreaterThan(1))
      expect(screen.getByTestId('agents-view-scan')).toBeInTheDocument()
    })

    it('adopts and displays a running command that this screen did not start', async () => {
      const focusSpy = vi.spyOn(HTMLElement.prototype, 'focus')
      withActiveCommand({ ...defaultCommand, status: 'running' })
      renderWithProviders(<Agents />)

      expect(await screen.findByText('Scanning…')).toBeInTheDocument()
      expect(screen.getByTestId('agents-command-status')).not.toHaveFocus()
      expect(
        focusSpy.mock.contexts.filter(
          (context) =>
            context instanceof HTMLElement &&
            context.dataset.testid === 'agents-command-status',
        ),
      ).toHaveLength(0)
      expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
      expect(screen.queryByTestId('agents-view-scan')).not.toBeInTheDocument()
    })

    it('passively adopts a newly observed active command without moving focus', async () => {
      const focusSpy = vi.spyOn(HTMLElement.prototype, 'focus')
      let detailReads = 0
      server.use(
        http.get(`${baseURL}/agents/:agentId`, () => {
          detailReads += 1
          return HttpResponse.json({
            ...defaultAgent,
            active_command_id:
              detailReads === 1 ? null : defaultCommand.command_id,
          })
        }),
        http.get(`${baseURL}/commands/:commandId`, () =>
          HttpResponse.json({ ...defaultCommand, status: 'running' as const }),
        ),
      )
      renderWithProviders(<Agents />)

      expect(await screen.findByTestId('agents-scan-now')).toBeInTheDocument()
      fireEvent.focus(window)
      focusManager.setFocused(true)

      expect(await screen.findByText('Scanning…')).toBeInTheDocument()
      expect(detailReads).toBeGreaterThan(1)
      expect(screen.getByTestId('agents-command-status')).not.toHaveFocus()
      expect(
        focusSpy.mock.contexts.filter(
          (context) =>
            context instanceof HTMLElement &&
            context.dataset.testid === 'agents-command-status',
        ),
      ).toHaveLength(0)
    })

    it('passively replaces a followed id only when the server reports a newly observed id', async () => {
      const focusSpy = vi.spyOn(HTMLElement.prototype, 'focus')
      const replacementCommandId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'
      const queriedCommandIds: string[] = []
      let detailReads = 0
      server.use(
        http.get(`${baseURL}/agents`, () =>
          HttpResponse.json({
            data: [
              { ...defaultAgent, active_command_id: defaultCommand.command_id },
            ],
          }),
        ),
        http.get(`${baseURL}/agents/:agentId`, () => {
          detailReads += 1
          return HttpResponse.json({
            ...defaultAgent,
            active_command_id:
              detailReads === 1
                ? defaultCommand.command_id
                : replacementCommandId,
          })
        }),
        http.get(`${baseURL}/commands/:commandId`, ({ params }) => {
          const commandId = String(params.commandId)
          queriedCommandIds.push(commandId)
          return HttpResponse.json({
            ...defaultCommand,
            command_id: commandId,
            status:
              commandId === replacementCommandId
                ? ('uploading' as const)
                : ('running' as const),
          })
        }),
      )
      renderWithProviders(<Agents />)

      expect(await screen.findByText('Scanning…')).toBeInTheDocument()
      focusManager.setFocused(false)
      fireEvent.focus(window)
      focusManager.setFocused(true)

      expect(await screen.findByText('Uploading results…')).toBeInTheDocument()
      expect(queriedCommandIds).toContain(defaultCommand.command_id)
      expect(queriedCommandIds).toContain(replacementCommandId)
      expect(screen.getByTestId('agents-command-status')).not.toHaveFocus()
      expect(
        focusSpy.mock.contexts.filter(
          (context) =>
            context instanceof HTMLElement &&
            context.dataset.testid === 'agents-command-status',
        ),
      ).toHaveLength(0)
    })

    it('keeps following a command when a later server observation becomes null', async () => {
      let detailReads = 0
      let commandReads = 0
      server.use(
        http.get(`${baseURL}/agents`, () =>
          HttpResponse.json({
            data: [
              { ...defaultAgent, active_command_id: defaultCommand.command_id },
            ],
          }),
        ),
        http.get(`${baseURL}/agents/:agentId`, () => {
          detailReads += 1
          return HttpResponse.json({
            ...defaultAgent,
            active_command_id:
              detailReads === 1 ? defaultCommand.command_id : null,
          })
        }),
        http.get(`${baseURL}/commands/:commandId`, () => {
          commandReads += 1
          return HttpResponse.json({
            ...defaultCommand,
            status: 'running' as const,
          })
        }),
      )
      renderWithProviders(<Agents />)

      expect(await screen.findByText('Scanning…')).toBeInTheDocument()
      focusManager.setFocused(false)
      fireEvent.focus(window)
      focusManager.setFocused(true)
      await waitFor(() => expect(detailReads).toBeGreaterThan(1))

      expect(screen.getByText('Scanning…')).toBeInTheDocument()
      expect(screen.getByTestId('agents-command-status')).toBeInTheDocument()
      expect(commandReads).toBeGreaterThan(1)
    })

    it('keeps an adopted run visible across a background agent-read failure', async () => {
      let detailReads = 0
      server.use(
        http.get(`${baseURL}/agents`, () =>
          HttpResponse.json({
            data: [
              { ...defaultAgent, active_command_id: defaultCommand.command_id },
            ],
          }),
        ),
        http.get(`${baseURL}/agents/:agentId`, () => {
          detailReads += 1
          return detailReads === 1
            ? HttpResponse.json({
                ...defaultAgent,
                active_command_id: defaultCommand.command_id,
              })
            : new HttpResponse(null, { status: 500 })
        }),
        http.get(`${baseURL}/commands/:commandId`, () =>
          HttpResponse.json({ ...defaultCommand, status: 'running' as const }),
        ),
      )
      renderWithProviders(<Agents />)

      expect(await screen.findByText('Scanning…')).toBeInTheDocument()
      fireEvent.focus(window)
      focusManager.setFocused(true)
      await waitFor(() => expect(detailReads).toBeGreaterThan(1))

      expect(screen.getByTestId('agents-card')).toBeInTheDocument()
      expect(screen.queryByTestId('agents-error')).not.toBeInTheDocument()
      expect(screen.getByText('Scanning…')).toBeInTheDocument()
    })
  })

  describe('terminal presentation', () => {
    it('distinguishes failed from expired and offers retry to an admin', async () => {
      withActiveCommand({
        ...defaultCommand,
        status: 'failed',
        error_code: 'agent_disconnected',
      })
      const { unmount } = renderWithProviders(<Agents />)
      expect(await screen.findByText('Scan failed')).toBeInTheDocument()
      expect(
        screen.getByText(/stopped responding while the scan was running/i),
      ).toBeInTheDocument()
      expect(screen.getByTestId('agents-retry')).toBeInTheDocument()
      expect(screen.queryByText('agent_disconnected')).not.toBeInTheDocument()
      expect(
        screen.queryByText(/never picked up the scan/i),
      ).not.toBeInTheDocument()
      unmount()

      withActiveCommand({ ...defaultCommand, status: 'expired' })
      renderWithProviders(<Agents />)
      expect(await screen.findByText('Not picked up')).toBeInTheDocument()
      expect(screen.getByText(/never picked up the scan/i)).toBeInTheDocument()
      expect(
        screen.queryByText(/stopped responding while the scan was running/i),
      ).not.toBeInTheDocument()
      expect(screen.getByTestId('agents-retry')).toBeInTheDocument()
    })

    it('uses the approved failed copy and never exposes a refusal code', async () => {
      withActiveCommand({
        ...defaultCommand,
        status: 'failed',
        error_code: 'device_offline',
      })
      renderWithProviders(<Agents />)

      expect(await screen.findByText('Scan failed')).toBeInTheDocument()
      expect(
        screen.getByText(
          "The Pi wasn't connected when the scan was requested. Check that it's powered on and online, then try again.",
        ),
      ).toBeInTheDocument()
      expect(screen.queryByText('device_offline')).not.toBeInTheDocument()
    })

    it('does not expose a scan link when done has no scan id', async () => {
      withActiveCommand({
        ...defaultCommand,
        status: 'done',
        scan_id: null,
        completed_at: new Date().toISOString(),
      })
      renderWithProviders(<Agents />)

      expect(await screen.findByText('Done')).toBeInTheDocument()
      expect(screen.queryByTestId('agents-view-scan')).not.toBeInTheDocument()
    })

    it('lets a viewer open a completed scan but omits every device action', async () => {
      signedInAs(viewerProfile)
      withActiveCommand({
        ...defaultCommand,
        status: 'done',
        completed_at: new Date().toISOString(),
      })
      renderWithProviders(<Agents />)

      expect(await screen.findByText('Done')).toBeInTheDocument()
      expect(screen.getByTestId('agents-view-scan')).toHaveAttribute(
        'href',
        `/scans/${defaultCommand.scan_id}`,
      )
      expect(
        screen.queryByTestId('agents-network-change'),
      ).not.toBeInTheDocument()
      expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
      expect(screen.queryByTestId('agents-retry')).not.toBeInTheDocument()
    })
  })

  describe('refusals', () => {
    it('adopts a busy command instead of showing an error', async () => {
      const user = userEvent.setup()
      const focusSpy = vi.spyOn(HTMLElement.prototype, 'focus')
      let detailReads = 0
      server.use(
        http.post(`${baseURL}/agents/:agentId/commands`, () =>
          HttpResponse.json(
            { error: { code: 'device_busy', message: 'busy' } },
            { status: 409 },
          ),
        ),
        http.get(`${baseURL}/agents/:agentId`, () => {
          detailReads += 1
          return HttpResponse.json({
            ...defaultAgent,
            active_command_id:
              detailReads === 1 ? null : defaultCommand.command_id,
          })
        }),
      )
      renderWithProviders(<Agents />)

      await user.click(await screen.findByTestId('agents-scan-now'))
      expect(await screen.findByText('Queued')).toBeInTheDocument()
      expect(screen.getByTestId('agents-command-status')).toHaveFocus()
      expect(
        focusSpy.mock.contexts.filter(
          (context) =>
            context instanceof HTMLElement &&
            context.dataset.testid === 'agents-command-status',
        ),
      ).toHaveLength(1)
      expect(await screen.findByTestId('toast')).toHaveTextContent(
        'That Pi is already scanning. Showing the scan in progress.',
      )
      expect(screen.queryByTestId('agents-error')).not.toBeInTheDocument()
    })

    it('reports a plain start failure when a busy Pi exposes no command to adopt', async () => {
      const user = userEvent.setup()
      commandRefused(409, 'device_busy')
      renderWithProviders(<Agents />)

      await user.click(await screen.findByTestId('agents-scan-now'))

      expect(await screen.findByTestId('toast')).toHaveTextContent(
        "Couldn't start the scan.",
      )
      expect(
        screen.queryByTestId('agents-command-status'),
      ).not.toBeInTheDocument()
      expect(screen.getByTestId('agents-scan-now')).toBeInTheDocument()
    })

    it('toasts an offline refusal and re-reads the visible agent state', async () => {
      const user = userEvent.setup()
      let detailReads = 0
      commandRefused(503, 'device_offline')
      server.use(
        http.get(`${baseURL}/agents/:agentId`, () => {
          detailReads += 1
          return HttpResponse.json({
            ...defaultAgent,
            online: detailReads === 1,
          })
        }),
      )
      renderWithProviders(<Agents />)

      const trigger = await screen.findByTestId('agents-scan-now')
      await user.click(trigger)

      expect(await screen.findByTestId('toast')).toHaveTextContent(
        'Pi seems to be offline.',
      )
      await waitFor(() =>
        expect(screen.getByTestId('agents-presence')).toHaveTextContent(
          'Offline',
        ),
      )
      expect(detailReads).toBeGreaterThan(1)
      expect(screen.queryByText('device_offline')).not.toBeInTheDocument()
      expect(screen.getByTestId('agents-scan-now')).toBe(trigger)
      expect(trigger).toHaveFocus()
      expect(
        screen.queryByTestId('agents-command-status'),
      ).not.toBeInTheDocument()
    })

    it('toasts a stale-network refusal, re-reads, and returns to the chooser', async () => {
      const user = userEvent.setup()
      let detailReads = 0
      commandRefused(422, 'subnet_not_reported')
      server.use(
        http.get(`${baseURL}/agents/:agentId`, () => {
          detailReads += 1
          return HttpResponse.json({
            ...defaultAgent,
            target_subnet:
              detailReads === 1 ? defaultAgent.target_subnet : null,
          })
        }),
      )
      renderWithProviders(<Agents />)

      await user.click(await screen.findByTestId('agents-scan-now'))

      expect(await screen.findByTestId('toast')).toHaveTextContent(
        "The Pi doesn't report that network any more. Pick the network to scan again.",
      )
      expect(await screen.findByTestId('agents-chooser')).toBeInTheDocument()
      expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
      await waitFor(() =>
        expect(screen.getByTestId('agents-network')).toHaveTextContent(
          'No network chosen yet.',
        ),
      )
      expect(screen.queryByText('subnet_not_reported')).not.toBeInTheDocument()
    })

    it('requires both the documented status and code for a refusal branch', async () => {
      const user = userEvent.setup()
      commandRefused(409, 'device_offline')
      renderWithProviders(<Agents />)

      await user.click(await screen.findByTestId('agents-scan-now'))

      expect(await screen.findByTestId('toast')).toHaveTextContent(
        "Couldn't start the scan.",
      )
      expect(
        screen.queryByText('Pi seems to be offline.'),
      ).not.toBeInTheDocument()
      expect(screen.queryByText('device_offline')).not.toBeInTheDocument()
    })
  })

  describe('retry', () => {
    it.each(['failed', 'expired'] as const)(
      'retries a %s command into a newly queued run',
      async (terminalStatus) => {
        const user = userEvent.setup()
        let postCount = 0
        server.use(
          http.post(`${baseURL}/agents/:agentId/commands`, () => {
            postCount += 1
            return HttpResponse.json(
              {
                command_id:
                  postCount === 1
                    ? defaultCommand.command_id
                    : 'new-command-id',
                scan_id: defaultCommand.scan_id,
                agent_id: defaultAgent.agent_id,
                status: 'queued' as const,
              },
              { status: 202 },
            )
          }),
          http.get(`${baseURL}/commands/:commandId`, ({ params }) =>
            HttpResponse.json({
              ...defaultCommand,
              command_id: String(params.commandId),
              status:
                params.commandId === 'new-command-id'
                  ? 'queued'
                  : terminalStatus,
            }),
          ),
        )
        renderWithProviders(<Agents />)

        await user.click(await screen.findByTestId('agents-scan-now'))
        expect(await screen.findByTestId('agents-retry')).toHaveTextContent(
          'Retry',
        )
        await user.click(screen.getByTestId('agents-retry'))

        expect(await screen.findByText('Queued')).toBeInTheDocument()
        expect(postCount).toBe(2)
      },
    )

    it('keeps the terminal command and Retry focus when a retry is refused', async () => {
      const user = userEvent.setup()
      commandRefused(503, 'device_offline')
      withActiveCommand({
        ...defaultCommand,
        status: 'failed',
        error_code: 'device_offline',
      })
      renderWithProviders(<Agents />)

      const retry = await screen.findByTestId('agents-retry')
      await user.click(retry)

      expect(await screen.findByTestId('toast')).toHaveTextContent(
        'Pi seems to be offline.',
      )
      expect(screen.getByText('Scan failed')).toBeInTheDocument()
      expect(screen.getByTestId('agents-retry')).toBe(retry)
      expect(retry).toHaveFocus()
      expect(screen.getByTestId('agents-command-status')).not.toHaveFocus()
    })

    it.each(['failed', 'expired'] as const)(
      'lets a retry own the new run while the agent cache still names an adopted %s command',
      async (terminalStatus) => {
        const user = userEvent.setup()
        const focusSpy = vi.spyOn(HTMLElement.prototype, 'focus')
        const newCommandId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'
        let newCommandReads = 0
        server.use(
          http.get(`${baseURL}/agents`, () =>
            HttpResponse.json({
              data: [
                {
                  ...defaultAgent,
                  active_command_id: defaultCommand.command_id,
                },
              ],
            }),
          ),
          http.get(`${baseURL}/agents/:agentId`, () =>
            HttpResponse.json({
              ...defaultAgent,
              active_command_id: defaultCommand.command_id,
            }),
          ),
          http.post(`${baseURL}/agents/:agentId/commands`, () =>
            HttpResponse.json(
              {
                command_id: newCommandId,
                scan_id: defaultCommand.scan_id,
                agent_id: defaultAgent.agent_id,
                status: 'queued' as const,
              },
              { status: 202 },
            ),
          ),
          http.get(`${baseURL}/commands/:commandId`, ({ params }) => {
            const commandId = String(params.commandId)
            if (commandId === newCommandId) newCommandReads += 1
            return HttpResponse.json({
              ...defaultCommand,
              command_id: commandId,
              status:
                commandId === newCommandId
                  ? ('queued' as const)
                  : terminalStatus,
            })
          }),
        )
        renderWithProviders(<Agents />)

        await user.click(await screen.findByTestId('agents-retry'))

        expect(await screen.findByText('Queued')).toBeInTheDocument()
        expect(newCommandReads).toBeGreaterThan(0)
        expect(screen.queryByTestId('agents-retry')).not.toBeInTheDocument()
        expect(screen.getByTestId('agents-command-status')).toHaveFocus()
        expect(
          focusSpy.mock.contexts.filter(
            (context) =>
              context instanceof HTMLElement &&
              context.dataset.testid === 'agents-command-status',
          ),
        ).toHaveLength(1)
      },
    )
  })

  describe('concurrency', () => {
    it('keeps the followed-command slot while the first GET is pending and cannot post twice', async () => {
      const user = userEvent.setup()
      const focusSpy = vi.spyOn(HTMLElement.prototype, 'focus')
      let postCount = 0
      let releaseCommand!: () => void
      const commandPending = new Promise<void>((resolve) => {
        releaseCommand = resolve
      })
      let commandReads = 0
      server.use(
        http.post(`${baseURL}/agents/:agentId/commands`, () => {
          postCount += 1
          return HttpResponse.json(
            {
              command_id: defaultCommand.command_id,
              scan_id: defaultCommand.scan_id,
              agent_id: defaultAgent.agent_id,
              status: 'queued' as const,
            },
            { status: 202 },
          )
        }),
        http.get(`${baseURL}/commands/:commandId`, async () => {
          await commandPending
          commandReads += 1
          return HttpResponse.json({
            ...defaultCommand,
            status: commandReads === 1 ? 'queued' : 'running',
          })
        }),
      )
      renderWithProviders(<Agents />)

      const trigger = await screen.findByTestId('agents-scan-now')
      await user.click(trigger)

      const status = await screen.findByTestId('agents-command-status')
      expect(status).toHaveTextContent('Starting…')
      expect(status).toHaveFocus()
      expect(status).toHaveAttribute('role', 'status')
      expect(status).toHaveAttribute('aria-live', 'polite')
      expect(status).toHaveAttribute('tabindex', '-1')
      expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
      expect(screen.queryByTestId('agents-retry')).not.toBeInTheDocument()
      expect(postCount).toBe(1)
      expect(
        focusSpy.mock.contexts.filter(
          (context) =>
            context instanceof HTMLElement &&
            context.dataset.testid === 'agents-command-status',
        ),
      ).toHaveLength(1)

      releaseCommand()
      expect(await screen.findByText('Queued')).toBeInTheDocument()
      expect(screen.getByTestId('agents-command-status')).toBe(status)
      expect(status).toHaveFocus()
      expect(
        focusSpy.mock.contexts.filter(
          (context) =>
            context instanceof HTMLElement &&
            context.dataset.testid === 'agents-command-status',
        ),
      ).toHaveLength(1)
      expect(postCount).toBe(1)

      focusManager.setFocused(false)
      fireEvent.focus(window)
      focusManager.setFocused(true)
      expect(await screen.findByText('Scanning…')).toBeInTheDocument()
      expect(screen.getByTestId('agents-command-status')).toBe(status)
      expect(status).toHaveFocus()
      expect(
        focusSpy.mock.contexts.filter(
          (context) =>
            context instanceof HTMLElement &&
            context.dataset.testid === 'agents-command-status',
        ),
      ).toHaveLength(1)
    })

    it('prevents a duplicate POST while the accepted action is still pending', async () => {
      const user = userEvent.setup()
      let postCount = 0
      let releasePost!: () => void
      const postPending = new Promise<void>((resolve) => {
        releasePost = resolve
      })
      server.use(
        http.post(`${baseURL}/agents/:agentId/commands`, async () => {
          postCount += 1
          await postPending
          return HttpResponse.json(
            {
              command_id: defaultCommand.command_id,
              scan_id: defaultCommand.scan_id,
              agent_id: defaultAgent.agent_id,
              status: 'queued' as const,
            },
            { status: 202 },
          )
        }),
      )
      renderWithProviders(<Agents />)

      const trigger = await screen.findByTestId('agents-scan-now')
      void user.click(trigger)
      await waitFor(() => expect(postCount).toBe(1))
      expect(trigger).toBeDisabled()

      fireEvent.click(trigger)
      expect(postCount).toBe(1)

      releasePost()
      expect(await screen.findByText('Queued')).toBeInTheDocument()
      expect(postCount).toBe(1)
    })
  })
})
