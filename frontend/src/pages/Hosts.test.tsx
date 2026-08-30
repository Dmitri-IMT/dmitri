import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import Hosts from '@/pages/Hosts'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import LocationProbe from '@/test/LocationProbe'
import { baseURL } from '@/test/hostsHarness'
import { adminProfile, hostFixtures, viewerProfile } from '@/test/mswHandlers'
import type { components } from '@/types/openapi'

type HostSummary = components['schemas']['HostSummary']
type HostListResponse = components['schemas']['HostListResponse']

const unnamedHost = hostFixtures[24]
const newestHost = hostFixtures[0]

function overrideUser(profile: typeof adminProfile | typeof viewerProfile) {
  server.use(http.get(`${baseURL}/users/me`, () => HttpResponse.json(profile)))
}

function emptyList(): HostListResponse {
  return { data: [], total: 0, page: 1 }
}

function hostList(
  rows: HostSummary[],
  { requireLastSeenDesc = false }: { requireLastSeenDesc?: boolean } = {},
) {
  server.use(
    http.get(`${baseURL}/hosts`, ({ request }) => {
      const params = new URL(request.url).searchParams
      if (
        requireLastSeenDesc &&
        (params.get('sort_by') !== 'last_seen_at' ||
          params.get('sort_order') !== 'desc')
      ) {
        return HttpResponse.json(emptyList())
      }
      return HttpResponse.json({
        data: rows,
        total: rows.length,
        page: 1,
      } satisfies HostListResponse)
    }),
  )
}

function row(hostId: string) {
  return screen.getByTestId(`hosts-table-row-${hostId}`)
}

function dataRows() {
  return within(screen.getByTestId('hosts-table')).getAllByRole('row').slice(1)
}

function hostnameAsc() {
  return [...hostFixtures].sort((left, right) =>
    left.hostname.localeCompare(right.hostname, undefined, { numeric: true }),
  )
}

function hostnameDesc() {
  return hostnameAsc().reverse()
}

