import { afterEach, describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { http, HttpResponse } from 'msw'
import { focusManager } from '@tanstack/react-query'
import DeviceDetail from '@/pages/DeviceDetail'
import { agentDetail, withActiveCommand } from '@/test/agentsHarness'
import {
  defaultAgent,
  defaultCommand,
  latestSuccessfulScan,
  viewerProfile,
} from '@/test/mswHandlers'
import { renderWithProviders } from '@/test/renderWithProviders'
import { signedInAs } from '@/test/usersHarness'
import { SCAN_MODE_DESCRIPTION } from '@/lib/scanModes'
import { server } from '@/test/setup'
import { baseURL } from '@/test/scansHarness'
import type { components } from '@/types/openapi'

type ScanSummary = components['schemas']['ScanSummary']
type ScanListResponse = components['schemas']['ScanListResponse']

const agentRoute = `/devices/${defaultAgent.agent_id}`

function renderDeviceDetail(route = agentRoute) {
  return renderWithProviders(
    <Routes>
      <Route path="/devices" element={<div data-testid="devices-list" />} />
      <Route path="/devices/:agentId" element={<DeviceDetail />} />
    </Routes>,
    { route },
  )
}

afterEach(() => {
  focusManager.setFocused(undefined)
})

describe('DeviceDetail', () => {
  it('A box owns its settings', async () => {
    renderDeviceDetail()

    expect(await screen.findByTestId('agents-network')).toHaveTextContent(
      '192.168.0.0/24 (eth0)',
    )
    expect(screen.getByTestId('agents-network-change')).toBeInTheDocument()
    expect(screen.getByTestId('scan-type-tabs')).toBeInTheDocument()
    expect(screen.getByTestId('agents-scan-now')).toBeInTheDocument()
  })

  it('Scan type never persists by accident', async () => {
    const user = userEvent.setup()
    renderDeviceDetail()

    const maxTab = await screen.findByTestId('scan-type-tab-max')
    await user.click(maxTab)
    expect(screen.getByTestId('scan-type-description')).toHaveTextContent(
      SCAN_MODE_DESCRIPTION.max,
    )

    await user.click(screen.getByTestId('device-detail-back'))
    expect(await screen.findByTestId('devices-list')).toBeInTheDocument()

    renderDeviceDetail()
    const standardTab = await screen.findByTestId('scan-type-tab-standard')
    expect(standardTab).toHaveAttribute('data-state', 'active')
    expect(screen.getByTestId('scan-type-description')).toHaveTextContent(
      SCAN_MODE_DESCRIPTION.standard,
    )
  })

  it('No default is claimed', async () => {
    renderDeviceDetail()

    await screen.findByTestId('scan-type-tabs')
    expect(screen.queryByText(/daily scan uses/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/use this scan type/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/stored default/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/default scan/i)).not.toBeInTheDocument()
  })

  it('Viewers cannot configure a box', async () => {
    signedInAs(viewerProfile)
    renderDeviceDetail()

    expect(await screen.findByTestId('agents-network')).toHaveTextContent(
      '192.168.0.0/24 (eth0)',
    )
    expect(screen.getByTestId('scan-type-readonly')).toBeInTheDocument()
    expect(screen.getByText('Standard')).toBeInTheDocument()
    expect(
      screen.queryByTestId('agents-network-change'),
    ).not.toBeInTheDocument()
    expect(screen.queryByTestId('scan-type-tabs')).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
  })

  it('Scanning is unavailable without a network', async () => {
    agentDetail({ ...defaultAgent, target_subnet: null })
    renderDeviceDetail()

    expect(await screen.findByTestId('agents-chooser')).toBeInTheDocument()
    expect(screen.queryByTestId('scan-type-tabs')).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
  })

  it('A running scan reports where it started', async () => {
    const user = userEvent.setup()
    renderDeviceDetail()

    await user.click(await screen.findByTestId('agents-scan-now'))

    const status = await screen.findByTestId('agents-command-status')
    expect(status).toHaveFocus()
    expect(status).toHaveAttribute('role', 'status')
    expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
    expect(within(status).getByTestId('agents-status')).toBeInTheDocument()
  })

  it('opens the tab strip on Standard', async () => {
    renderDeviceDetail()

    const standardTab = await screen.findByTestId('scan-type-tab-standard')
    expect(standardTab).toHaveAttribute('data-state', 'active')
    expect(screen.getByTestId('scan-type-description')).toHaveTextContent(
      SCAN_MODE_DESCRIPTION.standard,
    )
  })

  it('requires a reported network choice without free text', async () => {
    const user = userEvent.setup()
    agentDetail({ ...defaultAgent, target_subnet: null })
    renderDeviceDetail()

    expect(await screen.findByTestId('agents-chooser')).toBeInTheDocument()
    expect(
      screen.getByLabelText('Ethernet · 192.168.0.0/24'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()

    await user.click(
      screen.getByLabelText('Wi-Fi · 10.12.0.0/16 (internet connection)'),
    )
    await user.click(screen.getByTestId('agents-chooser-confirm'))

    expect(await screen.findByTestId('agents-scan-now')).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByTestId('agents-scan-now')).toHaveFocus(),
    )
    expect(screen.getByTestId('agents-network')).toHaveTextContent(
      '10.12.0.0/16 (wlan0)',
    )
  })

  it('shows a viewer the unchosen-network direction without device controls', async () => {
    signedInAs(viewerProfile)
    withActiveCommand(defaultCommand, {
      ...defaultAgent,
      target_subnet: null,
    })
    renderDeviceDetail()

    expect(await screen.findByTestId('agents-network')).toHaveTextContent(
      'No network chosen yet. Ask your admin to choose one.',
    )
    expect(screen.getByTestId('agents-command-status')).toBeInTheDocument()
    expect(screen.queryByTestId('agents-chooser')).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
  })

  it('hides scan controls while choosing a network', async () => {
    const user = userEvent.setup()
    renderDeviceDetail()

    await user.click(await screen.findByTestId('agents-network-change'))
    expect(screen.getByTestId('agents-chooser')).toBeInTheDocument()
    expect(screen.queryByTestId('scan-type-tabs')).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
  })

  it('shows empty scan history copy when this box has no scans', async () => {
    server.use(
      http.get(`${baseURL}/scans`, () =>
        HttpResponse.json({
          data: [],
          total: 0,
          page: 1,
        } satisfies ScanListResponse),
      ),
    )
    renderDeviceDetail()

    expect(
      await screen.findByTestId('device-scan-history-blank'),
    ).toHaveTextContent('No scans from this box yet.')
  })

  it('loads history for this box and lists When, Mode, Status, Duration', async () => {
    const requested: string[] = []
    const failed: ScanSummary = {
      ...latestSuccessfulScan,
      scan_id: '77777777-7777-4777-8777-777777777777',
      status: 'failed',
      duration: null,
      host_count: 0,
      finding_count: 0,
      highest_severity: null,
    }
    server.use(
      http.get(`${baseURL}/scans`, ({ request }) => {
        requested.push(new URL(request.url).searchParams.get('agent_id') ?? '')
        return HttpResponse.json({
          data: [latestSuccessfulScan, failed],
          total: 2,
          page: 1,
        } satisfies ScanListResponse)
      }),
    )
    renderDeviceDetail()

    const table = await screen.findByTestId('device-scan-history-table')
    await waitFor(() => {
      expect(requested).toContain(defaultAgent.agent_id)
    })
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((header) => header.textContent),
    ).toEqual(['When', 'Mode', 'Status', 'Duration'])
    const failedRow = screen.getByTestId(
      `device-scan-history-table-row-${failed.scan_id}`,
    )
    expect(within(failedRow).getAllByRole('cell')[3]).toHaveTextContent('—')
  })

  it('labels stopped, stopped-early, and completed rows in device history', async () => {
    const stoppedEarly: ScanSummary = {
      ...latestSuccessfulScan,
      scan_id: '66666666-6666-4666-8666-666666666666',
      terminated_by: 'user_cancel',
    }
    const cancelled: ScanSummary = {
      ...latestSuccessfulScan,
      scan_id: '44444444-4444-4444-8444-444444444444',
      status: 'cancelled',
      host_count: 0,
      finding_count: 0,
      highest_severity: null,
      duration: null,
      terminated_by: null,
    }
    const plainCompleted: ScanSummary = {
      ...latestSuccessfulScan,
      scan_id: '55555555-5555-4555-8555-555555555555',
      terminated_by: null,
    }
    const timeoutPartial: ScanSummary = {
      ...latestSuccessfulScan,
      scan_id: '33333333-3333-4333-8333-333333333334',
      terminated_by: 'timeout',
    }
    const errorPartial: ScanSummary = {
      ...latestSuccessfulScan,
      scan_id: '22222222-2222-4222-8222-222222222222',
      terminated_by: 'error',
    }
    server.use(
      http.get(`${baseURL}/scans`, () =>
        HttpResponse.json({
          data: [
            stoppedEarly,
            cancelled,
            plainCompleted,
            timeoutPartial,
            errorPartial,
          ],
          total: 5,
          page: 1,
        } satisfies ScanListResponse),
      ),
    )
    renderDeviceDetail()

    const stoppedEarlyRow = await screen.findByTestId(
      `device-scan-history-table-row-${stoppedEarly.scan_id}`,
    )
    expect(within(stoppedEarlyRow).getAllByRole('cell')[2]).toHaveTextContent(
      /^Stopped early$/,
    )
    const cancelledRow = screen.getByTestId(
      `device-scan-history-table-row-${cancelled.scan_id}`,
    )
    expect(within(cancelledRow).getAllByRole('cell')[2]).toHaveTextContent(
      /^Stopped$/,
    )
    const completedRow = screen.getByTestId(
      `device-scan-history-table-row-${plainCompleted.scan_id}`,
    )
    expect(within(completedRow).getAllByRole('cell')[2]).toHaveTextContent(
      /^Completed$/,
    )
    const timeoutRow = screen.getByTestId(
      `device-scan-history-table-row-${timeoutPartial.scan_id}`,
    )
    expect(within(timeoutRow).getAllByRole('cell')[2]).toHaveTextContent(
      /^Completed$/,
    )
    const errorRow = screen.getByTestId(
      `device-scan-history-table-row-${errorPartial.scan_id}`,
    )
    expect(within(errorRow).getAllByRole('cell')[2]).toHaveTextContent(
      /^Completed$/,
    )
  })

  it('names the scan history pagination for its own surface', async () => {
    server.use(
      http.get(`${baseURL}/scans`, () =>
        HttpResponse.json({
          data: [latestSuccessfulScan],
          total: 25,
          page: 1,
        } satisfies ScanListResponse),
      ),
    )
    renderDeviceDetail()

    expect(
      await screen.findByRole('navigation', { name: 'Scan pages' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('navigation', { name: 'Pagination' }),
    ).not.toBeInTheDocument()
  })
})
