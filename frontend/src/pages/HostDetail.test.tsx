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
})
