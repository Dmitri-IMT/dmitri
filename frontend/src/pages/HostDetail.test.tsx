import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import HostDetail from '@/pages/HostDetail'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import LocationProbe from '@/test/LocationProbe'
import {
  baseURL,
  confidentHostProfile,
  hostDetail,
  hostExposure,
  hostNotFound,
  withHostAssessment,
} from '@/test/hostsHarness'
import {
  criticalFinding,
  findingFixtures,
  hostDetailFixtures,
  latestSuccessfulScan,
} from '@/test/mswHandlers'

const DAY_MS = 24 * 60 * 60 * 1000
const WEEK_MS = 7 * DAY_MS
const HOST = hostDetailFixtures[0]
const HOST_WITH_PORTS = hostDetailFixtures[1]
const UNNAMED_HOST = hostDetailFixtures[24]
const OTHER_HOST_FINDING = findingFixtures[2]
const SCAN_ID = latestSuccessfulScan.scan_id

function renderPage(route: string, state?: unknown) {
  return renderWithProviders(
    <>
      <Routes>
        <Route path="/network/:hostId" element={<HostDetail />} />
      </Routes>
      <LocationProbe />
    </>,
    { route, state },
  )
}

function agoIso(ms: number): string {
  return new Date(Date.now() - ms).toISOString()
}

function metaHost(overrides: Partial<typeof HOST_WITH_PORTS>) {
  return { ...HOST_WITH_PORTS, ...overrides }
}

function expectPageError() {
  expect(screen.getByTestId('host-detail-error')).toHaveTextContent(
    "Couldn't load this machine.",
  )
  expect(screen.getByTestId('host-detail-error-retry')).toHaveTextContent(
    'Retry',
  )
  expect(screen.getByRole('button', { name: 'Retry' })).toBeEnabled()
  expect(screen.queryByTestId('host-findings-table')).not.toBeInTheDocument()
  expect(screen.queryByTestId('host-ports-table')).not.toBeInTheDocument()
  expect(screen.queryByTestId('host-history-table')).not.toBeInTheDocument()
}

