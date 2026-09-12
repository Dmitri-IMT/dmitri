import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useLocation } from 'react-router'
import { delay, http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import {
  adminProfile,
  viewerProfile,
  criticalFinding,
  highFinding,
  homeSnapshot,
  latestSuccessfulScan,
} from '@/test/mswHandlers'
import type { components } from '@/types/openapi'
import Home from './Home'

type HomeSnapshot = components['schemas']['HomeSnapshot']

const baseURL = 'http://localhost:8000/api/v1'

function eventsPanel() {
  return document.getElementById('home-events-panel')
}

function activityPanel() {
  return document.getElementById('home-activity-panel')
}

function LocationProbe() {
  const location = useLocation()
  return (
    <div data-testid="location-probe">
      {location.pathname}
      {location.search}
    </div>
  )
}

function overrideHome(
  resolve: (url: URL) => HomeSnapshot | Promise<HomeSnapshot>,
) {
  server.use(
    http.get(`${baseURL}/home`, async ({ request }) => {
      const url = new URL(request.url)
      return HttpResponse.json(await resolve(url))
    }),
  )
}

function trackRequests() {
  const homeUrls: string[] = []
  const scansUrls: string[] = []
  const findingsUrls: string[] = []
  const analysisUrls: string[] = []

  server.use(
    http.get(`${baseURL}/home`, ({ request }) => {
      homeUrls.push(request.url)
      const url = new URL(request.url)
      const attentionPage = Number(
        url.searchParams.get('attention_page') ?? '1',
      )
      return HttpResponse.json(homeSnapshot({}, attentionPage))
    }),
    http.get(`${baseURL}/scans`, ({ request }) => {
      scansUrls.push(request.url)
      return HttpResponse.json({ data: [], total: 0, page: 1 })
    }),
    http.get(`${baseURL}/findings`, ({ request }) => {
      findingsUrls.push(request.url)
      return HttpResponse.json({ data: [], total: 0, page: 1 })
    }),
    http.get(`${baseURL}/scans/:scanId/analysis`, ({ request }) => {
      analysisUrls.push(request.url)
      return HttpResponse.json({
        scan_id: latestSuccessfulScan.scan_id,
        analysis_id: null,
        status: 'unavailable',
        analysis: null,
        provider: null,
        model: null,
        context_version: null,
        prompt_version: null,
        created_at: null,
        updated_at: null,
        completed_at: null,
      })
    }),
  )

  return { homeUrls, scansUrls, findingsUrls, analysisUrls }
}

function overrideUser(profile: typeof adminProfile | typeof viewerProfile) {
  server.use(http.get(`${baseURL}/users/me`, () => HttpResponse.json(profile)))
}

function interactiveElements() {
  return [
    ...screen.queryAllByRole('button'),
    ...screen.queryAllByRole('link'),
    ...screen.queryAllByRole('textbox'),
  ]
}

function expectNoDisabledControls() {
  for (const el of interactiveElements()) {
    expect(el).toBeEnabled()
    expect(el).not.toHaveAttribute('aria-disabled', 'true')
  }
}

const nineDaysAgo = new Date(Date.now() - 9 * 24 * 60 * 60 * 1000).toISOString()
const staleSuccessfulScan = {
  ...latestSuccessfulScan,
  timestamp: nineDaysAgo,
}

describe('Home', () => {
  it('loads the Home snapshot and its persisted latest-scan AI overview', async () => {
    const tracked = trackRequests()
    renderWithProviders(<Home />)

    await screen.findByTestId('home-verdict')
    expect(tracked.homeUrls).toHaveLength(1)
    expect(tracked.scansUrls).toHaveLength(0)
    expect(tracked.findingsUrls).toHaveLength(0)
    expect(tracked.analysisUrls).toHaveLength(1)
  })

  it('with attention, the title states the count and each row navigates', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <>
        <LocationProbe />
        <Home />
      </>,
    )

    await screen.findByTestId('home-verdict')
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      '2 things need your attention',
    )
    expect(screen.getByTestId('home-table')).toBeInTheDocument()
    expect(
      screen.getByTestId(`home-table-row-${criticalFinding.finding_id}`),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId(`home-table-row-${highFinding.finding_id}`),
    ).toBeInTheDocument()

    const criticalLink = screen.getByRole('link', {
      name: `${criticalFinding.title} on ${criticalFinding.host_ip}`,
    })
    await user.click(criticalLink)
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/scans/${criticalFinding.scan_id}?finding=${criticalFinding.finding_id}`,
    )

    const highLink = screen.getByRole('link', {
      name: `${highFinding.title} on ${highFinding.host_ip}`,
    })
    await user.click(highLink)
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/scans/${highFinding.scan_id}?finding=${highFinding.finding_id}`,
    )
  })

  it('opens the machine when the Machine cell is activated', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <>
        <LocationProbe />
        <Home />
      </>,
    )

    const row = await screen.findByTestId(
      `home-table-row-${criticalFinding.finding_id}`,
    )
    await user.click(
      within(row).getByRole('link', { name: criticalFinding.host_ip ?? '' }),
    )
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/network/${criticalFinding.host_id}`,
    )
  })

  it('with none, the title reads Nothing needs your attention and no table is in the DOM', async () => {
    overrideHome(() =>
      homeSnapshot({
        review_state: 'clear',
        review_count: 0,
        attention: { data: [], total: 0, page: 1 },
      }),
    )
    renderWithProviders(<Home />)

    await screen.findByTestId('home-verdict')
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      'Nothing needs your attention',
    )
    expect(screen.queryByTestId('home-table')).toBeNull()
    expect(eventsPanel()).toBeInTheDocument()
    expect(activityPanel()).toBeInTheDocument()
  })

  it('a failed latest scan renders its one-line notice', async () => {
    overrideHome(() =>
      homeSnapshot({
        review_count: 1,
        notices: [
          {
            kind: 'failed_scan',
            text: "Last night's scan didn't finish.",
          },
        ],
        attention: { data: [], total: 0, page: 1 },
      }),
    )
    renderWithProviders(<Home />)

    await screen.findByTestId('home-item-scan')
    expect(screen.getByTestId('home-item-scan')).toHaveTextContent(
      "Last night's scan didn't finish.",
    )
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      '1 thing needs your attention',
    )
    expect(screen.queryByTestId('home-table')).toBeNull()
  })

  it('a stale coverage window renders its one-line notice', async () => {
    overrideHome(() =>
      homeSnapshot({
        review_count: 1,
        latest_successful_scan: staleSuccessfulScan,
        notices: [
          {
            kind: 'stale_coverage',
            text: 'No successful scan in 9 days.',
            days: 9,
          },
        ],
        attention: { data: [], total: 0, page: 1 },
      }),
    )
    renderWithProviders(<Home />)

    await screen.findByTestId('home-item-coverage')
    expect(screen.getByTestId('home-item-coverage')).toHaveTextContent(
      'No successful scan in 9 days.',
    )
    expect(screen.queryByTestId('home-table')).toBeNull()
  })

  it('failed-scan and stale-coverage notices sit below the last-scan line', async () => {
    overrideHome(() =>
      homeSnapshot({
        review_count: 4,
        latest_successful_scan: staleSuccessfulScan,
        notices: [
          {
            kind: 'failed_scan',
            text: "Last night's scan didn't finish.",
          },
          {
            kind: 'stale_coverage',
            text: 'No successful scan in 9 days.',
            days: 9,
          },
        ],
        attention: {
          data: [criticalFinding, highFinding],
          total: 2,
          page: 1,
        },
      }),
    )
    renderWithProviders(<Home />)

    await screen.findByTestId('home-item-scan')
    const context = screen.getByTestId('home-context')
    const scanNotice = screen.getByTestId('home-item-scan')
    const coverageNotice = screen.getByTestId('home-item-coverage')

    expect(
      context.compareDocumentPosition(scanNotice) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(
      scanNotice.compareDocumentPosition(coverageNotice) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      '4 things need your attention',
    )
  })

  it('admin blank links to the first scan and shows feed panels', async () => {
    overrideUser(adminProfile)
    overrideHome(() =>
      homeSnapshot({
        review_state: 'blank',
        review_count: 0,
        latest_successful_scan: null,
        attention: { data: [], total: 0, page: 1 },
      }),
    )
    renderWithProviders(<Home />)

    expect(await screen.findByTestId('home-blank-body')).toHaveTextContent(
      'Your first scan finds the machines on your network and what needs fixing.',
    )
    const cta = screen.getByTestId('first-scan-cta')
    expect(cta).toHaveAttribute('href', '/devices')
    expect(screen.queryByTestId('first-scan-note')).not.toBeInTheDocument()
    expect(eventsPanel()).toBeInTheDocument()
    expect(activityPanel()).toBeInTheDocument()
    expect(screen.queryByTestId('home-table')).toBeNull()
  })

  it('viewer blank shows only the admin-direction note', async () => {
    overrideUser(viewerProfile)
    overrideHome(() =>
      homeSnapshot({
        review_state: 'blank',
        review_count: 0,
        latest_successful_scan: null,
        attention: { data: [], total: 0, page: 1 },
      }),
    )
    renderWithProviders(<Home />)

    expect(await screen.findByTestId('first-scan-note')).toHaveTextContent(
      'Ask your admin to run the first scan.',
    )
    expect(screen.queryByTestId('first-scan-cta')).not.toBeInTheDocument()
    expect(screen.queryAllByRole('button')).toHaveLength(0)
    expect(screen.queryAllByRole('link')).toHaveLength(0)
  })

  it('error renders the copy and Try again, with no verdict text present', async () => {
    server.use(
      http.get(
        `${baseURL}/home`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    )
    renderWithProviders(<Home />)

    await screen.findByTestId('home-error')
    expect(screen.getByTestId('home-error')).toHaveTextContent(
      "Couldn't load what needs your attention.",
    )
    expect(screen.getByRole('button', { name: 'Try again' })).toBeEnabled()
    expect(screen.queryByTestId('home-verdict')).not.toBeInTheDocument()
  })

  it('Try again recovers to the clear state after a transient failure', async () => {
    const user = userEvent.setup()
    let calls = 0
    server.use(
      http.get(`${baseURL}/home`, () => {
        calls += 1
        if (calls === 1) return new HttpResponse(null, { status: 500 })
        return HttpResponse.json(
          homeSnapshot({
            review_state: 'clear',
            review_count: 0,
            attention: { data: [], total: 0, page: 1 },
          }),
        )
      }),
    )

    renderWithProviders(<Home />)
    await screen.findByTestId('home-error')

    await user.click(screen.getByRole('button', { name: 'Try again' }))

    await screen.findByTestId('home-verdict')
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      'Nothing needs your attention',
    )
  })

  it('the verdict states review_count when it exceeds the rows shown', async () => {
    overrideHome(() =>
      homeSnapshot({
        review_count: 37,
        attention: {
          data: [criticalFinding],
          total: 37,
          page: 1,
        },
      }),
    )
    renderWithProviders(<Home />)

    await screen.findByTestId('home-verdict')
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      '37 things need your attention',
    )
  })

  it('review_count stays correct on attention page 2', async () => {
    const user = userEvent.setup()
    overrideHome((url) => {
      const attentionPage = Number(
        url.searchParams.get('attention_page') ?? '1',
      )
      return homeSnapshot(
        {
          review_count: 14,
          attention: {
            data: attentionPage === 1 ? [criticalFinding] : [highFinding],
            total: 14,
            page: attentionPage,
          },
        },
        attentionPage,
      )
    })
    renderWithProviders(<Home />)

    await screen.findByTestId('home-verdict')
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      '14 things need your attention',
    )

    await user.click(screen.getByTestId('home-attention-page-2'))

    await screen.findByTestId(`home-table-row-${highFinding.finding_id}`)
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      '14 things need your attention',
    )
  })

  it('hides attention pagination when total is at most 8', async () => {
    overrideHome(() => homeSnapshot())
    renderWithProviders(<Home />)

    await screen.findByTestId('home-verdict')
    expect(
      screen.queryByRole('navigation', { name: 'Attention pages' }),
    ).toBeNull()
  })

  it('shows attention pagination named Attention pages when total exceeds 8', async () => {
    overrideHome(() =>
      homeSnapshot({
        review_count: 9,
        attention: {
          data: [criticalFinding],
          total: 9,
          page: 1,
        },
      }),
    )
    renderWithProviders(<Home />)

    await screen.findByRole('navigation', { name: 'Attention pages' })
  })

  it('changing attention page keeps both feed panels on screen', async () => {
    const user = userEvent.setup()
    overrideHome((url) => {
      const attentionPage = Number(
        url.searchParams.get('attention_page') ?? '1',
      )
      return homeSnapshot(
        {
          review_count: 14,
          attention: {
            data: attentionPage === 1 ? [criticalFinding] : [highFinding],
            total: 14,
            page: attentionPage,
          },
          events: {
            data: [
              {
                kind: 'box_offline',
                text: 'pi-office-01 has not reported for 4 days.',
                occurred_at: '2026-09-01T10:00:00Z',
              },
            ],
            total: 1,
            page: 1,
          },
          activity: {
            data: [
              {
                kind: 'scan_finished',
                text: 'Scan of 192.168.1.0/24 finished.',
                occurred_at: '2026-09-01T09:00:00Z',
              },
            ],
            total: 1,
            page: 1,
          },
        },
        attentionPage,
      )
    })
    renderWithProviders(<Home />)

    await screen.findByTestId('home-verdict')
    expect(eventsPanel()).toBeInTheDocument()
    expect(activityPanel()).toBeInTheDocument()

    await user.click(screen.getByTestId('home-attention-page-2'))

    await screen.findByTestId(`home-table-row-${highFinding.finding_id}`)
    expect(eventsPanel()).toBeInTheDocument()
    expect(activityPanel()).toBeInTheDocument()
  })

  it('a viewer sees invite and role-change activity with server-neutral copy', async () => {
    overrideUser(viewerProfile)
    overrideHome(() =>
      homeSnapshot({
        activity: {
          data: [
            {
              kind: 'member_invited',
              text: 'ana@northwind.example was invited as a viewer.',
              occurred_at: '2026-09-01T08:00:00Z',
            },
            {
              kind: 'role_changed',
              text: 'sam@northwind.example is now an admin.',
              occurred_at: '2026-09-01T07:00:00Z',
            },
          ],
          total: 2,
          page: 1,
        },
      }),
    )
    renderWithProviders(<Home />)

    await screen.findByTestId('home-activity-row-0-text')
    expect(screen.getByTestId('home-activity-row-0-text')).toHaveTextContent(
      'ana@northwind.example was invited as a viewer.',
    )
    expect(screen.getByTestId('home-activity-row-1-text')).toHaveTextContent(
      'sam@northwind.example is now an admin.',
    )
  })

  it('first load renders the home-loading skeleton', async () => {
    server.use(
      http.get(`${baseURL}/home`, async () => {
        await delay('infinite')
        return HttpResponse.json(homeSnapshot())
      }),
    )

    renderWithProviders(<Home />)

    expect(await screen.findByTestId('home-loading')).toBeInTheDocument()
    expect(screen.getByTestId('home-page')).toBeInTheDocument()
    expect(screen.queryByTestId('home-verdict')).not.toBeInTheDocument()
  })

  it('a page change does not return to home-loading', async () => {
    const user = userEvent.setup()
    let calls = 0
    overrideHome(async (url) => {
      calls += 1
      if (calls > 1) await delay(20)
      const attentionPage = Number(
        url.searchParams.get('attention_page') ?? '1',
      )
      return homeSnapshot(
        {
          review_count: 14,
          attention: {
            data: attentionPage === 1 ? [criticalFinding] : [highFinding],
            total: 14,
            page: attentionPage,
          },
        },
        attentionPage,
      )
    })
    renderWithProviders(<Home />)

    await screen.findByTestId('home-verdict')
    expect(screen.queryByTestId('home-loading')).toBeNull()

    await user.click(screen.getByTestId('home-attention-page-2'))

    expect(screen.queryByTestId('home-loading')).toBeNull()
    expect(screen.getByTestId('home-verdict')).toBeInTheDocument()

    await screen.findByTestId(`home-table-row-${highFinding.finding_id}`)
  })

  it.each([
    ['admin', adminProfile, 'blank' as const],
    ['viewer', viewerProfile, 'blank' as const],
    ['admin', adminProfile, 'clear' as const],
    ['viewer', viewerProfile, 'clear' as const],
    ['admin', adminProfile, 'pending' as const],
    ['viewer', viewerProfile, 'pending' as const],
    ['admin', adminProfile, 'error' as const],
    ['viewer', viewerProfile, 'error' as const],
  ])(
    'every rendered control is enabled with no aria-disabled, %s / %s',
    async (_label, profile, state) => {
      overrideUser(profile)
      if (state === 'blank') {
        overrideHome(() =>
          homeSnapshot({
            review_state: 'blank',
            review_count: 0,
            latest_successful_scan: null,
            attention: { data: [], total: 0, page: 1 },
          }),
        )
      } else if (state === 'clear') {
        overrideHome(() =>
          homeSnapshot({
            review_state: 'clear',
            review_count: 0,
            attention: { data: [], total: 0, page: 1 },
          }),
        )
      } else if (state === 'error') {
        server.use(
          http.get(
            `${baseURL}/home`,
            () => new HttpResponse(null, { status: 500 }),
          ),
        )
      }
      renderWithProviders(<Home />)

      if (state === 'blank') {
        await screen.findByTestId(
          profile.role === 'admin' ? 'first-scan-cta' : 'first-scan-note',
        )
      } else if (state === 'error') {
        await screen.findByTestId('home-error')
      } else {
        await screen.findByTestId('home-verdict')
      }

      expectNoDisabledControls()
    },
  )
})
