import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { focusManager } from '@tanstack/react-query'
import { COMMAND_POLL_INTERVAL_MS } from '@/api/commands'
import { renderWithProviders } from '@/test/renderWithProviders'
import { baseURL } from '@/test/agentsHarness'
import { defaultAgent, defaultCommand } from '@/test/mswHandlers'
import { server } from '@/test/setup'
import HostFindings from './hosts/HostFindings'
import Agents from './Agents'
import Hosts from './Hosts'
import Scans from './Scans'

afterEach(() => {
  focusManager.setFocused(undefined)
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('Agents command cache invalidation', () => {
  it('refreshes each completed-product family once and does not repeat the done sweep', async () => {
    vi.useFakeTimers()
    let commandReads = 0
    let agentDetailReads = 0
    let scanReads = 0
    let hostReads = 0
    let findingReads = 0
    server.use(
      http.get(`${baseURL}/agents`, () =>
        HttpResponse.json({
          data: [
            { ...defaultAgent, active_command_id: defaultCommand.command_id },
          ],
        }),
      ),
      http.get(`${baseURL}/agents/:agentId`, () => {
        agentDetailReads += 1
        return HttpResponse.json({
          ...defaultAgent,
          active_command_id:
            agentDetailReads === 1 ? defaultCommand.command_id : null,
        })
      }),
      http.get(`${baseURL}/commands/:commandId`, () => {
        commandReads += 1
        const done = commandReads > 1
        return HttpResponse.json({
          ...defaultCommand,
          status: done ? ('done' as const) : ('queued' as const),
          completed_at: done ? new Date().toISOString() : null,
        })
      }),
      http.get(`${baseURL}/scans`, () => {
        scanReads += 1
        return HttpResponse.json({ data: [], total: 0, page: 1 })
      }),
      http.get(`${baseURL}/hosts`, () => {
        hostReads += 1
        return HttpResponse.json({ data: [], total: 0, page: 1 })
      }),
      http.get(`${baseURL}/findings`, () => {
        findingReads += 1
        return HttpResponse.json({ data: [], total: 0, page: 1 })
      }),
    )
    renderWithProviders(
      <>
        <Agents />
        <Scans />
        <Hosts />
        <HostFindings hostId="host-for-invalidation" />
      </>,
    )

    await vi.waitFor(() => {
      expect(screen.getByText('Queued')).toBeInTheDocument()
      expect(scanReads).toBe(1)
      expect(hostReads).toBe(1)
      expect(findingReads).toBe(1)
      expect(agentDetailReads).toBe(1)
    })
    await vi.advanceTimersByTimeAsync(COMMAND_POLL_INTERVAL_MS)
    await vi.waitFor(() => {
      expect(screen.getByText('Done')).toBeInTheDocument()
      expect(scanReads).toBe(2)
      expect(hostReads).toBe(2)
      expect(findingReads).toBe(2)
      expect(agentDetailReads).toBe(2)
    })

    await vi.advanceTimersByTimeAsync(COMMAND_POLL_INTERVAL_MS * 3)
    expect(commandReads).toBe(2)
    expect(scanReads).toBe(2)
    expect(hostReads).toBe(2)
    expect(findingReads).toBe(2)
    expect(agentDetailReads).toBe(2)
    expect(screen.getByTestId('agents-view-scan')).toHaveAttribute(
      'href',
      `/scans/${defaultCommand.scan_id}`,
    )
  })
})
