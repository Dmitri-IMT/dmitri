import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import ScanDetail from '@/pages/ScanDetail'
import { SCAN_FAILURE_REASONS } from '@/lib/scanFailureReasons'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import LocationProbe from '@/test/LocationProbe'
import { scanDetail, scanNotFound } from '@/test/scansHarness'
import { confirmedModbusService } from '@/test/industrialFixtures'
import {
  criticalFinding,
  hostFixtures,
  latestSuccessfulScan,
} from '@/test/mswHandlers'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']
type ScanDetailResponse = components['schemas']['ScanDetailResponse']
type ScanHostView = components['schemas']['ScanHostView']

const SCAN_ID = latestSuccessfulScan.scan_id
const UNKNOWN_FINDING_ID = 'ffffffff-ffff-4fff-8fff-ffffffffffff'
const NAS_HOST_ID = hostFixtures[1].host_id

const nas: ScanHostView = {
  host_id: NAS_HOST_ID,
  ip: '192.168.0.42',
  mac: '00:11:32:AA:BB:CC',
  hostname: 'synology-nas',
  vendor: 'Synology',
  ports: [
    {
      port: 443,
      protocol: 'tcp',
      state: 'open',
      service: 'https',
      version: 'nginx 1.24',
    },
  ],
  industrial_services: [],
  unreadable_fields: [],
}

const piLab: ScanHostView = {
  host_id: hostFixtures[0].host_id,
  ip: '192.168.0.17',
  mac: 'DC:A6:32:11:22:33',
  hostname: 'pi-lab',
  vendor: 'Raspberry Pi',
  ports: [
    {
      port: 22,
      protocol: 'tcp',
      state: 'open',
      service: 'ssh',
      version: 'OpenSSH 9.6',
    },
  ],
  industrial_services: [],
  unreadable_fields: [],
}

const phpCgiFinding: FindingRecord = {
  ...criticalFinding,
  finding_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  scan_id: SCAN_ID,
  host_id: NAS_HOST_ID,
  host_hostname: nas.hostname,
  host_ip: nas.ip,
  port: 443,
  protocol: 'tcp',
  service: 'php-cgi',
  cve_id: 'CVE-2024-4577',
  cvss_score: 9.8,
  severity: 'critical',
  title: 'PHP CGI argument injection',
  description: 'PHP running as CGI on synology-nas accepts crafted arguments.',
  recommendation: 'Update PHP to a patched 8.3 release.',
  evidence: 'PHP/8.1.2 CGI',
  references: ['https://nvd.nist.gov/vuln/detail/CVE-2024-4577'],
}

function finding(
  overrides: Partial<FindingRecord> &
    Pick<FindingRecord, 'finding_id' | 'severity' | 'title'>,
): FindingRecord {
  return {
    ...phpCgiFinding,
    host_id: NAS_HOST_ID,
    host_ip: nas.ip,
    ...overrides,
  }
}

const shuffledFindings: FindingRecord[] = [
  finding({
    finding_id: '11111111-aaaa-4aaa-8aaa-111111111111',
    severity: 'low',
    title: 'Telnet port open',
    cve_id: null,
    cvss_score: null,
  }),
  finding({
    finding_id: '22222222-aaaa-4aaa-8aaa-222222222222',
    severity: 'medium',
    title: 'TLS certificate expired',
    cve_id: null,
    cvss_score: 5.3,
  }),
  phpCgiFinding,
  finding({
    finding_id: '33333333-aaaa-4aaa-8aaa-333333333333',
    severity: 'high',
    title: 'Outdated OpenSSH',
    cve_id: 'CVE-2023-38408',
    cvss_score: 8.1,
  }),
]

function completedScan(
  overrides: Partial<ScanDetailResponse> = {},
): ScanDetailResponse {
  return {
    ...latestSuccessfulScan,
    scan_id: SCAN_ID,
    hosts: [nas, piLab],
    findings: shuffledFindings,
    finding_count: shuffledFindings.length,
    host_count: 2,
    error_code: null,
    ...overrides,
  }
}

function renderPage(route: string, state?: unknown) {
  return renderWithProviders(
    <>
      <Routes>
        <Route path="/scans/:scanId" element={<ScanDetail />} />
      </Routes>
      <LocationProbe />
    </>,
    { route, state },
  )
}

function expectNoScanTables() {
  for (const severity of ['critical', 'high', 'medium', 'low']) {
    expect(screen.queryByTestId(`findings-${severity}`)).not.toBeInTheDocument()
  }
  expect(screen.queryByTestId('scan-hosts-table')).not.toBeInTheDocument()
}

