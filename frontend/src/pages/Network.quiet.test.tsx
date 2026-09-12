import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import Network from '@/pages/Network'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import { baseURL } from '@/test/hostsHarness'
import { hostFixtures } from '@/test/mswHandlers'
import type { components } from '@/types/openapi'

type HostSummary = components['schemas']['HostSummary']
type HostListResponse = components['schemas']['HostListResponse']

const WEEK_MS = 7 * 24 * 60 * 60 * 1000

function quietHosts(count: number): HostSummary[] {
  return hostFixtures.slice(0, count).map((host, index) => ({
    ...host,
    host_id: `quiet-${index}`,
    last_seen_at: new Date(Date.now() - (index + 2) * WEEK_MS).toISOString(),
  }))
}

function serveHosts(
  active: HostSummary[],
  quiet: HostSummary[],
  quietTotal = quiet.length,
) {
  const requests: { activePages: number[]; quietPages: number[] } = {
    activePages: [],
    quietPages: [],
  }
  server.use(
    http.get(`${baseURL}/hosts`, ({ request }) => {
      const params = new URL(request.url).searchParams
      const page = Number(params.get('page') ?? 1)
      const perPage = Number(params.get('per_page') ?? 20)
      const isQuiet = params.get('group') === 'quiet'
      const rows = isQuiet ? quiet : active
      if (isQuiet) requests.quietPages.push(page)
      else requests.activePages.push(page)
      return HttpResponse.json({
        data: rows.slice((page - 1) * perPage, page * perPage),
        total: rows.length,
        page,
        quiet_total: quietTotal,
      } satisfies HostListResponse)
    }),
  )
  return requests
}

function toggle(name: string) {
  return within(screen.getByTestId('network-quiet-group')).getByRole('button', {
    name,
  })
}

