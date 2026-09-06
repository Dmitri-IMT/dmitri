import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import Scans from '@/pages/Scans'
import { SCAN_MODE_LABEL } from '@/lib/scanModes'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import LocationProbe from '@/test/LocationProbe'
import { baseURL } from '@/test/scansHarness'
import {
  adminProfile,
  latestScan,
  latestSuccessfulScan,
  scanFixtures,
  viewerProfile,
} from '@/test/mswHandlers'
import type { components } from '@/types/openapi'

type ScanSummary = components['schemas']['ScanSummary']
type ScanListResponse = components['schemas']['ScanListResponse']

const unfinishedScan: ScanSummary = {
  ...latestScan,
  host_count: 0,
  finding_count: 0,
  highest_severity: null,
}

const failedScan: ScanSummary = {
  ...latestScan,
  scan_id: '77777777-7777-4777-8777-777777777777',
  timestamp: latestSuccessfulScan.timestamp,
  status: 'failed',
  host_count: 0,
  finding_count: 0,
  highest_severity: null,
}

function overrideUser(profile: typeof adminProfile | typeof viewerProfile) {
  server.use(http.get(`${baseURL}/users/me`, () => HttpResponse.json(profile)))
}

const rowKinds: ScanSummary[] = [
  unfinishedScan,
  latestSuccessfulScan,
  failedScan,
]

function emptyList(): ScanListResponse {
  return { data: [], total: 0, page: 1 }
}

function scanList(
  rows: ScanSummary[],
  { requireNewestFirst = false }: { requireNewestFirst?: boolean } = {},
) {
  server.use(
    http.get(`${baseURL}/scans`, ({ request }) => {
      const params = new URL(request.url).searchParams
      if (
        requireNewestFirst &&
        (params.get('sort_by') !== 'timestamp' ||
          params.get('sort_order') !== 'desc')
      ) {
        return HttpResponse.json(emptyList())
      }
      return HttpResponse.json({
        data: rows,
        total: rows.length,
        page: 1,
      } satisfies ScanListResponse)
    }),
  )
}

function row(scanId: string) {
  return screen.getByTestId(`scans-table-row-${scanId}`)
}

function countCells(scanId: string) {
  const cells = within(row(scanId)).getAllByRole('cell')
  return { hosts: cells[5], findings: cells[6], highest: cells[7] }
}

function expectHiddenCounts(scanId: string) {
  const { hosts, findings, highest } = countCells(scanId)
  expect(hosts).toHaveTextContent('—')
  expect(findings).toHaveTextContent('—')
  expect(highest).toHaveTextContent('—')
  expect(hosts).not.toHaveTextContent('0')
  expect(findings).not.toHaveTextContent('0')
  expect(findings).not.toHaveTextContent('None')
  expect(highest).not.toHaveTextContent('None')
}