describe('ScanDetail', () => {
  it('starts severity groups collapsed and opens one on demand', async () => {
    const user = userEvent.setup()
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`)

    const criticalToggle = await screen.findByRole('button', {
      name: 'Toggle critical vulnerabilities',
    })
    expect(criticalToggle).toHaveAttribute('aria-expanded', 'false')

    await user.click(criticalToggle)
    expect(criticalToggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByTestId('findings-critical')).not.toHaveAttribute(
      'hidden',
    )
  })

  it('splits a shuffled payload into one table per severity, worst card first', async () => {
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId(
      `findings-critical-row-${phpCgiFinding.finding_id}`,
    )

    for (const [severity, findingId] of [
      ['critical', phpCgiFinding.finding_id],
      ['high', '33333333-aaaa-4aaa-8aaa-333333333333'],
      ['medium', '22222222-aaaa-4aaa-8aaa-222222222222'],
      ['low', '11111111-aaaa-4aaa-8aaa-111111111111'],
    ]) {
      const table = screen.getByTestId(`findings-${severity}`)
      expect(
        within(table)
          .getAllByRole('row')
          .slice(1)
          .map((row) => row.getAttribute('data-testid')),
      ).toEqual([`findings-${severity}-row-${findingId}`])
    }

    expect(
      screen
        .getAllByRole('heading', { level: 2 })
        .map((heading) => heading.textContent),
    ).toEqual([
      'Scan reports',
      'Critical',
      'High',
      'Medium',
      'Low',
      'Machines seen',
    ])
    expect(screen.queryByTestId('findings-table')).not.toBeInTheDocument()
  })

  it('renders the summary strip, and drops the counts a failed scan cannot know', async () => {
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`)

    const strip = await screen.findByTestId('scan-summary-strip')
    expect(strip).toHaveTextContent('Mode')
    expect(strip).toHaveTextContent('Standard')
    expect(strip).toHaveTextContent('Network')
    expect(strip).toHaveTextContent(latestSuccessfulScan.subnet)
    expect(strip).toHaveTextContent('Machines seen')
    expect(strip).toHaveTextContent('Vulnerabilities')
    expect(strip).toHaveTextContent('Duration')
    expect(screen.getByTestId('scan-summary-duration')).toHaveTextContent(
      '8 min',
    )
  })

  it('shows confirmed industrial services without calling them vulnerabilities', async () => {
    scanDetail(
      completedScan({
        hosts: [
          nas,
          { ...piLab, industrial_services: [confirmedModbusService] },
        ],
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    const industrial = await screen.findByTestId('scan-industrial-services')
    expect(industrial).toHaveTextContent(piLab.hostname)
    expect(industrial).toHaveTextContent(piLab.ip)
    expect(industrial).toHaveTextContent('Modbus TCP · port 502')
    expect(industrial).toHaveTextContent('Schneider Electric')
    expect(
      screen.getByRole('heading', { name: 'Industrial services' }),
    ).toBeInTheDocument()
  })

  it('drops the unknowable counts from the strip on a failed scan', async () => {
    scanDetail(
      completedScan({
        status: 'failed',
        error_code: 'device_offline',
        findings: [],
        hosts: [],
        finding_count: 0,
        host_count: 0,
        duration: null,
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    const strip = await screen.findByTestId('scan-summary-strip')
    expect(strip).toHaveTextContent('Mode')
    expect(strip).toHaveTextContent('Network')
    expect(strip).not.toHaveTextContent('Machines seen')
    expect(strip).not.toHaveTextContent('Vulnerabilities')
    expect(strip).toHaveTextContent('Duration')
    expect(screen.getByTestId('scan-summary-duration')).toHaveTextContent('—')
  })

  it('keeps Duration in the strip on a running scan, as an em dash', async () => {
    scanDetail(
      completedScan({
        status: 'processing',
        findings: [],
        hosts: [],
        finding_count: 0,
        host_count: 0,
        duration: null,
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    const strip = await screen.findByTestId('scan-summary-strip')
    expect(strip).not.toHaveTextContent('Machines seen')
    expect(strip).toHaveTextContent('Duration')
    expect(screen.getByTestId('scan-summary-duration')).toHaveTextContent('—')
  })

  it('adopts the vulnerability vocabulary, with no reader-facing "finding"', async () => {
    const user = userEvent.setup()
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId(
      `findings-critical-row-${phpCgiFinding.finding_id}`,
    )

    expect(
      screen.getByRole('heading', { name: 'Critical' }),
    ).toBeInTheDocument()
    expect(
      screen.getAllByRole('columnheader', { name: 'Vulnerability' }),
    ).toHaveLength(4)
    expect(
      screen.getByRole('table', {
        name: 'critical vulnerabilities in this scan',
      }),
    ).toBeInTheDocument()
    expect(screen.queryAllByText(/finding/i)).toHaveLength(0)

    await user.click(
      screen.getByRole('button', {
        name: `Show details for ${phpCgiFinding.title}`,
      }),
    )

    await screen.findByTestId(`finding-panel-${phpCgiFinding.finding_id}`)
    expect(screen.queryAllByText(/finding/i)).toHaveLength(0)
  })

  it('opens a finding in place without changing the route', async () => {
    const user = userEvent.setup()
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId(
      `findings-critical-row-${phpCgiFinding.finding_id}`,
    )
    expect(
      screen.queryByTestId(`finding-panel-${phpCgiFinding.finding_id}`),
    ).not.toBeInTheDocument()

    await user.click(
      screen.getByRole('button', {
        name: `Show details for ${phpCgiFinding.title}`,
      }),
    )

    const panel = screen.getByTestId(
      `finding-panel-${phpCgiFinding.finding_id}`,
    )
    expect(panel).toHaveTextContent(phpCgiFinding.description)
    expect(panel).toHaveTextContent(phpCgiFinding.recommendation)
    expect(panel).toHaveTextContent(phpCgiFinding.evidence)
    expect(panel).toHaveTextContent(phpCgiFinding.references[0])
    expect(
      screen.getByTestId(`findings-panel-cvss-${phpCgiFinding.finding_id}`),
    ).toHaveTextContent('9.8')
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/scans/${SCAN_ID}`,
    )
  })

  it('opens a known ?finding= panel from the embedded scan without calling /findings', async () => {
    scanDetail(completedScan({ findings: [phpCgiFinding], finding_count: 1 }))
    renderPage(`/scans/${SCAN_ID}?finding=${phpCgiFinding.finding_id}`)

    const panel = await screen.findByTestId(
      `finding-panel-${phpCgiFinding.finding_id}`,
    )
    expect(panel).toHaveTextContent(phpCgiFinding.description)
    expect(panel).not.toHaveTextContent(criticalFinding.description)
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/scans/${SCAN_ID}`,
    )
  })

  it('renders nothing open when ?finding= is unknown', async () => {
    scanDetail(completedScan({ findings: [phpCgiFinding], finding_count: 1 }))
    renderPage(`/scans/${SCAN_ID}?finding=${UNKNOWN_FINDING_ID}`)

    await screen.findByTestId(
      `findings-critical-row-${phpCgiFinding.finding_id}`,
    )
    expect(
      screen.queryByTestId(`finding-panel-${phpCgiFinding.finding_id}`),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByTestId(`finding-panel-${UNKNOWN_FINDING_ID}`),
    ).not.toBeInTheDocument()
  })

  it('shows the device_offline sentence on a failed scan and hides both tables', async () => {
    scanDetail(
      completedScan({
        status: 'failed',
        error_code: 'device_offline',
        findings: [],
        hosts: [],
        finding_count: 0,
        host_count: 0,
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    const failed = await screen.findByTestId('scan-failed')
    expect(within(failed).getByText('Failed').tagName).toBe('P')
    expect(failed).toHaveTextContent("This scan didn't finish.")
    expect(screen.getByTestId('scan-failed-reason')).toHaveTextContent(
      SCAN_FAILURE_REASONS.device_offline,
    )
    expect(screen.queryByTestId(/pill/i)).not.toBeInTheDocument()
    expect(screen.getByTestId('scan-detail')).not.toHaveTextContent(
      'device_offline',
    )
    expectNoScanTables()
  })

  it('uses the unknown failure sentence when error_code is missing', async () => {
    scanDetail(
      completedScan({
        status: 'failed',
        error_code: null,
        findings: [],
        hosts: [],
        finding_count: 0,
        host_count: 0,
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    expect(await screen.findByTestId('scan-failed-reason')).toHaveTextContent(
      SCAN_FAILURE_REASONS.unknown,
    )
    expect(screen.getByTestId('scan-detail')).not.toHaveTextContent(
      'device_offline',
    )
    expectNoScanTables()
  })

  it('says the scan is clean when completed with no findings, and still shows hosts', async () => {
    scanDetail(
      completedScan({
        findings: [],
        finding_count: 0,
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    expect(await screen.findByTestId('scan-no-findings')).toHaveTextContent(
      'No vulnerabilities. Every machine in this scan came back clean.',
    )
    expect(screen.queryByTestId('findings-critical')).not.toBeInTheDocument()
    expect(screen.getByTestId('scan-hosts-table')).toBeInTheDocument()
    expect(
      screen.getByTestId(`scan-hosts-table-row-${NAS_HOST_ID}`),
    ).toBeInTheDocument()
  })

  it('shows live progress for a processing scan and re-reads on Check again', async () => {
    const user = userEvent.setup()
    const running = completedScan({
      status: 'processing',
      findings: [],
      finding_count: 0,
      host_count: 0,
    })
    const finished = completedScan()
    let payload: ScanDetailResponse = running
    server.use(
      http.get('http://localhost:8000/api/v1/scans/:scanId', () =>
        HttpResponse.json(payload),
      ),
    )
    renderPage(`/scans/${SCAN_ID}`)

    expect(await screen.findByTestId('scan-unfinished')).toHaveTextContent(
      'This scan is still running.',
    )
    expect(screen.getByTestId('scan-unfinished')).toHaveTextContent(
      'Progress updates automatically while the scan is running.',
    )
    expectNoScanTables()

    payload = finished
    await user.click(screen.getByTestId('scan-unfinished-check'))

    expect(
      await screen.findByTestId(
        `findings-critical-row-${phpCgiFinding.finding_id}`,
      ),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('scan-unfinished')).not.toBeInTheDocument()
  })

  it('sends a machines-seen row to that machine instead of expanding it', async () => {
    const user = userEvent.setup()
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`)

    const machineRow = await screen.findByTestId(
      `scan-hosts-table-row-${NAS_HOST_ID}`,
    )
    expect(
      screen.queryByTestId(`host-ports-panel-${NAS_HOST_ID}`),
    ).not.toBeInTheDocument()
    expect(machineRow).toHaveTextContent('1')

    await user.click(
      within(machineRow).getByRole('link', { name: 'Open synology-nas' }),
    )

    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/network/${NAS_HOST_ID}`,
    )
    expect(screen.getByTestId('location-state')).toHaveTextContent(
      `{"from":"/scans/${SCAN_ID}"}`,
    )
  })

  it('opens the machine when its name in a vulnerability row is activated', async () => {
    const user = userEvent.setup()
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`)

    const row = await screen.findByTestId(
      `findings-critical-row-${phpCgiFinding.finding_id}`,
    )
    expect(row).toHaveAttribute('data-row-action', 'expand')
    await user.click(within(row).getByRole('link', { name: nas.hostname }))

    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/network/${NAS_HOST_ID}`,
    )
    expect(
      screen.queryByTestId(`finding-panel-${phpCgiFinding.finding_id}`),
    ).not.toBeInTheDocument()
  })

  it('names the machine from host_hostname on the finding, not the scan snapshot', async () => {
    const renamedFinding: FindingRecord = {
      ...phpCgiFinding,
      host_hostname: 'Office PC',
    }
    scanDetail(
      completedScan({
        findings: [renamedFinding],
        finding_count: 1,
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    const row = await screen.findByTestId(
      `findings-critical-row-${renamedFinding.finding_id}`,
    )
    expect(within(row).getAllByRole('cell')[1]).toHaveTextContent('Office PC')
    expect(within(row).getAllByRole('cell')[1]).not.toHaveTextContent(
      nas.hostname,
    )
  })

  it('shows First seen on each vulnerability table', async () => {
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId(
      `findings-critical-row-${phpCgiFinding.finding_id}`,
    )

    for (const severity of ['critical', 'high', 'medium', 'low']) {
      const table = screen.getByTestId(`findings-${severity}`)
      expect(
        within(table).getByRole('columnheader', { name: 'First seen' }),
      ).toBeInTheDocument()
    }

    const row = screen.getByTestId(
      `findings-critical-row-${phpCgiFinding.finding_id}`,
    )
    expect(
      within(within(row).getAllByRole('cell')[4]).getByRole('time'),
    ).toHaveAttribute('datetime', phpCgiFinding.first_seen_at)
  })

  it('carries a Back link to the scans log', async () => {
    const user = userEvent.setup()
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId('scan-detail-header')
    await user.click(screen.getByRole('link', { name: 'Back' }))

    expect(screen.getByTestId('location-probe')).toHaveTextContent('/scans')
  })

  it('sends Back to the screen that opened the scan', async () => {
    const user = userEvent.setup()
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`, { from: '/' })

    await screen.findByTestId('scan-detail-header')
    await user.click(screen.getByRole('link', { name: 'Back' }))

    expect(screen.getByTestId('location-probe')).toHaveTextContent('/')
  })

  it('renders the not-found line and Back to scans', async () => {
    const user = userEvent.setup()
    scanNotFound()
    renderPage(`/scans/${SCAN_ID}`)

    expect(
      await screen.findByTestId('scan-detail-not-found'),
    ).toHaveTextContent("That scan doesn't exist.")
    await user.click(screen.getByRole('link', { name: 'Back to scans' }))
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/scans')
  })

  it('renders vulnerabilities and machines while analysis never resolves', async () => {
    server.use(
      http.get(
        'http://localhost:8000/api/v1/scans/:scanId/analysis',
        () => new Promise(() => {}),
      ),
    )
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId(
      `findings-critical-row-${phpCgiFinding.finding_id}`,
    )
    expect(screen.getByTestId('scan-hosts-table')).toBeInTheDocument()
  })
})
