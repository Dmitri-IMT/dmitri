import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import DataTable from '@/components/DataTable'
import {
  hostFindingColumns,
  scanFindingColumns,
} from '@/pages/scans/findingColumns'
import { criticalFinding, hostFixtures } from '@/test/mswHandlers'
import { renderWithProviders } from '@/test/renderWithProviders'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']
function renderScanColumns(finding: FindingRecord) {
  renderWithProviders(
    <DataTable
      columns={scanFindingColumns()}
      rows={[finding]}
      rowId={(row) => row.finding_id}
      testId="column-probe"
      caption="Column probe"
    />,
  )
}

function renderHostColumns(finding: FindingRecord) {
  renderWithProviders(
    <DataTable
      columns={hostFindingColumns()}
      rows={[finding]}
      rowId={(row) => row.finding_id}
      testId="column-probe"
      caption="Column probe"
    />,
  )
}

function machineCell(row: HTMLElement) {
  return within(row).getAllByRole('cell')[1]
}

function hostFirstSeenCell(row: HTMLElement) {
  return within(row).getAllByRole('cell')[3]
}

describe('scanFindingColumns', () => {
  it("names the machine by finding.host_hostname, the machine's current name", async () => {
    renderScanColumns({
      ...criticalFinding,
      host_id: hostFixtures[0].host_id,
      host_hostname: 'Office PC',
      host_ip: '192.168.0.17',
    })

    const row = await screen.findByTestId(
      `column-probe-row-${criticalFinding.finding_id}`,
    )
    expect(machineCell(row)).toHaveTextContent('Office PC')
  })

  it('falls back to finding.host_ip when the machine has no name', async () => {
    renderScanColumns({
      ...criticalFinding,
      host_id: hostFixtures[0].host_id,
      host_hostname: '',
      host_ip: '10.0.0.5',
    })

    const row = await screen.findByTestId(
      `column-probe-row-${criticalFinding.finding_id}`,
    )
    expect(machineCell(row)).toHaveTextContent('10.0.0.5')
  })

  it('reads Confirmed only for a demonstrated vulnerability', async () => {
    renderScanColumns({ ...criticalFinding, demonstrated: true })

    const row = await screen.findByTestId(
      `column-probe-row-${criticalFinding.finding_id}`,
    )
    expect(within(row).getAllByRole('cell')[2]).toHaveTextContent('Confirmed')
  })

  it('reads Unverified for any other vulnerability', async () => {
    renderScanColumns(criticalFinding)

    const row = await screen.findByTestId(
      `column-probe-row-${criticalFinding.finding_id}`,
    )
    expect(within(row).getAllByRole('cell')[2]).toHaveTextContent('Unverified')
  })
})

describe('hostFindingColumns', () => {
  it('renders First seen from first_seen_at', async () => {
    renderHostColumns(criticalFinding)

    expect(
      screen.getByRole('columnheader', { name: 'First seen' }),
    ).toBeInTheDocument()

    const row = await screen.findByTestId(
      `column-probe-row-${criticalFinding.finding_id}`,
    )
    const time = within(hostFirstSeenCell(row)).getByRole('time')
    expect(time).toHaveAttribute('datetime', criticalFinding.first_seen_at)
  })
})
