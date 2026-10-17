import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import ScanDetail from '@/pages/ScanDetail'
import {
  LANGUAGE_STORAGE_KEY,
  LanguageProvider,
  type Language,
} from '@/i18n/LanguageProvider'
import { SCAN_FAILURE_REASONS } from '@/lib/scanFailureReasons'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import LocationProbe from '@/test/LocationProbe'
import {
  awarenessExposure,
  relatedExposure,
  scanDetail,
  scanDetailFails,
  scanNotFound,
  withAssessment,
  withPartialResult,
  withoutAssessment,
} from '@/test/scansHarness'
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
  machine_type: 'storage',
  device_profile: null,
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
  machine_type: 'computer',
  device_profile: null,
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
    assessment_status: 'available',
    assessment_policy_version: '2026-09-15.1',
    exposures: [],
    error_code: null,
    ...overrides,
  }
}

function renderPage(route: string, state?: unknown, language: Language = 'en') {
  localStorage.setItem(LANGUAGE_STORAGE_KEY, language)
  return renderWithProviders(
    <LanguageProvider>
      <>
        <Routes>
          <Route path="/scans/:scanId" element={<ScanDetail />} />
        </Routes>
        <LocationProbe />
      </>
    </LanguageProvider>,
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
  it('groups service-targeted findings by severity and shows their source tool', async () => {
    const web = finding({
      finding_id: '44444444-aaaa-4aaa-8aaa-444444444444',
      severity: 'high',
      title: 'Exposed environment configuration',
      source: 'targeted_service_assessment',
      source_script: 'ffuf',
    })
    const ssl = finding({
      finding_id: '55555555-aaaa-4aaa-8aaa-555555555555',
      severity: 'medium',
      title: 'Weak TLS cipher',
      source: 'targeted_service_assessment',
      source_script: 'testssl.sh',
    })
    const smb = finding({
      finding_id: '66666666-aaaa-4aaa-8aaa-666666666666',
      severity: 'medium',
      title: 'SMB guest session is available',
      source: 'targeted_service_assessment',
      source_script: 'enum4linux-ng',
    })
    const tlsCritical = finding({
      finding_id: '77777777-aaaa-4aaa-8aaa-777777777777',
      severity: 'critical',
      title: 'TLS certificate trust issue',
      source: 'targeted_service_assessment',
      source_script: 'testssl.sh',
    })
    scanDetail(
      completedScan({
        scan_mode: 'extensive',
        findings: [phpCgiFinding, web, ssl, smb, tlsCritical],
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId(
      `findings-critical-row-${phpCgiFinding.finding_id}`,
    )

    expect(
      screen.getByRole('heading', { name: 'Targeted service findings: 4' }),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId(`targeted-high-row-${web.finding_id}`),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId(`targeted-medium-row-${ssl.finding_id}`),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId(`targeted-medium-row-${smb.finding_id}`),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId(`targeted-critical-row-${tlsCritical.finding_id}`),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId(`targeted-high-row-${web.finding_id}`),
    ).toHaveTextContent('Tool: ffuf')
    expect(
      screen.getByTestId(`targeted-medium-row-${ssl.finding_id}`),
    ).toHaveTextContent('Tool: testssl.sh')
    expect(
      screen.getByTestId(`findings-critical-row-${phpCgiFinding.finding_id}`),
    ).toBeInTheDocument()
    expect(
      screen.queryByTestId(`findings-high-row-${web.finding_id}`),
    ).toBeNull()
    expect(
      screen.queryByTestId(`findings-medium-row-${ssl.finding_id}`),
    ).toBeNull()
    expect(
      screen.queryByTestId(`findings-medium-row-${smb.finding_id}`),
    ).toBeNull()
  })

  it('localizes the service-targeted findings section in Brazilian Portuguese', async () => {
    const web = finding({
      finding_id: '44444444-aaaa-4aaa-8aaa-444444444444',
      severity: 'medium',
      title: 'Exposed environment configuration',
      source: 'targeted_service_assessment',
      source_script: 'ffuf',
    })
    scanDetail(completedScan({ scan_mode: 'extensive', findings: [web] }))
    renderPage(`/scans/${SCAN_ID}`, undefined, 'pt-BR')

    expect(
      await screen.findByRole('heading', {
        name: 'Achados das ferramentas por serviço: 1',
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', {
        name: 'Alternar achados direcionados de gravidade média',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('Ferramenta: ffuf')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Vulnerabilidade' })).toBeInTheDocument()
    expect(
      screen.getAllByRole('columnheader', { name: 'Equipamento' }).length,
    ).toBeGreaterThan(0)
  })

  it('opens the targeted section for a ?finding= deep link', async () => {
    const user = userEvent.setup()
    const web = finding({
      finding_id: '44444444-aaaa-4aaa-8aaa-444444444444',
      severity: 'high',
      title: 'Exposed environment configuration',
      source: 'targeted_service_assessment',
      source_script: 'ffuf',
    })
    scanDetail(
      completedScan({
        scan_mode: 'extensive',
        findings: [phpCgiFinding, web],
      }),
    )
    renderPage(`/scans/${SCAN_ID}?finding=${web.finding_id}`)

    const panel = await screen.findByTestId(`finding-panel-${web.finding_id}`)
    expect(panel).toBeVisible()
    expect(
      screen.queryByTestId(`finding-panel-${phpCgiFinding.finding_id}`),
    ).not.toBeInTheDocument()

    const trigger = screen.getByRole('button', {
      name: 'Toggle targeted service findings',
    })
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    await user.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })

  it('keeps the severity section open after closing its deep-linked finding', async () => {
    const user = userEvent.setup()
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}?finding=${phpCgiFinding.finding_id}`)

    await screen.findByTestId(`finding-panel-${phpCgiFinding.finding_id}`)
    const trigger = screen.getByRole('button', {
      name: 'Toggle critical vulnerabilities',
    })
    expect(trigger).toHaveAttribute('aria-expanded', 'true')

    await user.click(
      screen.getByTestId(`findings-critical-caret-${phpCgiFinding.finding_id}`),
    )

    expect(
      screen.queryByTestId(`finding-panel-${phpCgiFinding.finding_id}`),
    ).not.toBeInTheDocument()
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByTestId('findings-critical')).toBeVisible()
  })

  it('does not describe absent targeted findings as clean coverage', async () => {
    scanDetail(
      completedScan({
        scan_mode: 'extensive',
        findings: [phpCgiFinding],
        metadata: { targeted_units_planned: 0 },
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId(
      `findings-critical-row-${phpCgiFinding.finding_id}`,
    )

    expect(screen.getByTestId('scan-no-targeted-findings')).toHaveTextContent(
      'This does not confirm that every planned tool check ran.',
    )
  })

  it('shows unlisted omitted checks and observation evidence in coverage', async () => {
    scanDetail(
      completedScan({
        metadata: { targeted_units_omitted_unlisted: 4 },
        coverage: [
          {
            ip: '192.168.1.10',
            stage: 'targeted_assessment',
            port: 80,
            protocol: 'tcp',
            tool: 'nikto',
            outcome: 'completed',
            evidence_source: 'targeted_tool',
            issue_keys: [],
            observations: [
              {
                observation_key: 'web:administration:/admin',
                kind: 'administration',
                summary: 'Administration interface found',
                evidence: 'status=403; protected surface',
                path: '/admin',
                rule_id: 'ADMIN',
                policy_version: 'v1',
              },
            ],
          },
        ],
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    const coverage = await screen.findByTestId('scan-coverage')
    expect(coverage).toHaveTextContent(
      '4 additional omitted checks are not listed individually.',
    )
    expect(coverage).toHaveTextContent('status=403; protected surface')
  })

  it('shows the unlisted omission count when no individual units were stored', async () => {
    scanDetail(
      completedScan({
        metadata: { targeted_units_omitted_unlisted: 2 },
        coverage: [],
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    const coverage = await screen.findByTestId('scan-coverage')
    expect(coverage).toHaveTextContent(
      '2 additional omitted checks are not listed individually.',
    )
    expect(coverage).toHaveTextContent(
      'Check coverage was not recorded for this scan.',
    )
  })

  it('shows the targeted section when targeted_units_planned is zero', async () => {
    scanDetail(
      completedScan({
        findings: [phpCgiFinding],
        metadata: { targeted_units_planned: 0 },
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId(
      `findings-critical-row-${phpCgiFinding.finding_id}`,
    )

    expect(
      screen.getByRole('heading', { name: 'Targeted service findings: 0' }),
    ).toBeInTheDocument()
    expect(screen.getByTestId('scan-no-targeted-findings')).toBeInTheDocument()
    expect(screen.queryByTestId('findings-high')).not.toBeInTheDocument()
  })

  it('starts severity groups collapsed and opens one on demand', async () => {
    const user = userEvent.setup()
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`)

    const criticalToggle = await screen.findByRole('button', {
      name: 'Toggle critical vulnerabilities',
    })
    expect(criticalToggle).toHaveAttribute('aria-expanded', 'false')
    expect(criticalToggle).toHaveAttribute('data-state', 'closed')

    await user.click(criticalToggle)
    expect(criticalToggle).toHaveAttribute('aria-expanded', 'true')
    expect(criticalToggle).toHaveAttribute('data-state', 'open')
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
      'Vulnerabilities: 4',
      'Critical: 1 vulnerability',
      'High: 1 vulnerability',
      'Medium: 1 vulnerability',
      'Low: 1 vulnerability',
      'Attack surface',
      'Machines seen',
      'Check coverage',
    ])
    expect(screen.queryByTestId('findings-table')).not.toBeInTheDocument()
  })

  it('opens one vulnerabilities card before revealing the severity cards', async () => {
    const user = userEvent.setup()
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`)

    const vulnerabilitiesToggle = await screen.findByRole('button', {
      name: 'Toggle scan vulnerabilities',
    })
    expect(vulnerabilitiesToggle).toHaveAttribute('aria-expanded', 'false')

    await user.click(vulnerabilitiesToggle)

    expect(vulnerabilitiesToggle).toHaveAttribute('aria-expanded', 'true')
    expect(
      screen.getByRole('button', { name: 'Toggle critical vulnerabilities' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Toggle high vulnerabilities' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Toggle medium vulnerabilities' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Toggle low vulnerabilities' }),
    ).toBeInTheDocument()
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
      screen.getByRole('heading', { name: 'Critical: 1 vulnerability' }),
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

  it('shows a stopped notice without AI or findings when the scan was cancelled', async () => {
    scanDetail(
      completedScan({
        status: 'cancelled',
        findings: [],
        hosts: [],
        finding_count: 0,
        host_count: 0,
        duration: null,
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    const stopped = await screen.findByTestId('scan-stopped')
    expect(within(stopped).getByText('Stopped').tagName).toBe('P')
    expect(stopped).toHaveTextContent(
      'This scan was stopped before the Pi sent any results.',
    )
    expect(screen.queryByTestId(/^scan-ai-/)).not.toBeInTheDocument()
    expectNoScanTables()
    expect(screen.queryByTestId('scan-reports')).not.toBeInTheDocument()

    const strip = screen.getByTestId('scan-summary-strip')
    expect(strip).not.toHaveTextContent('Machines seen')
    expect(strip).not.toHaveTextContent('Vulnerabilities')
  })

  it('keeps partial results and AI for a completed user-cancel scan', async () => {
    server.use(
      http.get('http://localhost:8000/api/v1/scans/:scanId/analysis', () =>
        HttpResponse.json({
          scan_id: SCAN_ID,
          status: 'not_requested',
        }),
      ),
    )
    scanDetail(
      withPartialResult(
        completedScan({ findings: [phpCgiFinding], finding_count: 1 }),
        'user_cancel',
      ),
    )
    renderPage(`/scans/${SCAN_ID}`)

    const notice = await screen.findByTestId('scan-stopped-early')
    expect(notice).toHaveTextContent('Stopped early')
    expect(notice).toHaveTextContent(
      'This scan was stopped early. It shows what was found before the stop.',
    )
    expect(
      await screen.findByTestId(
        `findings-critical-row-${phpCgiFinding.finding_id}`,
      ),
    ).toBeInTheDocument()
    expect(screen.getByTestId('scan-hosts-table')).toBeInTheDocument()
    expect(screen.queryByTestId('scan-stopped')).not.toBeInTheDocument()
    expect(
      await screen.findByTestId('scan-ai-not-requested'),
    ).toBeInTheDocument()

    const strip = screen.getByTestId('scan-summary-strip')
    expect(strip).toHaveTextContent('Machines seen')
    expect(strip).toHaveTextContent('Vulnerabilities')
  })

  it('hides the stopped-early notice for plain completed and timeout/error partials', async () => {
    scanDetail(completedScan())
    const view = renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId(
      `findings-critical-row-${phpCgiFinding.finding_id}`,
    )
    expect(screen.queryByTestId('scan-stopped-early')).not.toBeInTheDocument()
    expect(screen.queryByText('Stopped early')).not.toBeInTheDocument()

    view.unmount()
    scanDetail(withPartialResult(completedScan(), 'timeout'))
    const timeoutView = renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId(
      `findings-critical-row-${phpCgiFinding.finding_id}`,
    )
    expect(screen.queryByTestId('scan-stopped-early')).not.toBeInTheDocument()
    expect(screen.queryByText('Stopped early')).not.toBeInTheDocument()

    timeoutView.unmount()
    scanDetail(withPartialResult(completedScan(), 'error'))
    renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId(
      `findings-critical-row-${phpCgiFinding.finding_id}`,
    )
    expect(screen.queryByTestId('scan-stopped-early')).not.toBeInTheDocument()
    expect(screen.queryByText('Stopped early')).not.toBeInTheDocument()
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
    expect(screen.queryByTestId('scan-reports')).not.toBeInTheDocument()
  })

  it('shows the report action in the scan summary strip once the scan has finished', async () => {
    scanDetail(completedScan())
    renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId(
      `findings-critical-row-${phpCgiFinding.finding_id}`,
    )
    const summary = screen.getByTestId('scan-assessment-summary')
    expect(within(summary).getByTestId('scan-reports')).toBeInTheDocument()
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

  it('reports no confirmed vulnerabilities without claiming the scan is clean', async () => {
    scanDetail(
      completedScan({
        findings: [],
        finding_count: 0,
        hosts: [
          {
            ...nas,
            operating_system: {
              name: 'Linux 2.6.9 - 2.6.33',
              accuracy: 100,
              cpes: [],
            },
          },
        ],
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    expect(await screen.findByTestId('scan-no-findings')).toHaveTextContent(
      'No confirmed vulnerabilities were found in this scan.',
    )
    expect(screen.queryByTestId('findings-critical')).not.toBeInTheDocument()
    expect(screen.getByTestId('scan-hosts-table')).toBeInTheDocument()
    expect(
      screen.getByTestId(`scan-hosts-table-row-${NAS_HOST_ID}`),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId(`scan-hosts-table-row-${NAS_HOST_ID}`),
    ).toHaveTextContent('Linux 2.6.9 - 2.6.33')
  })

  it('keeps exposure attention separate and opens its related vulnerability', async () => {
    const user = userEvent.setup()
    scanDetail(
      withAssessment(
        completedScan({ findings: [phpCgiFinding], finding_count: 1 }),
        [relatedExposure, awarenessExposure],
      ),
    )
    renderPage(`/scans/${SCAN_ID}`)

    const summary = await screen.findByTestId('scan-assessment-summary')
    expect(summary).toHaveTextContent('2 reachable services · 1 needs review')
    expect(
      screen.getByText(
        'Expand a row to see evidence and vulnerabilities related to that service.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Endpoint' })).toBeInTheDocument()
    expect(
      screen.getByRole('columnheader', { name: 'Observed service' }),
    ).toBeInTheDocument()
    expect(summary).toHaveTextContent('Vulnerabilities1')
    expect(screen.getByText('Needs review')).toBeInTheDocument()
    expect(screen.getByText('For awareness')).toBeInTheDocument()
    expect(
      screen.getByTestId(
        `scan-exposures-table-row-${relatedExposure.exposure_id}`,
      ),
    ).toBeInTheDocument()

    const trigger = screen.getByRole('button', {
      name: 'Show details for https on 192.168.0.42:443/tcp',
    })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(trigger).toHaveAttribute('aria-controls')
    await user.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    const panel = screen.getByTestId(
      `scan-exposures-table-panel-${relatedExposure.exposure_id}`,
    )
    expect(panel).toHaveAttribute('id', trigger.getAttribute('aria-controls'))
    expect(
      within(panel)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['Nmap service: https', 'Nmap version: nginx 1.24'])

    await user.click(
      screen.getByTestId(
        `exposure-related-finding-${phpCgiFinding.finding_id}`,
      ),
    )
    expect(
      screen.getByTestId(`finding-panel-${phpCgiFinding.finding_id}`),
    ).toBeInTheDocument()
    expect(document.activeElement).toHaveAttribute(
      'data-testid',
      `findings-critical-caret-${phpCgiFinding.finding_id}`,
    )
  })

  it('localizes the attack surface table in Brazilian Portuguese', async () => {
    scanDetail(withAssessment(completedScan(), [relatedExposure]))
    renderPage(`/scans/${SCAN_ID}`, undefined, 'pt-BR')

    expect(
      await screen.findByText(
        'Expanda uma linha para ver as evidências e vulnerabilidades relacionadas ao serviço.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('columnheader', { name: 'Endereço e porta' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('columnheader', { name: 'Serviço identificado' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Administração')).toBeInTheDocument()
  })

  it('closes an exposure with Escape and returns focus to its trigger', async () => {
    const user = userEvent.setup()
    scanDetail(withAssessment(completedScan(), [relatedExposure]))
    renderPage(`/scans/${SCAN_ID}`)

    const trigger = await screen.findByRole('button', {
      name: 'Show details for https on 192.168.0.42:443/tcp',
    })
    await user.click(trigger)
    expect(
      screen.getByTestId(
        `scan-exposures-table-panel-${relatedExposure.exposure_id}`,
      ),
    ).toBeInTheDocument()

    await user.keyboard('{Escape}')

    expect(
      screen.queryByTestId(
        `scan-exposures-table-panel-${relatedExposure.exposure_id}`,
      ),
    ).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('distinguishes current empty assessment from legacy unavailable data', async () => {
    const current = completedScan({ findings: [], finding_count: 0 })
    scanDetail(withAssessment(current))
    const view = renderPage(`/scans/${SCAN_ID}`)

    expect(await screen.findByTestId('scan-no-exposures')).toHaveTextContent(
      'No reachable services were found in this scan.',
    )
    expect(
      screen.queryByTestId('scan-assessment-unavailable'),
    ).not.toBeInTheDocument()

    view.unmount()
    scanDetail(withoutAssessment(current))
    renderPage(`/scans/${SCAN_ID}`)

    expect(
      await screen.findByTestId('scan-assessment-unavailable'),
    ).toHaveTextContent('Unavailable')
    expect(screen.queryByTestId('scan-no-exposures')).not.toBeInTheDocument()
  })

  it('counts open and filtered ports separately for each machine', async () => {
    scanDetail(
      completedScan({
        hosts: [
          {
            ...nas,
            ports: [
              ...nas.ports,
              {
                port: 445,
                protocol: 'tcp',
                state: 'filtered',
                service: 'microsoft-ds',
              },
            ],
          },
        ],
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    expect(
      await screen.findByTestId(`scan-hosts-table-row-${NAS_HOST_ID}`),
    ).toHaveTextContent('Open ports: 1, Filtered ports: 1')
  })

  it('shows partial coverage and keeps the no-findings copy honest', async () => {
    const completedPartial = withPartialResult(
      completedScan({ findings: [], finding_count: 0 }),
      'completed',
    )
    completedPartial.metadata = {
      ...completedPartial.metadata,
      targeted_units_planned: 19,
      targeted_units_completed: 5,
      targeted_units_failed: 0,
      targeted_units_timed_out: 1,
      targeted_units_skipped: 13,
    }
    completedPartial.targeted_coverage = [
      {
        tool: 'ffuf',
        completed: 0,
        failed: 0,
        timed_out: 0,
        skipped: 6,
        gaps: [{ reason: 'wordlist_unavailable', count: 6 }],
      },
      {
        tool: 'nikto',
        completed: 0,
        failed: 0,
        timed_out: 0,
        skipped: 6,
        gaps: [
          { reason: 'tool_unavailable', count: 4 },
          { reason: 'dependency_unavailable', count: 2 },
        ],
      },
    ]
    scanDetail(completedPartial)
    const view = renderPage(`/scans/${SCAN_ID}`)

    expect(await screen.findByTestId('scan-ai-unavailable')).toHaveTextContent(
      'AI summaries are disabled for this scan.',
    )
    expect(await screen.findByTestId('scan-no-findings')).toHaveTextContent(
      'No confirmed vulnerabilities in accepted evidence.',
    )
    const summary = await screen.findByTestId('scan-summary-strip')
    const warningButton = within(summary).getByRole('button', {
      name: 'Warning: partial scan',
    })
    expect(warningButton).toBeInTheDocument()
    await userEvent.setup().click(warningButton)
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    const notice = screen.getByTestId('scan-partial-notice')
    expect(notice).toHaveTextContent(
      '19 Planned, 5 Completed, 0 Failed, 1 Timed out, 13 Skipped',
    )
    expect(notice).toHaveTextContent('required wordlist is unavailable (6)')
    expect(notice).toHaveTextContent('tool is not installed or available (4)')
    expect(notice).toHaveTextContent('required dependency is unavailable (2)')
    expect(notice).toHaveTextContent('ffuf')
    expect(notice).toHaveTextContent('Skipped6')

    view.unmount()
    scanDetail(withPartialResult(completedScan(), 'timeout', 'deep_inspection'))
    renderPage(`/scans/${SCAN_ID}`)

    await screen.findByTestId(
      `findings-critical-row-${phpCgiFinding.finding_id}`,
    )
    expect(
      await screen.findByTestId('scan-partial-warning-trigger'),
    ).toBeInTheDocument()
  })

  it('does not call a scan clean when its completeness is unknown', async () => {
    scanDetail(
      completedScan({
        findings: [],
        finding_count: 0,
        evidence_completeness: 'unknown',
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    expect(await screen.findByTestId('scan-no-findings')).toHaveTextContent(
      'No confirmed vulnerabilities in accepted evidence.',
    )
  })

  it('keeps observations from a failed scan visible', async () => {
    scanDetail(
      completedScan({
        status: 'failed',
        error_code: 'device_offline',
        exposures: [relatedExposure],
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    const evidence = await screen.findByTestId('scan-failed-evidence')
    expect(evidence).toHaveTextContent(
      'Observations recorded before the scan failed',
    )
    expect(within(evidence).getByTestId('scan-hosts-table')).toBeInTheDocument()
    expect(
      within(evidence).getByTestId('scan-exposures-table'),
    ).toBeInTheDocument()
  })

  it('keeps loading and request errors free of false zero claims', async () => {
    server.use(
      http.get(
        'http://localhost:8000/api/v1/scans/:scanId',
        () => new Promise(() => {}),
      ),
    )
    const loading = renderPage(`/scans/${SCAN_ID}`)

    expect(screen.getByRole('heading', { name: 'Scan' })).toBeInTheDocument()
    expect(screen.getByLabelText('Loading scan')).toBeInTheDocument()
    expect(screen.queryByTestId('scan-no-exposures')).not.toBeInTheDocument()
    expect(screen.queryByTestId('scan-no-findings')).not.toBeInTheDocument()

    loading.unmount()
    scanDetailFails()
    renderPage(`/scans/${SCAN_ID}`)

    expect(
      await screen.findByText("Couldn't load this scan."),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('scan-no-exposures')).not.toBeInTheDocument()
    expect(screen.queryByTestId('scan-no-findings')).not.toBeInTheDocument()
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

  it('shows unknown live counters and an indeterminate bar before the first report', async () => {
    scanDetail(
      completedScan({
        status: 'processing',
        progress: null,
        hosts: [],
        findings: [],
        host_count: 0,
        finding_count: 0,
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    const notice = await screen.findByTestId('scan-unfinished')
    expect(notice).toHaveTextContent('Machines—')
    expect(notice).toHaveTextContent('Open ports—')
    expect(notice).toHaveTextContent('Vulnerabilities—')
    expect(screen.getByTestId('scan-progress')).not.toHaveTextContent('%')
    expect(screen.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow')
  })

  it('renders live stage, percentage, and confirmed zero counts', async () => {
    scanDetail(
      completedScan({
        status: 'processing',
        progress: {
          stage: 'ports',
          percent: 35,
          machines: 3,
          open_ports: 0,
          filtered_ports: 2,
          industrial_services: 0,
          vulnerabilities: null,
          updated_at: '2026-10-02T12:00:00Z',
        },
        hosts: [],
        findings: [],
        host_count: 0,
        finding_count: 0,
      }),
    )
    renderPage(`/scans/${SCAN_ID}`)

    const notice = await screen.findByTestId('scan-unfinished')
    expect(notice).toHaveTextContent('Machines3')
    expect(notice).toHaveTextContent('Open ports0')
    expect(notice).toHaveTextContent('Filtered ports2')
    expect(notice).toHaveTextContent('Vulnerabilities—')
    expect(screen.getByTestId('scan-progress')).toHaveTextContent('35%')
    expect(screen.getByTestId('scan-progress')).toHaveTextContent(
      'Checking ports',
    )
    expect(screen.getByRole('progressbar')).toHaveAttribute(
      'aria-valuenow',
      '35',
    )
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
    expect(screen.queryByTestId('scan-no-exposures')).not.toBeInTheDocument()
    expect(screen.queryByTestId('scan-no-findings')).not.toBeInTheDocument()
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