describe('HostDetail', () => {
  it('presents the assessed profile and attack surface before vulnerabilities without replacing observed identity', async () => {
    const host = withHostAssessment(HOST_WITH_PORTS, {
      operating_system: {
        name: 'Linux 2.6.9 - 2.6.33',
        accuracy: 100,
        cpes: [],
      },
    })
    hostDetail(host, [])
    renderPage(`/network/${host.host_id}`)

    const profile = await screen.findByTestId('host-profile')
    expect(profile).toHaveTextContent('Likely typeTV')
    expect(profile).toHaveTextContent('ManufacturerSamsung')
    expect(profile).toHaveTextContent('Product familySmart TV')
    expect(profile).toHaveTextContent('ModelUnknown')
    expect(profile).toHaveTextContent('Profile confidenceHigh')
    expect(screen.getByTestId('host-operating-system')).toHaveTextContent(
      'Linux 2.6.9 - 2.6.33',
    )
    expect(
      screen.getByTestId('host-operating-system-accuracy'),
    ).toHaveTextContent('100%')
    expect(screen.getByTestId('host-detail-meta')).toHaveTextContent(
      host.vendor,
    )
    expect(
      screen
        .getAllByRole('heading', { level: 2 })
        .map((heading) => heading.textContent),
    ).toEqual([
      'Machine profile',
      'Attack surface',
      'Ask about Machine',
      'Vulnerabilities',
      'Ports observed on this machine',
      'Industrial services',
      'Scan history',
      'Delete this machine',
    ])
    expect(screen.getByTestId('host-exposures-table')).toBeInTheDocument()
  })

  it('reveals profile evidence in stored order with conflicts and randomized-MAC limitations', async () => {
    const user = userEvent.setup()
    const host = withHostAssessment(HOST_WITH_PORTS, {
      machine_type: 'unknown',
      device_profile: {
        ...confidentHostProfile,
        manufacturer: null,
        product_family: null,
        confidence: 'low',
        conflicts: ['The service label conflicts with protocol evidence.'],
        limitations: [
          'Locally administered MAC address; OUI manufacturer unavailable.',
        ],
      },
    })
    hostDetail(host, [])
    renderPage(`/network/${host.host_id}`)

    await user.click(await screen.findByTestId('host-profile-evidence'))
    const profile = screen.getByTestId('host-profile')
    expect(profile).toHaveTextContent('Likely typeUnknown')
    expect(profile).toHaveTextContent('ManufacturerUnknown')
    expect(profile).toHaveTextContent('Product familyUnknown')
    expect(profile).toHaveTextContent('ModelUnknown')
    expect(profile).not.toHaveTextContent(/IoT/i)
    const text = profile.textContent ?? ''
    expect(text.indexOf('Observed vendor: Samsung')).toBeLessThan(
      text.indexOf('8001/tcp: http'),
    )
    expect(screen.getByTestId('host-profile-conflicts')).toHaveTextContent(
      'Conflicting evidence: The service label conflicts with protocol evidence.',
    )
    expect(screen.getByTestId('host-profile-limitations')).toHaveTextContent(
      'Limitation: Locally administered MAC address; OUI manufacturer unavailable.',
    )
  })

  it('distinguishes current empty assessment data from legacy unavailable data', async () => {
    const current = withHostAssessment(HOST_WITH_PORTS, { exposures: [] })
    hostDetail(current, [])
    const { unmount } = renderPage(`/network/${current.host_id}`)

    expect(await screen.findByTestId('host-no-exposures')).toHaveTextContent(
      'No reachable services were found on this machine.',
    )
    expect(
      screen.queryByTestId('host-exposures-unavailable'),
    ).not.toBeInTheDocument()
    unmount()

    hostDetail(HOST, [])
    renderPage(`/network/${HOST.host_id}`)
    expect(
      await screen.findByTestId('host-profile-unavailable'),
    ).toHaveTextContent('Unavailable')
    expect(screen.getByTestId('host-operating-system')).toHaveTextContent(
      'Unknown',
    )
    expect(screen.getByTestId('host-exposures-unavailable')).toHaveTextContent(
      'Unavailable',
    )
    expect(screen.getByTestId('host-detail')).toHaveTextContent(HOST.ip)
  })

  it('shows the detected operating system when device profiling is unavailable', async () => {
    hostDetail(
      {
        ...HOST,
        operating_system: {
          name: 'Linux 2.6.9 - 2.6.33',
          accuracy: 100,
          cpes: [],
        },
      },
      [],
    )
    renderPage(`/network/${HOST.host_id}`)

    expect(
      await screen.findByTestId('host-operating-system'),
    ).toHaveTextContent('Linux 2.6.9 - 2.6.33')
    expect(
      screen.getByTestId('host-operating-system-accuracy'),
    ).toHaveTextContent('100%')
  })

  it('navigates a related exposure vulnerability to its scan and finding', async () => {
    const user = userEvent.setup()
    const exposure = hostExposure(HOST_WITH_PORTS, {
      related_finding_ids: [criticalFinding.finding_id],
    })
    const host = withHostAssessment(HOST_WITH_PORTS, { exposures: [exposure] })
    hostDetail(host, [])
    renderPage(`/network/${host.host_id}`)

    await user.click(
      await screen.findByRole('button', {
        name: `Show details for ${exposure.observed_service} on ${exposure.ip}:${exposure.port}/${exposure.protocol}`,
      }),
    )
    expect(
      screen.getByTestId(`host-exposures-table-row-${exposure.exposure_id}`),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId(`host-exposures-table-panel-${exposure.exposure_id}`),
    ).toHaveTextContent(exposure.reason)
    const relatedLink = screen.getByTestId(
      `exposure-related-finding-${criticalFinding.finding_id}`,
    )
    expect(relatedLink).toHaveAttribute(
      'href',
      `/scans/${exposure.scan_id}?finding=${criticalFinding.finding_id}`,
    )
    await user.click(relatedLink)
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/scans/${exposure.scan_id}`,
    )
  })

  it("renders only this host's findings, identity, empty-ports copy, and history", async () => {
    hostDetail(HOST, findingFixtures)
    renderPage(`/network/${HOST.host_id}`)

    expect(await screen.findByTestId('host-detail-identity')).toHaveTextContent(
      HOST.hostname,
    )
    expect(screen.getByTestId('host-detail')).toHaveTextContent(HOST.ip)
    expect(
      await screen.findByTestId(
        `host-findings-table-row-${criticalFinding.finding_id}`,
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText(OTHER_HOST_FINDING.title)).not.toBeInTheDocument()
    expect(
      screen.queryByTestId(
        `host-findings-table-row-${OTHER_HOST_FINDING.finding_id}`,
      ),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId('host-no-ports')).toHaveTextContent(
      'No ports have been recorded for this machine.',
    )
    expect(
      screen.getByRole('heading', { name: 'Ports observed on this machine' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Scan history' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Industrial services' }),
    ).toBeInTheDocument()
    expect(screen.getByTestId('no-industrial-services')).toHaveTextContent(
      'No industrial services were detected',
    )
    expect(screen.queryByTestId('host-ports-table')).not.toBeInTheDocument()
    expect(
      screen.getByTestId(`host-history-table-row-${SCAN_ID}`),
    ).toBeInTheDocument()
  })

  it('adopts the vulnerability vocabulary on the network detail screen', async () => {
    hostDetail(HOST, findingFixtures)
    renderPage(`/network/${HOST.host_id}`)

    await screen.findByTestId(
      `host-findings-table-row-${criticalFinding.finding_id}`,
    )

    expect(
      screen.getByRole('heading', { name: 'Vulnerabilities' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('table', { name: 'Vulnerabilities on this machine' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('columnheader', { name: 'Vulnerability' }),
    ).toBeInTheDocument()
    expect(screen.queryAllByText(/finding/i)).toHaveLength(0)
  })

  it('shows First seen on the vulnerabilities table', async () => {
    hostDetail(HOST, findingFixtures)
    renderPage(`/network/${HOST.host_id}`)

    const table = await screen.findByTestId('host-findings-table')
    expect(
      within(table).getByRole('columnheader', { name: 'First seen' }),
    ).toBeInTheDocument()

    const row = await screen.findByTestId(
      `host-findings-table-row-${criticalFinding.finding_id}`,
    )
    expect(
      within(within(row).getAllByRole('cell')[3]).getByRole('time'),
    ).toHaveAttribute('datetime', criticalFinding.first_seen_at)
  })

  it('opens a finding panel with CVE, CVSS, and reference links', async () => {
    const user = userEvent.setup()
    hostDetail(HOST, findingFixtures)
    renderPage(`/network/${HOST.host_id}`)

    await screen.findByTestId(
      `host-findings-table-row-${criticalFinding.finding_id}`,
    )
    await user.click(
      screen.getByTestId(
        `host-findings-table-row-${criticalFinding.finding_id}`,
      ),
    )

    const panel = screen.getByTestId(
      `finding-panel-${criticalFinding.finding_id}`,
    )
    expect(panel).toHaveTextContent(criticalFinding.cve_id ?? '')
    expect(
      screen.getByTestId(`findings-panel-cvss-${criticalFinding.finding_id}`),
    ).toHaveTextContent('9.8')
    expect(
      screen.getByRole('link', { name: criticalFinding.references[0] }),
    ).toHaveAttribute('href', criticalFinding.references[0])
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/network/${HOST.host_id}`,
    )
  })

  it('shows API-filtered evidence totals before the host findings page', async () => {
    hostDetail(HOST, findingFixtures)
    server.use(
      http.get(`${baseURL}/findings`, () =>
        HttpResponse.json({
          data: [criticalFinding],
          total: 153,
          page: 1,
          evidence_summary: {
            scope: 'filtered_findings',
            total_records: 153,
            by_method: {
              version_correlation: 90,
              configuration_observation: 20,
              specific_check: 30,
              textual_reference: 5,
              unknown: 8,
            },
            by_confidence: {
              tentative: 28,
              probable: 50,
              confirmed: 60,
              unknown: 15,
            },
            conflicting_records: 4,
            demonstrated_records: 12,
          },
        }),
      ),
    )
    renderPage(`/network/${HOST.host_id}`)

    const summary = await screen.findByTestId('evidence-summary-filtered')
    const table = await screen.findByTestId('host-findings-table')
    expect(summary).toHaveTextContent('Vulnerability records153')
    expect(summary).toHaveTextContent('Filtered vulnerabilities')
    expect(summary).toHaveTextContent('Version association90')
    expect(summary).toHaveTextContent('Confirmed60')
    expect(
      summary.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).not.toBe(0)
  })

  it('renders an inert ports table when the host has open ports', async () => {
    hostDetail(HOST_WITH_PORTS, findingFixtures)
    renderPage(`/network/${HOST_WITH_PORTS.host_id}`)

    const table = await screen.findByTestId('host-ports-table')
    expect(
      screen.getByRole('table', { name: 'Ports observed on this machine' }),
    ).toBe(table)
    expect(screen.queryByTestId('host-no-ports')).not.toBeInTheDocument()
    for (const row of within(table).getAllByRole('row')) {
      expect(within(row).queryByRole('button')).not.toBeInTheDocument()
      expect(within(row).queryByRole('link')).not.toBeInTheDocument()
    }
  })

  it('navigates to the scan when a history row is activated', async () => {
    const user = userEvent.setup()
    hostDetail(HOST, findingFixtures)
    renderPage(`/network/${HOST.host_id}`)

    await screen.findByTestId(`host-history-table-row-${SCAN_ID}`)
    await user.click(
      within(screen.getByTestId(`host-history-table-row-${SCAN_ID}`)).getByRole(
        'link',
      ),
    )

    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/scans/${SCAN_ID}`,
    )
    expect(screen.getByTestId('location-state')).toHaveTextContent(
      `{"from":"/network/${HOST.host_id}"}`,
    )
  })

  it('sends Back to the network list by default', async () => {
    const user = userEvent.setup()
    hostDetail(HOST, findingFixtures)
    renderPage(`/network/${HOST.host_id}`)

    await screen.findByTestId('host-detail-identity')
    await user.click(screen.getByRole('link', { name: 'Back' }))
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/network')
  })

  it('sends Back to the screen that opened the machine', async () => {
    const user = userEvent.setup()
    hostDetail(HOST, findingFixtures)
    renderPage(`/network/${HOST.host_id}`, { from: `/scans/${SCAN_ID}` })

    await screen.findByTestId('host-detail-identity')
    await user.click(screen.getByRole('link', { name: 'Back' }))
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/scans/${SCAN_ID}`,
    )
  })

  it('shows the page error and Retry when the host read fails', async () => {
    server.use(
      http.get(
        `${baseURL}/hosts/:hostId`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    )
    renderPage(`/network/${HOST.host_id}`)

    await screen.findByTestId('host-detail-error')
    expectPageError()
  })

  it('keeps the page loading state free of false empty-result copy', () => {
    server.use(
      http.get(`${baseURL}/hosts/:hostId`, async () => {
        await new Promise(() => {})
        return HttpResponse.json(HOST)
      }),
    )
    renderPage(`/network/${HOST.host_id}`)

    expect(screen.getByRole('heading', { name: 'Machine' })).toBeInTheDocument()
    expect(screen.queryByTestId('host-profile')).not.toBeInTheDocument()
    expect(screen.queryByTestId('host-no-exposures')).not.toBeInTheDocument()
    expect(screen.queryByTestId('host-no-findings')).not.toBeInTheDocument()
    expect(screen.queryByText(/No reachable services/)).not.toBeInTheDocument()
    expect(
      screen.queryByText(/No confirmed vulnerabilities/),
    ).not.toBeInTheDocument()
  })

  it('keeps findings loading local while profile, attack surface, services, and history remain visible', async () => {
    const host = withHostAssessment(HOST_WITH_PORTS)
    hostDetail(host, [])
    server.use(
      http.get(`${baseURL}/findings`, async () => {
        await new Promise(() => {})
        return HttpResponse.json({ data: [], total: 0, page: 1 })
      }),
    )
    renderPage(`/network/${host.host_id}`)

    expect(await screen.findByTestId('host-profile')).toBeInTheDocument()
    expect(screen.getByTestId('host-exposures-table')).toBeInTheDocument()
    expect(screen.getByTestId('host-ports-table')).toBeInTheDocument()
    expect(
      screen.getByTestId(`host-history-table-row-${SCAN_ID}`),
    ).toBeInTheDocument()
    expect(screen.getByTestId('host-findings-table')).toBeInTheDocument()
    expect(screen.queryByTestId('host-no-findings')).not.toBeInTheDocument()
    expect(
      screen.queryByText(/No confirmed vulnerabilities/),
    ).not.toBeInTheDocument()
  })

  it('fails the findings section alone and keeps the rest of the host', async () => {
    hostDetail(HOST, findingFixtures)
    server.use(
      http.get(
        `${baseURL}/findings`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    )
    renderPage(`/network/${HOST.host_id}`)

    expect(await screen.findByTestId('host-findings-error')).toHaveTextContent(
      "Couldn't load this machine's vulnerabilities.",
    )
    expect(screen.getByTestId('host-findings-error-retry')).toHaveTextContent(
      'Retry',
    )
    expect(screen.queryByTestId('host-detail-error')).not.toBeInTheDocument()
    expect(screen.getByTestId('host-detail-identity')).toHaveTextContent(
      HOST.hostname,
    )
    expect(
      screen.getByRole('heading', { name: 'Ports observed on this machine' }),
    ).toBeInTheDocument()
    expect(screen.getByTestId('host-no-ports')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Scan history' }),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId(`host-history-table-row-${SCAN_ID}`),
    ).toBeInTheDocument()
  })

  it('retries the findings section without refetching the host', async () => {
    const user = userEvent.setup()
    let hostReads = 0
    let findingsReads = 0
    server.use(
      http.get(`${baseURL}/hosts/:hostId`, () => {
        hostReads += 1
        return HttpResponse.json(HOST)
      }),
      http.get(`${baseURL}/findings`, () => {
        findingsReads += 1
        return findingsReads === 1
          ? new HttpResponse(null, { status: 500 })
          : HttpResponse.json({
              data: [criticalFinding],
              total: 1,
              page: 1,
            })
      }),
    )
    renderPage(`/network/${HOST.host_id}`)

    await screen.findByTestId('host-findings-error')
    await user.click(screen.getByTestId('host-findings-error-retry'))

    expect(
      await screen.findByTestId(
        `host-findings-table-row-${criticalFinding.finding_id}`,
      ),
    ).toBeInTheDocument()
    expect(hostReads).toBe(1)
    expect(findingsReads).toBe(2)
  })

  it('renders the not-found line and Back to the network', async () => {
    const user = userEvent.setup()
    hostNotFound()
    renderPage(`/network/${HOST.host_id}`)

    expect(
      await screen.findByTestId('host-detail-not-found'),
    ).toHaveTextContent("That machine doesn't exist.")
    await user.click(screen.getByRole('link', { name: 'Back to the network' }))
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/network')
  })

  it('uses the IP as the title when hostname is empty', async () => {
    hostDetail(UNNAMED_HOST, [])
    renderPage(`/network/${UNNAMED_HOST.host_id}`)

    expect(await screen.findByTestId('host-detail-identity')).toHaveTextContent(
      UNNAMED_HOST.ip,
    )
    expect(screen.getByTestId('host-detail-identity')).not.toHaveTextContent(
      'host-',
    )
  })
  it('names the vendor, the machine type and the open-port count on the identity line', async () => {
    const host = metaHost({
      vendor: 'Hikvision',
      machine_type: 'camera',
      open_ports_count: 4,
    })
    hostDetail(host, [])
    renderPage(`/network/${host.host_id}`)

    expect(await screen.findByTestId('host-detail-meta')).toHaveTextContent(
      `${host.ip} · ${host.mac} · Hikvision · Camera · 4 open ports`,
    )
  })

  it('omits an unknown machine type from the identity line, separator and all', async () => {
    const host = metaHost({
      vendor: 'Espressif',
      machine_type: 'unknown',
      open_ports_count: 2,
    })
    hostDetail(host, [])
    renderPage(`/network/${host.host_id}`)

    const meta = await screen.findByTestId('host-detail-meta')
    expect(meta).toHaveTextContent(
      `${host.ip} · ${host.mac} · Espressif · 2 open ports`,
    )
    expect(meta).not.toHaveTextContent('—')
    expect(meta).not.toHaveTextContent(/unknown/i)
  })

  it.each([
    [0, 'no open ports'],
    [1, '1 open port'],
    [4, '4 open ports'],
  ])('phrases an open-port count of %i as "%s"', async (count, phrase) => {
    const host = metaHost({ open_ports_count: count })
    hostDetail(host, [])
    renderPage(`/network/${host.host_id}`)

    expect(await screen.findByTestId('host-detail-meta')).toHaveTextContent(
      new RegExp(`${phrase}$`),
    )
  })

  it('renders the detail header test ids from the design contract', async () => {
    hostDetail(HOST, findingFixtures)
    renderPage(`/network/${HOST.host_id}`)

    expect(await screen.findByTestId('host-detail-header')).toBeInTheDocument()
    expect(screen.getByTestId('host-detail-identity')).toBeInTheDocument()
    expect(screen.getByTestId('host-detail-meta')).toBeInTheDocument()
    expect(screen.getByTestId('host-detail-seen')).toBeInTheDocument()
  })

  it('reads a machine seen six days ago as last seen, not quiet', async () => {
    const host = metaHost({ last_seen_at: agoIso(6 * DAY_MS) })
    hostDetail(host, [])
    renderPage(`/network/${host.host_id}`)

    const seen = await screen.findByTestId('host-detail-seen')
    expect(seen).toHaveTextContent('last seen')
    expect(seen).not.toHaveTextContent(/not seen for/i)
  })

  it.each([
    [1, 'not seen for 1 week'],
    [3, 'not seen for 3 weeks'],
  ])('reads the quiet line at %i week(s) as "%s"', async (weeks, phrase) => {
    const host = metaHost({ last_seen_at: agoIso(weeks * WEEK_MS) })
    hostDetail(host, [])
    renderPage(`/network/${host.host_id}`)

    const seen = await screen.findByTestId('host-detail-seen')
    expect(seen).toHaveTextContent('First seen')
    expect(seen).toHaveTextContent(new RegExp(`${phrase}$`))
    expect(seen).not.toHaveTextContent('last seen')
  })

  it('distinguishes current, historical, and unverified port observations', async () => {
    const host = metaHost({
      last_seen_at: agoIso(5 * 60 * 1000),
      ports: [
        {
          port: 443,
          protocol: 'tcp',
          service: 'https',
          version: 'nginx 1.18.0',
          first_seen_at: agoIso(9 * WEEK_MS),
          last_seen_at: agoIso(5 * 60 * 1000),
          observed_in_latest_scan: true,
        },
        {
          port: 23,
          protocol: 'tcp',
          service: 'telnet',
          version: null,
          first_seen_at: agoIso(9 * WEEK_MS),
          last_seen_at: agoIso(3 * WEEK_MS),
          observed_in_latest_scan: false,
        },
        {
          port: 25,
          protocol: 'tcp',
          service: 'smtp',
          version: null,
          first_seen_at: agoIso(9 * WEEK_MS),
          last_seen_at: agoIso(3 * WEEK_MS),
          observed_in_latest_scan: null,
        },
      ],
    })
    hostDetail(host, [])
    renderPage(`/network/${host.host_id}`)

    const table = await screen.findByTestId('host-ports-table')
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((header) => header.textContent?.trim()),
    ).toEqual(['Service', 'Protocol', 'Version', 'Last seen'])

    const openRow = screen.getByTestId('host-ports-table-row-443/tcp')
    const closedRow = screen.getByTestId('host-ports-table-row-23/tcp')
    const unknownRow = screen.getByTestId('host-ports-table-row-25/tcp')
    expect(openRow).toHaveTextContent('Observed in latest scan')
    expect(closedRow).toHaveTextContent('Historical observation')
    expect(unknownRow).toHaveTextContent('Not verified in latest scan')
    expect(within(openRow).getAllByRole('cell')[3]).toHaveTextContent(/min ago/)
    expect(within(closedRow).getAllByRole('cell')[3]).toHaveTextContent(
      /^[A-Z][a-z]{2} \d{1,2}, \d{2}:\d{2}$/,
    )

    expect(closedRow).not.toHaveAttribute('data-tone')
    expect(closedRow).not.toHaveClass('line-through')
    expect(closedRow).not.toHaveClass('text-muted-foreground')
    expect(closedRow.className).toEqual(openRow.className)
  })

  it('left-aligns the scan history Services count with tabular figures', async () => {
    hostDetail(HOST, findingFixtures)
    renderPage(`/network/${HOST.host_id}`)

    await screen.findByTestId(`host-history-table-row-${SCAN_ID}`)
    const servicesHeader = screen.getByRole('columnheader', {
      name: 'Services',
    })
    expect(servicesHeader).not.toHaveClass('text-right')

    const servicesCell = within(
      screen.getByTestId(`host-history-table-row-${SCAN_ID}`),
    ).getAllByRole('cell')[2]
    const count = String(HOST.scan_history[0].open_ports_count)
    expect(within(servicesCell).getByText(count)).toHaveClass('tabular-nums')
    expect(servicesCell).not.toHaveClass('text-right')
  })
})