describe('Network quiet group', () => {
  it('reports the whole-inventory quiet count on a page holding no quiet rows', async () => {
    const user = userEvent.setup()
    const requests = serveHosts(hostFixtures.slice(0, 3), [], 6)
    renderWithProviders(<Network />, { route: '/network' })

    const group = await screen.findByTestId('network-quiet-group')
    expect(group).toHaveTextContent('Not seen recently (6)')
    expect(requests.quietPages).toEqual([])

    await user.click(toggle('Not seen recently (6)'))

    await waitFor(() => expect(requests.quietPages).toEqual([1]))
    expect(
      screen.queryByTestId('network-table-row-quiet-0'),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId('network-quiet-group')).toHaveTextContent(
      'Not seen recently (6)',
    )
    expect(
      screen.queryByRole('navigation', { name: 'Quiet machine pages' }),
    ).not.toBeInTheDocument()
  })

  it('draws the headings, one inert sentence row and the group when every machine is quiet', async () => {
    serveHosts([], quietHosts(3))
    renderWithProviders(<Network />, { route: '/network' })

    const group = await screen.findByTestId('network-quiet-group')
    expect(
      screen
        .getAllByRole('columnheader')
        .map((header) => header.textContent?.trim()),
    ).toEqual([
      'Machine',
      'Address',
      'Type',
      'Vulnerabilities',
      'Highest severity',
      'Last seen',
    ])

    const sentence = screen.getByTestId('network-no-active')
    expect(sentence).toHaveTextContent('No machines seen in the last 7 days.')
    const sentenceRow = within(
      screen.getByTestId('network-table'),
    ).getAllByRole('row')[1]
    expect(sentenceRow).toContainElement(sentence)
    expect(within(sentenceRow).queryByRole('link')).not.toBeInTheDocument()
    expect(within(sentenceRow).queryByRole('button')).not.toBeInTheDocument()

    expect(group).toHaveTextContent('Not seen recently (3)')
    expect(screen.queryByTestId('network-pagination')).not.toBeInTheDocument()
  })

  it('keeps the opened group and its rows when the active list pages', async () => {
    const user = userEvent.setup()
    const active = hostFixtures.slice(0, 25)
    const requests = serveHosts(active, quietHosts(2))
    renderWithProviders(<Network />, { route: '/network' })

    await screen.findByTestId('network-quiet-group')
    await user.click(toggle('Not seen recently (2)'))

    expect(
      await screen.findByTestId('network-table-row-quiet-0'),
    ).toBeInTheDocument()

    await user.click(screen.getByTestId('network-next'))

    expect(
      await screen.findByTestId(`network-table-row-${active[20].host_id}`),
    ).toBeInTheDocument()
    expect(screen.getByTestId('network-table-row-quiet-0')).toBeInTheDocument()
    expect(screen.getByTestId('network-table-row-quiet-1')).toBeInTheDocument()
    expect(toggle('Not seen recently (2)')).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    expect(requests.quietPages.every((page) => page === 1)).toBe(true)
  })

  it('keeps the quiet page when the active list pages', async () => {
    const user = userEvent.setup()
    const active = hostFixtures.slice(0, 25)
    const quiet = Array.from({ length: 25 }, (_, index) => ({
      ...quietHosts(1)[0],
      host_id: `quiet-${index}`,
    }))
    serveHosts(active, quiet)
    renderWithProviders(<Network />, { route: '/network' })

    await screen.findByTestId('network-quiet-group')
    await user.click(toggle('Not seen recently (25)'))
    await screen.findByTestId('network-table-row-quiet-0')
    await user.click(screen.getByTestId('network-quiet-next'))
    expect(
      await screen.findByTestId('network-table-row-quiet-20'),
    ).toBeInTheDocument()

    await user.click(screen.getByTestId('network-next'))

    expect(
      await screen.findByTestId(`network-table-row-${active[20].host_id}`),
    ).toBeInTheDocument()
    expect(
      await screen.findByTestId('network-table-row-quiet-20'),
    ).toBeInTheDocument()
    expect(
      screen.queryByTestId('network-table-row-quiet-0'),
    ).not.toBeInTheDocument()
  })

  it('does not re-collapse the opened group when the active list is sorted', async () => {
    const user = userEvent.setup()
    serveHosts(hostFixtures.slice(0, 3), quietHosts(2))
    renderWithProviders(<Network />, { route: '/network' })

    await screen.findByTestId('network-quiet-group')
    await user.click(toggle('Not seen recently (2)'))

    expect(
      await screen.findByTestId('network-table-row-quiet-0'),
    ).toBeInTheDocument()

    await user.click(screen.getByTestId('network-table-sort-hostname'))

    expect(
      await screen.findByRole('columnheader', { name: 'Machine' }),
    ).toHaveAttribute('aria-sort', 'ascending')
    expect(toggle('Not seen recently (2)')).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    expect(screen.getByTestId('network-table-row-quiet-0')).toBeInTheDocument()
  })

  it('shows the group skeleton while its own read is in flight, without touching the active list', async () => {
    const user = userEvent.setup()
    const active = hostFixtures.slice(0, 3)
    server.use(
      http.get(`${baseURL}/hosts`, async ({ request }) => {
        const params = new URL(request.url).searchParams
        if (params.get('group') === 'quiet') await delay('infinite')
        return HttpResponse.json({
          data: active,
          total: active.length,
          page: 1,
          quiet_total: 4,
        } satisfies HostListResponse)
      }),
    )
    renderWithProviders(<Network />, { route: '/network' })

    await screen.findByTestId('network-quiet-group')
    await user.click(toggle('Not seen recently (4)'))

    expect(
      await screen.findByTestId('network-quiet-loading'),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('network-quiet-error')).not.toBeInTheDocument()
    expect(
      screen.getByTestId(`network-table-row-${active[0].host_id}`),
    ).toBeInTheDocument()
    expect(screen.getByTestId('network-quiet-group')).toHaveTextContent(
      'Not seen recently (4)',
    )
  })
})