describe('Hosts', () => {
  it('shows the last-seen descending hostname first when the request sends that sort', async () => {
    hostList([newestHost, unnamedHost], { requireLastSeenDesc: true })
    renderWithProviders(<Hosts />, { route: '/hosts' })

    await screen.findByTestId(`hosts-table-row-${newestHost.host_id}`)
    expect(within(dataRows()[0]).getAllByRole('cell')[0]).toHaveTextContent(
      newestHost.hostname,
    )
  })

  it('sorts by Host ascending from page 2 and returns to the first page', async () => {
    const user = userEvent.setup()
    const firstPage = hostFixtures.slice(0, 20)
    const secondPage = hostFixtures.slice(20, 25)
    const ascending = hostnameAsc()
    renderWithProviders(<Hosts />, { route: '/hosts' })

    expect(
      await screen.findByTestId(`hosts-table-row-${firstPage[0].host_id}`),
    ).toBeInTheDocument()

    await user.click(screen.getByTestId('hosts-next'))

    expect(
      await screen.findByTestId(`hosts-table-row-${secondPage[0].host_id}`),
    ).toBeInTheDocument()
    expect(
      screen.queryByTestId(`hosts-table-row-${firstPage[0].host_id}`),
    ).not.toBeInTheDocument()

    await user.click(screen.getByTestId('hosts-table-sort-hostname'))

    expect(
      await screen.findByTestId(`hosts-table-row-${ascending[0].host_id}`),
    ).toBeInTheDocument()
    expect(screen.getByTestId('hosts-range')).toHaveTextContent(
      `Showing 1–20 of ${hostFixtures.length}`,
    )
    expect(within(dataRows()[0]).getAllByRole('cell')[0]).toHaveTextContent(
      '(unnamed)',
    )
    expect(row(newestHost.host_id)).toBeInTheDocument()
    expect(
      screen.queryByTestId(`hosts-table-row-${secondPage[0].host_id}`),
    ).not.toBeInTheDocument()
  })

  it('flips Host from ascending to descending when the active heading is clicked again', async () => {
    const user = userEvent.setup()
    const ascendingFirst = hostnameAsc()[0]
    const descendingFirst = hostnameDesc()[0]
    renderWithProviders(<Hosts />, { route: '/hosts' })

    await screen.findByTestId(`hosts-table-row-${newestHost.host_id}`)
    await user.click(screen.getByTestId('hosts-table-sort-hostname'))

    expect(
      await screen.findByTestId(`hosts-table-row-${ascendingFirst.host_id}`),
    ).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Host' })).toHaveAttribute(
      'aria-sort',
      'ascending',
    )

    await user.click(screen.getByTestId('hosts-table-sort-hostname'))

    expect(
      await screen.findByTestId(`hosts-table-row-${descendingFirst.host_id}`),
    ).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Host' })).toHaveAttribute(
      'aria-sort',
      'descending',
    )
    expect(within(dataRows()[0]).getAllByRole('cell')[0]).toHaveTextContent(
      descendingFirst.hostname,
    )
  })

  it('starts Last seen descending when the sort switches back to it', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Hosts />, { route: '/hosts' })

    await screen.findByTestId(`hosts-table-row-${newestHost.host_id}`)
    await user.click(screen.getByTestId('hosts-table-sort-hostname'))

    expect(screen.getByRole('columnheader', { name: 'Host' })).toHaveAttribute(
      'aria-sort',
      'ascending',
    )

    await user.click(screen.getByTestId('hosts-table-sort-last_seen_at'))

    expect(
      await screen.findByRole('columnheader', { name: 'Last seen' }),
    ).toHaveAttribute('aria-sort', 'descending')
  })

  it('renders the server order for vendor even when that payload is unsorted', async () => {
    const user = userEvent.setup()
    const scrambled = [
      hostFixtures[10],
      hostFixtures[0],
      hostFixtures[20],
      hostFixtures[5],
    ]
    server.use(
      http.get(`${baseURL}/hosts`, ({ request }) => {
        const params = new URL(request.url).searchParams
        const rows =
          params.get('sort_by') === 'vendor' ? scrambled : [newestHost]
        return HttpResponse.json({
          data: rows,
          total: rows.length,
          page: 1,
        } satisfies HostListResponse)
      }),
    )
    renderWithProviders(<Hosts />, { route: '/hosts' })

    await screen.findByTestId(`hosts-table-row-${newestHost.host_id}`)
    await user.click(screen.getByTestId('hosts-table-sort-vendor'))

    expect(
      await screen.findByTestId(`hosts-table-row-${scrambled[0].host_id}`),
    ).toBeInTheDocument()
    expect(
      dataRows().map(
        (hostRow) => within(hostRow).getAllByRole('cell')[0].textContent,
      ),
    ).toEqual(scrambled.map((host) => host.hostname))
  })

  it('keeps seven cells for a host with no MAC and no hostname', async () => {
    hostList([unnamedHost])
    renderWithProviders(<Hosts />, { route: '/hosts' })

    const cells = within(
      await screen.findByTestId(`hosts-table-row-${unnamedHost.host_id}`),
    ).getAllByRole('cell')
    expect(cells).toHaveLength(7)
    expect(cells[0]).toHaveTextContent('(unnamed)')
    expect(cells[2]).toHaveTextContent('—')
  })

  it('shows rows 21–25 after advancing a page, and none of rows 1–20', async () => {
    const user = userEvent.setup()
    const firstPage = hostFixtures.slice(0, 20)
    const secondPage = hostFixtures.slice(20, 25)
    renderWithProviders(<Hosts />, { route: '/hosts' })

    expect(
      await screen.findByTestId(`hosts-table-row-${firstPage[0].host_id}`),
    ).toBeInTheDocument()
    expect(screen.getByTestId('hosts-pagination')).toBeInTheDocument()
    expect(screen.getByTestId('hosts-range')).toHaveTextContent(
      `Showing 1–20 of ${hostFixtures.length}`,
    )

    await user.click(screen.getByTestId('hosts-next'))

    expect(
      await screen.findByTestId(`hosts-table-row-${secondPage[0].host_id}`),
    ).toBeInTheDocument()
    expect(screen.getByTestId('hosts-range')).toHaveTextContent(
      `Showing 21–25 of ${hostFixtures.length}`,
    )
    for (const host of secondPage) {
      expect(row(host.host_id)).toBeInTheDocument()
    }
    for (const host of firstPage) {
      expect(
        screen.queryByTestId(`hosts-table-row-${host.host_id}`),
      ).not.toBeInTheDocument()
    }
  })

  it('renders the first-scan link for an admin blank state', async () => {
    overrideUser(adminProfile)
    hostList([])
    renderWithProviders(<Hosts />, { route: '/hosts' })

    const blank = await screen.findByTestId('hosts-blank')
    expect(blank).toHaveTextContent('No hosts yet.')
    expect(blank).not.toHaveTextContent('Scanning is set up on the Pi itself.')
    expect(within(blank).getByTestId('first-scan-cta')).toHaveAttribute(
      'href',
      '/agents',
    )
    expect(
      within(blank).queryByTestId('first-scan-note'),
    ).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('renders only the admin-direction note for a viewer blank state', async () => {
    overrideUser(viewerProfile)
    hostList([])
    renderWithProviders(<Hosts />, { route: '/hosts' })

    const blank = await screen.findByTestId('hosts-blank')
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
      http.get(`${baseURL}/hosts`, () => {
        if (failed) {
          failed = false
          return new HttpResponse(null, { status: 500 })
        }
        return HttpResponse.json({
          data: [newestHost],
          total: 1,
          page: 1,
        } satisfies HostListResponse)
      }),
    )
    renderWithProviders(<Hosts />, { route: '/hosts' })

    expect(await screen.findByTestId('hosts-error')).toHaveTextContent(
      "Couldn't load the hosts.",
    )
    expect(screen.queryByTestId('hosts-table')).not.toBeInTheDocument()

    await user.click(screen.getByTestId('hosts-error-retry'))

    expect(
      await screen.findByTestId(`hosts-table-row-${newestHost.host_id}`),
    ).toBeInTheDocument()
  })

  it('navigates to the host when a row is activated', async () => {
    const user = userEvent.setup()
    hostList([newestHost])
    renderWithProviders(
      <>
        <Hosts />
        <LocationProbe />
      </>,
      { route: '/hosts' },
    )

    await screen.findByTestId(`hosts-table-row-${newestHost.host_id}`)
    await user.click(within(row(newestHost.host_id)).getByRole('link'))

    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/hosts/${newestHost.host_id}`,
    )
  })
})
