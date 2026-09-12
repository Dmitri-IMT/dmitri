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
type ScanHostView = components['schemas']['ScanHostView']

const scanHost: ScanHostView = {
  host_id: hostFixtures[0].host_id,
  ip: '192.168.0.17',
  mac: 'DC:A6:32:11:22:33',
  hostname: 'pi-lab',
  vendor: 'Raspberry Pi',
  ports: [],
}

function renderScanColumns(
  finding: FindingRecord,
  hosts: ScanHostView[] = [scanHost],
) {
  renderWithProviders(
    <DataTable
      columns={scanFindingColumns(hosts)}
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

function scanFirstSeenCell(row: HTMLElement) {
  return within(row).getAllByRole('cell')[4]
}

function hostFirstSeenCell(row: HTMLElement) {
  return within(row).getAllByRole('cell')[3]
}

describe('scanFindingColumns', () => {
  it('prefers finding.host_hostname over the scan host snapshot', async () => {
    renderScanColumns({
      ...criticalFinding,
      host_id: scanHost.host_id,
      host_hostname: 'Office PC',
      host_ip: scanHost.ip,
    })

    const row = await screen.findByTestId(
      `column-probe-row-${criticalFinding.finding_id}`,
    )
    expect(machineCell(row)).toHaveTextContent('Office PC')
    expect(machineCell(row)).not.toHaveTextContent('pi-lab')
  })

  it('falls back to the scan host hostname, then its ip, then finding.host_ip', async () => {
    const unnamedHost: ScanHostView = { ...scanHost, hostname: '' }

    renderScanColumns(
      {
        ...criticalFinding,
        host_id: unnamedHost.host_id,
        host_hostname: null,
        host_ip: '10.0.0.5',
      },
      [unnamedHost],
    )

    const hostSnapshotRow = await screen.findByTestId(
      `column-probe-row-${criticalFinding.finding_id}`,
    )
    expect(machineCell(hostSnapshotRow)).toHaveTextContent('192.168.0.17')

    renderScanColumns({
      ...criticalFinding,
      finding_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      host_id: null,
      host_hostname: null,
      host_ip: '10.0.0.5',
    })

    const addressRow = await screen.findByTestId(
      'column-probe-row-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    )
    expect(machineCell(addressRow)).toHaveTextContent('10.0.0.5')
  })

  it('uses the scan host hostname when finding.host_hostname is absent', async () => {
    renderScanColumns({
      ...criticalFinding,
      host_id: scanHost.host_id,
      host_hostname: null,
      host_ip: scanHost.ip,
    })

    const row = await screen.findByTestId(
      `column-probe-row-${criticalFinding.finding_id}`,
    )
    expect(machineCell(row)).toHaveTextContent('pi-lab')
  })

  it('renders First seen from first_seen_at', async () => {
    renderScanColumns(criticalFinding)

    expect(
      screen.getByRole('columnheader', { name: 'First seen' }),
    ).toBeInTheDocument()

    const row = await screen.findByTestId(
      `column-probe-row-${criticalFinding.finding_id}`,
    )
    const time = within(scanFirstSeenCell(row)).getByRole('time')
    expect(time).toHaveAttribute('datetime', criticalFinding.first_seen_at)
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
