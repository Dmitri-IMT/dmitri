import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import Devices from '@/pages/Devices'
import { noAgents } from '@/test/agentsHarness'
import { baseURL } from '@/test/agentsHarness'
import LocationProbe from '@/test/LocationProbe'
import { agentSummaries } from '@/test/mswHandlers'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/setup'

const onlineWithNetwork = agentSummaries[0]
const onlineWithoutNetwork = agentSummaries[1]
const offlineAgent = agentSummaries[2]

function tableHeaders() {
  return within(screen.getByTestId('devices-table'))
    .getAllByRole('columnheader')
    .map((header) => header.textContent)
}

function rowCells(agentId: string) {
  return within(
    screen.getByTestId(`devices-table-row-${agentId}`),
  ).getAllByRole('cell')
}

describe('Devices', () => {
  it('lists every box with its four columns', async () => {
    renderWithProviders(<Devices />, { route: '/devices' })

    for (const agent of agentSummaries) {
      await screen.findByTestId(`devices-table-row-${agent.agent_id}`)
    }

    expect(tableHeaders()).toEqual(['Box', 'Network', 'Status', 'Last report'])

    const firstCells = rowCells(onlineWithNetwork.agent_id)
    expect(firstCells[0]).toHaveTextContent(onlineWithNetwork.display_name)
    expect(firstCells[1]).toHaveTextContent(onlineWithNetwork.target_subnet!)
    expect(firstCells[2]).toHaveTextContent('Online')
    expect(firstCells[3]).toBeTruthy()

    const offlineCells = rowCells(offlineAgent.agent_id)
    expect(offlineCells[2]).toHaveTextContent('Offline')
    expect(
      screen.getByTestId(`devices-table-row-${offlineAgent.agent_id}`),
    ).toHaveAttribute('data-tone', 'muted')
  })

  it('shows muted copy when a box has no network chosen', async () => {
    renderWithProviders(<Devices />, { route: '/devices' })

    const networkCell = within(
      await screen.findByTestId(
        `devices-table-row-${onlineWithoutNetwork.agent_id}`,
      ),
    ).getAllByRole('cell')[1]

    expect(networkCell).toHaveTextContent('No network chosen yet')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('keeps an offline box in the list with a muted row', async () => {
    renderWithProviders(<Devices />, { route: '/devices' })

    const row = await screen.findByTestId(
      `devices-table-row-${offlineAgent.agent_id}`,
    )
    expect(row).toHaveAttribute('data-tone', 'muted')
    expect(within(row).getByText('Old office')).toBeInTheDocument()
    expect(within(row).getByText('Offline')).toBeInTheDocument()
  })

  it('distinguishes a revoked device from an offline device', async () => {
    const revokedAt = new Date().toISOString()
    server.use(
      http.get(`${baseURL}/agents`, () =>
        HttpResponse.json({
          data: [
            { ...onlineWithNetwork, online: true, revoked_at: revokedAt },
            offlineAgent,
          ],
        }),
      ),
    )
    renderWithProviders(<Devices />, { route: '/devices' })

    const revokedStatus = await screen.findByTestId(
      `devices-status-${onlineWithNetwork.agent_id}`,
    )
    expect(revokedStatus).toHaveTextContent('Revoked')
    expect(revokedStatus).toHaveClass('truncate')
    expect(revokedStatus).toHaveAttribute(
      'title',
      `Revoked ${new Date(revokedAt).toLocaleString()}`,
    )
    expect(
      screen.getByTestId(`devices-status-${offlineAgent.agent_id}`),
    ).toHaveTextContent('Offline')
    expect(
      screen.getByTestId(`devices-table-row-${onlineWithNetwork.agent_id}`),
    ).toHaveAttribute('data-tone', 'muted')
  })

  it('navigates to the box detail when a row is activated', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <>
        <Devices />
        <LocationProbe />
      </>,
      { route: '/devices' },
    )

    await screen.findByTestId(`devices-table-row-${onlineWithNetwork.agent_id}`)
    await user.click(
      screen.getByRole('link', {
        name: `Open ${onlineWithNetwork.display_name}`,
      }),
    )

    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/devices/${onlineWithNetwork.agent_id}`,
    )
  })

  it('does not expose scan controls on the list', async () => {
    renderWithProviders(<Devices />, { route: '/devices' })

    await screen.findByTestId(`devices-table-row-${onlineWithNetwork.agent_id}`)
    expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
    expect(
      screen.queryByTestId('agents-command-status'),
    ).not.toBeInTheDocument()
  })

  it('renders no trailing action column', async () => {
    renderWithProviders(<Devices />, { route: '/devices' })

    await screen.findByTestId(`devices-table-row-${onlineWithNetwork.agent_id}`)
    expect(tableHeaders()).toHaveLength(4)
    expect(
      screen.queryByRole('columnheader', { name: /action/i }),
    ).not.toBeInTheDocument()
  })

  it('renders the blank state when no boxes are connected', async () => {
    noAgents()
    renderWithProviders(<Devices />, { route: '/devices' })

    expect(await screen.findByTestId('devices-blank')).toHaveTextContent(
      'No box connected yet',
    )
    expect(screen.getByTestId('devices-blank-note')).toHaveTextContent(
      'Contact whoever installed Dmitri if you were expecting one.',
    )
    expect(screen.queryByTestId('devices-table')).not.toBeInTheDocument()
  })

  it('renders an error with a working retry', async () => {
    const user = userEvent.setup()
    let failed = true
    server.use(
      http.get(`${baseURL}/agents`, () => {
        if (failed) {
          failed = false
          return new HttpResponse(null, { status: 500 })
        }
        return HttpResponse.json({ data: agentSummaries })
      }),
    )
    renderWithProviders(<Devices />, { route: '/devices' })

    expect(await screen.findByTestId('devices-error')).toHaveTextContent(
      "Couldn't load your devices.",
    )
    expect(screen.queryByTestId('devices-table')).not.toBeInTheDocument()

    await user.click(screen.getByTestId('devices-error-retry'))

    expect(
      await screen.findByTestId(
        `devices-table-row-${onlineWithNetwork.agent_id}`,
      ),
    ).toBeInTheDocument()
  })
})
