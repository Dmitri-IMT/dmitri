import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import HostDetail from '@/pages/HostDetail'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import LocationProbe from '@/test/LocationProbe'
import { baseURL, hostDetail, hostNotFound } from '@/test/hostsHarness'
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
      'No services are running on this machine.',
    )
    expect(
      screen.getByRole('heading', { name: 'Services running on this machine' }),
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

  it('renders an inert ports table when the host has open ports', async () => {
    hostDetail(HOST_WITH_PORTS, findingFixtures)
    renderPage(`/network/${HOST_WITH_PORTS.host_id}`)

    const table = await screen.findByTestId('host-ports-table')
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
      screen.getByRole('heading', { name: 'Services running on this machine' }),
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

  it('tells a service last seen before the machine apart by its date alone', async () => {
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
        },
        {
          port: 23,
          protocol: 'tcp',
          service: 'telnet',
          version: null,
          first_seen_at: agoIso(9 * WEEK_MS),
          last_seen_at: agoIso(3 * WEEK_MS),
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
    expect(within(openRow).getAllByRole('cell')[3]).toHaveTextContent(/min ago/)
    expect(within(closedRow).getAllByRole('cell')[3]).toHaveTextContent(
      /^[A-Z][a-z]{2} \d{1,2}, \d{2}:\d{2}$/,
    )

    expect(closedRow).not.toHaveTextContent(
      /closed|inactive|stale|gone|no longer|not seen/i,
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
