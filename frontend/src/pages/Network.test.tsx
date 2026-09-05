import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import Network from '@/pages/Network'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import LocationProbe from '@/test/LocationProbe'
import { baseURL } from '@/test/hostsHarness'
import { adminProfile, hostFixtures, viewerProfile } from '@/test/mswHandlers'
import type { components } from '@/types/openapi'

type HostSummary = components['schemas']['HostSummary']
type HostListResponse = components['schemas']['HostListResponse']

const DAY_MS = 24 * 60 * 60 * 1000

const unnamedHost = hostFixtures[24]
const newestHost = hostFixtures[0]

function weeksAgo(weeks: number): string {
  return new Date(Date.now() - weeks * 7 * DAY_MS).toISOString()
}

function quiet(host: HostSummary, weeks: number): HostSummary {
  return { ...host, last_seen_at: weeksAgo(weeks) }
}

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

function headerSubtitle() {
  return screen.getByRole('heading', { name: 'Network' }).nextElementSibling
}

function row(hostId: string) {
  return screen.getByTestId(`network-table-row-${hostId}`)
}

function tableRows() {
  return within(screen.getByTestId('network-table'))
    .getAllByRole('row')
    .slice(1)
}

function hostnameAsc() {
  return [...hostFixtures].sort((left, right) =>
    left.hostname.localeCompare(right.hostname, undefined, { numeric: true }),
  )
}

function hostnameDesc() {
  return hostnameAsc().reverse()
}

