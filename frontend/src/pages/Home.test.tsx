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
  latestScan,
  latestSuccessfulScan,
  criticalFinding,
  highFinding,
} from '@/test/mswHandlers'
import type { components } from '@/types/openapi'
import Home from './Home'

type ScanSummary = components['schemas']['ScanSummary']
type FindingRecord = components['schemas']['FindingRecord']

const baseURL = 'http://localhost:8000/api/v1'

function LocationProbe() {
  const location = useLocation()
  return (
    <div data-testid="location-probe">
      {location.pathname}
      {location.search}
    </div>
  )
}

function overrideScans(
  unfiltered: ScanSummary | null,
  completed: ScanSummary | null,
) {
  server.use(
    http.get(`${baseURL}/scans`, ({ request }) => {
      const status = new URL(request.url).searchParams.get('status')
      if (status === 'completed') {
        return HttpResponse.json(
          completed
            ? { data: [completed], total: 1, page: 1 }
            : { data: [], total: 0, page: 1 },
        )
      }
      return HttpResponse.json(
        unfiltered
          ? { data: [unfiltered], total: 1, page: 1 }
          : { data: [], total: 0, page: 1 },
      )
    }),
  )
}

function overrideFindings(
  overrides: {
    criticalData?: FindingRecord[]
    criticalTotal?: number
    highData?: FindingRecord[]
    highTotal?: number
  } = {},
) {
  const {
    criticalData = [],
    criticalTotal = criticalData.length,
    highData = [],
    highTotal = highData.length,
  } = overrides
  server.use(
    http.get(`${baseURL}/findings`, ({ request }) => {
      const severity = new URL(request.url).searchParams.get('severity')
      if (severity === 'critical') {
        return HttpResponse.json({
          data: criticalData,
          total: criticalTotal,
          page: 1,
        })
      }
      return HttpResponse.json({ data: highData, total: highTotal, page: 1 })
    }),
  )
}

function overrideScansUnfilteredError() {
  server.use(
    http.get(`${baseURL}/scans`, ({ request }) => {
      const status = new URL(request.url).searchParams.get('status')
      if (!status) {
        return new HttpResponse(null, { status: 500 })
      }
      return HttpResponse.json({
        data: [latestSuccessfulScan],
        total: 1,
        page: 1,
      })
    }),
  )
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
const staleSuccessfulScan: ScanSummary = {
  ...latestSuccessfulScan,
  timestamp: nineDaysAgo,
}
const failedScan: ScanSummary = { ...latestScan, status: 'failed' }

describe('Home', () => {
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

  it('with none, the title reads Nothing needs your attention and no table or empty card is in the DOM', async () => {
    overrideFindings()
    renderWithProviders(<Home />)

    await screen.findByTestId('home-verdict')
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      'Nothing needs your attention',
    )
    expect(screen.queryByTestId('home-table')).toBeNull()
    expect(screen.queryByTestId('home-deck')).toBeNull()
    expect(screen.queryByTestId('home-deck-card')).toBeNull()
  })

  it('medium/low-only findings yield the clear title with no attention table', async () => {
    overrideFindings()
    renderWithProviders(<Home />)

    await screen.findByTestId('home-verdict')
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      'Nothing needs your attention',
    )
    expect(screen.queryByTestId('home-table')).toBeNull()
  })

  it('a failed latest scan renders its one-line notice', async () => {
    overrideFindings()
    overrideScans(failedScan, latestSuccessfulScan)
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
    overrideFindings()
    overrideScans(latestScan, staleSuccessfulScan)
    renderWithProviders(<Home />)

    await screen.findByTestId('home-item-coverage')
    expect(screen.getByTestId('home-item-coverage')).toHaveTextContent(
      'No successful scan in 9 days.',
    )
    expect(screen.queryByTestId('home-table')).toBeNull()
  })

  it('failed-scan and stale-coverage notices sit below the last-scan line', async () => {
    overrideScans(failedScan, staleSuccessfulScan)
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

  it('admin blank links to the first scan', async () => {
    overrideUser(adminProfile)
    overrideScans(null, null)
    renderWithProviders(<Home />)

    expect(await screen.findByTestId('home-blank-body')).toHaveTextContent(
      'Your first scan finds the machines on your network and what needs fixing.',
    )
    const cta = screen.getByTestId('first-scan-cta')
    expect(cta).toHaveAttribute('href', '/devices')
    expect(screen.queryByTestId('first-scan-note')).not.toBeInTheDocument()
  })

  it('viewer blank shows only the admin-direction note', async () => {
    overrideUser(viewerProfile)
    overrideScans(null, null)
    renderWithProviders(<Home />)

    expect(await screen.findByTestId('first-scan-note')).toHaveTextContent(
      'Ask your admin to run the first scan.',
    )
    expect(screen.queryByTestId('first-scan-cta')).not.toBeInTheDocument()
    expect(screen.queryAllByRole('button')).toHaveLength(0)
    expect(screen.queryAllByRole('link')).toHaveLength(0)
  })

  it('error renders the copy and Try again, with no verdict text present', async () => {
    overrideScansUnfilteredError()
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
    let scanCalls = 0
    overrideFindings()
    server.use(
      http.get(`${baseURL}/scans`, ({ request }) => {
        const status = new URL(request.url).searchParams.get('status')
        if (!status) {
          scanCalls += 1
          if (scanCalls === 1) {
            return new HttpResponse(null, { status: 500 })
          }
          return HttpResponse.json({ data: [latestScan], total: 1, page: 1 })
        }
        return HttpResponse.json({
          data: [latestSuccessfulScan],
          total: 1,
          page: 1,
        })
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

  it('the verdict states the total-derived number when it exceeds the rows shown', async () => {
    overrideFindings({ criticalData: [criticalFinding], criticalTotal: 37 })
    renderWithProviders(<Home />)

    await screen.findByTestId('home-verdict')
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      '37 things need your attention',
    )
  })

  it("loading renders no element in the verdict's position — no skeleton, spinner or placeholder", () => {
    server.use(
      http.get(`${baseURL}/scans`, async () => {
        await delay('infinite')
        return HttpResponse.json({ data: [], total: 0, page: 1 })
      }),
    )

    const { container } = renderWithProviders(<Home />)

    expect(container).toBeEmptyDOMElement()
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
        overrideScans(null, null)
      } else if (state === 'clear') {
        overrideFindings()
      } else if (state === 'error') {
        overrideScansUnfilteredError()
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
