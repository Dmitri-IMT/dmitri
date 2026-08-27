import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import ScanDetail from '@/pages/ScanDetail'
import { SCAN_FAILURE_REASONS } from '@/lib/scanFailureReasons'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import LocationProbe from '@/test/LocationProbe'
import { scanDetail, scanNotFound } from '@/test/scansHarness'
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
}

const phpCgiFinding: FindingRecord = {
  ...criticalFinding,
  finding_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  scan_id: SCAN_ID,
  host_id: NAS_HOST_ID,
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

function renderPage(route: string) {
  return renderWithProviders(
    <>
      <Routes>
        <Route path="/scans/:scanId" element={<ScanDetail />} />
      </Routes>
      <LocationProbe />
    </>,
    { route },
  )
}

function expectNoScanTables() {
  expect(screen.queryByTestId('findings-table')).not.toBeInTheDocument()
  expect(screen.queryByTestId('scan-hosts-table')).not.toBeInTheDocument()
}

describe('ScanDetail', () => {
  it('renders findings worst-first from a shuffled payload', async () => {
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId(`findings-table-row-${phpCgiFinding.finding_id}`)

    expect(
      screen
        .getAllByTestId(/^findings-table-row-/)
        .map((row) => row.getAttribute('data-testid')),
    ).toEqual([
      `findings-table-row-${phpCgiFinding.finding_id}`,
      'findings-table-row-33333333-aaaa-4aaa-8aaa-333333333333',
      'findings-table-row-22222222-aaaa-4aaa-8aaa-222222222222',
      'findings-table-row-11111111-aaaa-4aaa-8aaa-111111111111',
    ])
  })

  it('opens a finding in place without changing the route', async () => {
    const user = userEvent.setup()
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId(`findings-table-row-${phpCgiFinding.finding_id}`)
    expect(
      screen.queryByTestId(`finding-panel-${phpCgiFinding.finding_id}`),
    ).not.toBeInTheDocument()

    await user.click(
      screen.getByTestId(`findings-table-row-${phpCgiFinding.finding_id}`),
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

    await screen.findByTestId(`findings-table-row-${phpCgiFinding.finding_id}`)
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

    expect(await screen.findByTestId('scan-failed')).toHaveTextContent(
      "This scan didn't finish.",
    )
    expect(screen.getByTestId('scan-failed-reason')).toHaveTextContent(
      SCAN_FAILURE_REASONS.device_offline,
    )
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
      'No findings. Every host in this scan came back clean.',
    )
    expect(screen.queryByTestId('findings-table')).not.toBeInTheDocument()
    expect(screen.getByTestId('scan-hosts-table')).toBeInTheDocument()
    expect(
      screen.getByTestId(`scan-hosts-table-row-${NAS_HOST_ID}`),
    ).toBeInTheDocument()
  })

  it('says a processing scan is still running, re-reads on Check again, and does not poll', async () => {
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
      "Findings appear here when it finishes. This page doesn't update on its own.",
    )
    expectNoScanTables()

    payload = finished
    await user.click(screen.getByTestId('scan-unfinished-check'))

    expect(
      await screen.findByTestId(
        `findings-table-row-${phpCgiFinding.finding_id}`,
      ),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('scan-unfinished')).not.toBeInTheDocument()
  })

  it('opens host ports in place and the host link navigates to that host', async () => {
    const user = userEvent.setup()
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId(`scan-hosts-table-row-${NAS_HOST_ID}`)
    await user.click(screen.getByTestId(`scan-hosts-table-row-${NAS_HOST_ID}`))

    const ports = screen.getByTestId(`host-ports-panel-${NAS_HOST_ID}`)
    expect(ports).toHaveTextContent('443')
    expect(ports).toHaveTextContent('https')
    expect(
      screen.getByRole('link', { name: 'Open synology-nas' }),
    ).toHaveAttribute('href', `/hosts/${NAS_HOST_ID}`)
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/scans/${SCAN_ID}`,
    )

    await user.click(screen.getByTestId(`scan-hosts-open-${NAS_HOST_ID}`))

    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/hosts/${NAS_HOST_ID}`,
    )
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
})