describe('Network', () => {
  it('shows the machine count and the last scan in the header', async () => {
    hostList([newestHost, unnamedHost])
    renderWithProviders(<Network />, { route: '/network' })

    await waitFor(() => {
      expect(headerSubtitle()).toHaveTextContent('2 machines')
      expect(headerSubtitle()).toHaveTextContent('last scan')
    })
  })

  it('shows the singular machine count for a one-row list', async () => {
    hostList([newestHost])
    renderWithProviders(<Network />, { route: '/network' })

    await waitFor(() => {
      expect(headerSubtitle()).toHaveTextContent('1 machine')
    })
    expect(headerSubtitle()).not.toHaveTextContent('1 machines')
  })

  it('shows the last-seen descending hostname first when the request sends that sort', async () => {
    hostList([newestHost, unnamedHost], { requireLastSeenDesc: true })
    renderWithProviders(<Network />, { route: '/network' })

    await screen.findByTestId(`network-table-row-${newestHost.host_id}`)
    expect(within(tableRows()[0]).getAllByRole('cell')[0]).toHaveTextContent(
      newestHost.hostname,
    )
  })

  it('sorts by Machine ascending from page 2 and returns to the first page', async () => {
    const user = userEvent.setup()
    const firstPage = hostFixtures.slice(0, 20)
    const secondPage = hostFixtures.slice(20, 25)
    const ascending = hostnameAsc()
    renderWithProviders(<Network />, { route: '/network' })

    expect(
      await screen.findByTestId(`network-table-row-${firstPage[0].host_id}`),
    ).toBeInTheDocument()

    await user.click(screen.getByTestId('network-next'))

    expect(
      await screen.findByTestId(`network-table-row-${secondPage[0].host_id}`),
    ).toBeInTheDocument()
    expect(
      screen.queryByTestId(`network-table-row-${firstPage[0].host_id}`),
    ).not.toBeInTheDocument()

    await user.click(screen.getByTestId('network-table-sort-hostname'))

    expect(
      await screen.findByTestId(`network-table-row-${ascending[0].host_id}`),
    ).toBeInTheDocument()
    expect(row(newestHost.host_id)).toBeInTheDocument()
    expect(
      screen.queryByTestId(`network-table-row-${secondPage[0].host_id}`),
    ).not.toBeInTheDocument()
  })

  it('flips Machine from ascending to descending when the active heading is clicked again', async () => {
    const user = userEvent.setup()
    const ascendingFirst = hostnameAsc()[0]
    const descendingFirst = hostnameDesc()[0]
    renderWithProviders(<Network />, { route: '/network' })

    await screen.findByTestId(`network-table-row-${newestHost.host_id}`)
    await user.click(screen.getByTestId('network-table-sort-hostname'))

    expect(
      await screen.findByTestId(`network-table-row-${ascendingFirst.host_id}`),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('columnheader', { name: 'Machine' }),
    ).toHaveAttribute('aria-sort', 'ascending')

    await user.click(screen.getByTestId('network-table-sort-hostname'))

    expect(
      await screen.findByTestId(`network-table-row-${descendingFirst.host_id}`),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('columnheader', { name: 'Machine' }),
    ).toHaveAttribute('aria-sort', 'descending')
    expect(within(tableRows()[0]).getAllByRole('cell')[0]).toHaveTextContent(
      descendingFirst.hostname,
    )
  })

  it('starts Last seen descending when the sort switches back to it', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Network />, { route: '/network' })

    await screen.findByTestId(`network-table-row-${newestHost.host_id}`)
    await user.click(screen.getByTestId('network-table-sort-hostname'))

    expect(
      screen.getByRole('columnheader', { name: 'Machine' }),
    ).toHaveAttribute('aria-sort', 'ascending')

    await user.click(screen.getByTestId('network-table-sort-last_seen_at'))

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
    renderWithProviders(<Network />, { route: '/network' })

    await screen.findByTestId(`network-table-row-${newestHost.host_id}`)
    await user.click(screen.getByTestId('network-table-sort-vendor'))

    expect(
      await screen.findByTestId(`network-table-row-${scrambled[0].host_id}`),
    ).toBeInTheDocument()
    expect(
      tableRows().map(
        (hostRow) => within(hostRow).getAllByRole('cell')[0].textContent,
      ),
    ).toEqual(scrambled.map((host) => host.hostname))
  })

  it('draws only the six specified columns', async () => {
    hostList([newestHost])
    renderWithProviders(<Network />, { route: '/network' })

    await screen.findByTestId(`network-table-row-${newestHost.host_id}`)
    expect(
      screen
        .getAllByRole('columnheader')
        .map((header) => header.textContent?.trim()),
    ).toEqual([
      'Machine',
      'Address',
      'Vendor',
      'Services',
      'Highest severity',
      'Last seen',
    ])
    expect(
      screen.getByRole('columnheader', { name: 'Services' }),
    ).toHaveClass('text-center')
  })

  it('lists a machine with no hostname by its address, with No name yet', async () => {
    hostList([unnamedHost, newestHost])
    renderWithProviders(<Network />, { route: '/network' })

    const cells = within(
      await screen.findByTestId(`network-table-row-${unnamedHost.host_id}`),
    ).getAllByRole('cell')
    expect(cells).toHaveLength(6)
    expect(cells[0]).toHaveTextContent(unnamedHost.ip)
    expect(cells[0]).toHaveTextContent('No name yet')
    expect(
      screen.getByRole('link', { name: `Open ${unnamedHost.ip}` }),
    ).toHaveAttribute('href', `/network/${unnamedHost.host_id}`)

    const named = within(row(newestHost.host_id)).getAllByRole('cell')[0]
    expect(named).toHaveTextContent(newestHost.hostname)
    expect(named).not.toHaveTextContent('No name yet')
  })

  it('renders every control enabled on the machine list', async () => {
    hostList([newestHost, quiet(hostFixtures[3], 3)])
    renderWithProviders(<Network />, { route: '/network' })

    await screen.findByTestId(`network-table-row-${newestHost.host_id}`)
    const interactive = [
      ...screen.queryAllByRole('button'),
      ...screen.queryAllByRole('link'),
      ...screen.queryAllByRole('textbox'),
    ]
    expect(interactive.length).toBeGreaterThan(0)
    for (const element of interactive) {
      expect(element).toBeEnabled()
      expect(element).not.toHaveAttribute('aria-disabled', 'true')
    }
  })

  it('collapses a quiet machine into the group, muted and with its weeks line', async () => {
    const user = userEvent.setup()
    const quietHost = quiet(hostFixtures[3], 3)
    hostList([newestHost, quietHost])
    renderWithProviders(<Network />, { route: '/network' })

    await screen.findByTestId(`network-table-row-${newestHost.host_id}`)
    expect(
      screen.queryByTestId(`network-table-row-${quietHost.host_id}`),
    ).not.toBeInTheDocument()

    const recentRow = row(newestHost.host_id)
    expect(recentRow).not.toHaveAttribute('data-tone', 'muted')
    expect(recentRow).not.toHaveTextContent('Not seen for')

    const group = screen.getByTestId('network-quiet-group')
    expect(group).toHaveTextContent('Not seen recently (1)')
    expect(tableRows().at(-1)).toBe(group)

    const toggle = within(group).getByRole('button', {
      name: 'Not seen recently (1)',
    })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')

    await user.click(toggle)

    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    const quietRow = row(quietHost.host_id)
    expect(quietRow).toHaveAttribute('data-tone', 'muted')
    expect(quietRow).toHaveTextContent('Not seen for 3 weeks')
    expect(
      within(quietRow).getByRole('link', {
        name: `Open ${quietHost.hostname}`,
      }),
    ).toHaveAttribute('href', `/network/${quietHost.host_id}`)

    await user.click(toggle)

    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(
      screen.queryByTestId(`network-table-row-${quietHost.host_id}`),
    ).not.toBeInTheDocument()
  })

  it('keeps the group last after the sort changes', async () => {
    const user = userEvent.setup()
    const quietHost = quiet(hostFixtures[3], 4)
    hostList([newestHost, quietHost])
    renderWithProviders(<Network />, { route: '/network' })

    await screen.findByTestId(`network-table-row-${newestHost.host_id}`)
    await user.click(screen.getByTestId('network-table-sort-hostname'))

    expect(
      await screen.findByRole('columnheader', { name: 'Machine' }),
    ).toHaveAttribute('aria-sort', 'ascending')
    expect(tableRows().at(-1)).toBe(screen.getByTestId('network-quiet-group'))
  })

  it('renders an empty main body and every machine in the group when all are quiet', async () => {
    const user = userEvent.setup()
    const quietHosts = [quiet(hostFixtures[1], 3), quiet(hostFixtures[2], 5)]
    hostList(quietHosts)
    renderWithProviders(<Network />, { route: '/network' })

    const group = await screen.findByTestId('network-quiet-group')
    expect(group).toHaveTextContent('Not seen recently (2)')
    expect(screen.getByTestId('network-table')).toBeInTheDocument()
    expect(screen.queryByTestId('network-blank')).not.toBeInTheDocument()
    expect(tableRows()).toEqual([group])

    await user.click(
      within(group).getByRole('button', { name: 'Not seen recently (2)' }),
    )

    quietHosts.forEach((host, index) => {
      const quietRow = row(host.host_id)
      expect(quietRow).toHaveAttribute('data-tone', 'muted')
      expect(quietRow).toHaveTextContent(
        `Not seen for ${index === 0 ? 3 : 5} weeks`,
      )
    })
  })

  it('shows rows 21–25 after advancing a page, and none of rows 1–20', async () => {
    const user = userEvent.setup()
    const firstPage = hostFixtures.slice(0, 20)
    const secondPage = hostFixtures.slice(20, 25)
    renderWithProviders(<Network />, { route: '/network' })

    expect(
      await screen.findByTestId(`network-table-row-${firstPage[0].host_id}`),
    ).toBeInTheDocument()
    expect(screen.getByTestId('network-pagination')).toBeInTheDocument()

    await user.click(screen.getByTestId('network-next'))

    expect(
      await screen.findByTestId(`network-table-row-${secondPage[0].host_id}`),
    ).toBeInTheDocument()
    for (const host of secondPage) {
      expect(row(host.host_id)).toBeInTheDocument()
    }
    for (const host of firstPage) {
      expect(
        screen.queryByTestId(`network-table-row-${host.host_id}`),
      ).not.toBeInTheDocument()
    }
  })

  it('renders the first-scan link for an admin blank state', async () => {
    overrideUser(adminProfile)
    hostList([])
    renderWithProviders(<Network />, { route: '/network' })

    const blank = await screen.findByTestId('network-blank')
    expect(blank).toHaveTextContent('No machines yet')
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
    hostList([])
    renderWithProviders(<Network />, { route: '/network' })

    const blank = await screen.findByTestId('network-blank')
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
    renderWithProviders(<Network />, { route: '/network' })

    expect(await screen.findByTestId('network-error')).toHaveTextContent(
      "Couldn't load your network.",
    )
    expect(screen.queryByTestId('network-table')).not.toBeInTheDocument()

    await user.click(screen.getByTestId('network-error-retry'))

    expect(
      await screen.findByTestId(`network-table-row-${newestHost.host_id}`),
    ).toBeInTheDocument()
  })

  it('navigates to the machine when a row is activated', async () => {
    const user = userEvent.setup()
    hostList([newestHost])
    renderWithProviders(
      <>
        <Network />
        <LocationProbe />
      </>,
      { route: '/network' },
    )

    await screen.findByTestId(`network-table-row-${newestHost.host_id}`)
    await user.click(
      screen.getByRole('link', { name: `Open ${newestHost.hostname}` }),
    )

    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/network/${newestHost.host_id}`,
    )
  })
})