describe('Scans', () => {
  it('keeps column headings over skeleton rows while the list is loading', async () => {
    server.use(
      http.get(`${baseURL}/scans`, async () => {
        await delay('infinite')
        return HttpResponse.json(emptyList())
      }),
    )
    renderWithProviders(<Scans />, { route: '/scans' })

    const table = await screen.findByTestId('scans-table')
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((header) => header.textContent),
    ).toEqual([
      'When',
      'Box',
      'Mode',
      'Status',
      'Duration',
      'Machines',
      'Vulnerabilities',
      'Highest severity',
    ])
    expect(
      screen.queryByTestId(`scans-table-row-${latestScan.scan_id}`),
    ).not.toBeInTheDocument()
    expect(screen.queryByTestId('scans-loading')).not.toBeInTheDocument()
    expect(screen.queryByTestId('scans-blank')).not.toBeInTheDocument()
    expect(screen.queryByTestId('scans-error')).not.toBeInTheDocument()
  })

  it('renders the first-scan link for an admin blank state', async () => {
    overrideUser(adminProfile)
    scanList([])
    renderWithProviders(<Scans />, { route: '/scans' })

    const blank = await screen.findByTestId('scans-blank')
    expect(blank).toHaveTextContent('No scans yet')
    expect(blank).toHaveTextContent(
      'Your first scan finds the machines on your network and what needs fixing.',
    )
    expect(within(blank).getByTestId('first-scan-cta')).toHaveAttribute(
      'href',
      '/devices',
    )
    expect(
      within(blank).queryByTestId('first-scan-note'),
    ).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('renders only the admin-direction note for a viewer blank state', async () => {
    overrideUser(viewerProfile)
    scanList([])
    renderWithProviders(<Scans />, { route: '/scans' })

    const blank = await screen.findByTestId('scans-blank')
    expect(within(blank).getByTestId('first-scan-note')).toHaveTextContent(
      'Ask your admin to run the first scan.',
    )
    expect(
      within(blank).queryByTestId('first-scan-cta'),
    ).not.toBeInTheDocument()
    expect(within(blank).queryByRole('link')).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('renders the error copy, and Retry re-reads the list', async () => {
    const user = userEvent.setup()
    let failed = true
    server.use(
      http.get(`${baseURL}/scans`, () => {
        if (failed) {
          failed = false
          return new HttpResponse(null, { status: 500 })
        }
        return HttpResponse.json({
          data: [latestSuccessfulScan],
          total: 1,
          page: 1,
        } satisfies ScanListResponse)
      }),
    )
    renderWithProviders(<Scans />, { route: '/scans' })

    expect(await screen.findByTestId('scans-error')).toHaveTextContent(
      "Couldn't load the scans.",
    )
    expect(screen.queryByTestId('scans-table')).not.toBeInTheDocument()

    await user.click(screen.getByTestId('scans-error-retry'))

    expect(
      await screen.findByTestId(
        `scans-table-row-${latestSuccessfulScan.scan_id}`,
      ),
    ).toBeInTheDocument()
  })

  it('hides unfinished and failed counts, shows Completed as text, and requests newest-first order', async () => {
    scanList(rowKinds, { requireNewestFirst: true })
    renderWithProviders(<Scans />, { route: '/scans' })

    await screen.findByTestId(`scans-table-row-${unfinishedScan.scan_id}`)

    const unfinished = row(unfinishedScan.scan_id)
    expect(
      within(unfinished).getByTestId(`scans-status-${unfinishedScan.scan_id}`),
    ).toHaveTextContent('Running…')
    expectHiddenCounts(unfinishedScan.scan_id)

    const completedStatus = within(
      row(latestSuccessfulScan.scan_id),
    ).getByTestId(`scans-status-${latestSuccessfulScan.scan_id}`)
    expect(completedStatus).toHaveTextContent('Completed')
    expect(completedStatus).not.toHaveTextContent('—')

    const failed = row(failedScan.scan_id)
    expect(
      within(failed).getByTestId(`scans-status-${failedScan.scan_id}`),
    ).toHaveTextContent('Failed')
    expectHiddenCounts(failedScan.scan_id)

    const table = screen.getByTestId('scans-table')
    for (const header of within(table).getAllByRole('columnheader')) {
      expect(within(header).queryByRole('button')).not.toBeInTheDocument()
    }
  })

  it('shows rows 21–25 after advancing a page, and none of rows 1–20', async () => {
    const user = userEvent.setup()
    const firstPage = scanFixtures.slice(0, 20)
    const secondPage = scanFixtures.slice(20, 25)
    renderWithProviders(<Scans />, { route: '/scans' })

    expect(
      await screen.findByTestId(`scans-table-row-${firstPage[0].scan_id}`),
    ).toBeInTheDocument()
    expect(screen.getByTestId('scans-pagination')).toBeInTheDocument()
    expect(
      screen.getByRole('navigation', { name: 'Scan pages' }),
    ).toBeInTheDocument()

    await user.click(screen.getByTestId('scans-next'))

    expect(
      await screen.findByTestId(`scans-table-row-${secondPage[0].scan_id}`),
    ).toBeInTheDocument()
    for (const scan of secondPage) {
      expect(row(scan.scan_id)).toBeInTheDocument()
    }
    for (const scan of firstPage) {
      expect(
        screen.queryByTestId(`scans-table-row-${scan.scan_id}`),
      ).not.toBeInTheDocument()
    }
  })

  it('renders the mode label, Duration column, and no Result column', async () => {
    scanList([latestSuccessfulScan])
    renderWithProviders(<Scans />, { route: '/scans' })

    await screen.findByTestId(`scans-table-row-${latestSuccessfulScan.scan_id}`)

    const headers = within(screen.getByTestId('scans-table'))
      .getAllByRole('columnheader')
      .map((header) => header.textContent)
    expect(headers).toContain('Duration')
    expect(headers).not.toContain('Result')
    expect(screen.getByTestId('scans-page')).not.toHaveTextContent(
      /scan type|scan settings|Use this scan type/i,
    )
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
    expect(
      within(row(latestSuccessfulScan.scan_id)).getAllByRole('cell')[2],
    ).toHaveTextContent(SCAN_MODE_LABEL[latestSuccessfulScan.scan_mode])
  })

  it('navigates to the scan when a row is activated', async () => {
    const user = userEvent.setup()
    scanList([latestSuccessfulScan])
    renderWithProviders(
      <>
        <Scans />
        <LocationProbe />
      </>,
      { route: '/scans' },
    )

    await screen.findByTestId(`scans-table-row-${latestSuccessfulScan.scan_id}`)
    await user.click(
      within(row(latestSuccessfulScan.scan_id)).getByRole('link'),
    )

    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/scans/${latestSuccessfulScan.scan_id}`,
    )
  })
})
