import { afterEach, describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { focusManager } from '@tanstack/react-query'
import DeviceDetail from '@/pages/DeviceDetail'
import { agentDetail, withActiveCommand } from '@/test/agentsHarness'
import { defaultAgent, defaultCommand, viewerProfile } from '@/test/mswHandlers'
import { renderWithProviders } from '@/test/renderWithProviders'
import { signedInAs } from '@/test/usersHarness'
import { SCAN_MODE_DESCRIPTION } from '@/lib/scanModes'

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
})
