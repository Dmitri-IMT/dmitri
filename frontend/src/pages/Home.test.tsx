import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import {
  adminProfile,
  viewerProfile,
  latestScan,
  latestSuccessfulScan,
  criticalFinding,
} from '@/test/mswHandlers'
import type { components } from '@/types/openapi'
import Home from './Home'

type ScanSummary = components['schemas']['ScanSummary']
type FindingRecord = components['schemas']['FindingRecord']

const baseURL = 'http://localhost:8000/api/v1'

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
  it('AC 9 — all-clear shows the verdict and context sentence, and no review item', async () => {
    overrideFindings()
    renderWithProviders(<Home />)

    await screen.findByTestId('home-verdict')
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      'Nothing needs your attention.',
    )
    expect(screen.getByTestId('home-context')).toHaveTextContent(
      /Last scan finished .+ — 12 hosts, no critical findings\./,
    )
    expect(screen.queryByTestId('home-deck')).not.toBeInTheDocument()
    expect(screen.queryByTestId('home-item-scan')).not.toBeInTheDocument()
    expect(screen.queryByTestId('home-item-coverage')).not.toBeInTheDocument()
    expect(screen.getByTestId('home-footer')).toBeInTheDocument()
    expect(screen.getByTestId('home-footer-scan')).toHaveTextContent(
      /Last scan: .+ · 12 hosts · standard mode/,
    )
    expect(screen.getByTestId('home-footer-pi')).toHaveTextContent(
      /Pi status: online · last seen .+/,
    )
  })

  it('AC 11 — medium/low-only findings yield the all-clear verdict with no finding card', async () => {
    overrideFindings()
    renderWithProviders(<Home />)

    await screen.findByTestId('home-verdict')
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      'Nothing needs your attention.',
    )
    expect(screen.queryByTestId('home-item-severity')).not.toBeInTheDocument()
    expect(screen.queryByTestId('home-deck-card')).not.toBeInTheDocument()
  })

  it("AC 10 — items-pending shows the deck's first card naming the CVE and the host IP", async () => {
    renderWithProviders(<Home />)

    await screen.findByTestId('home-deck-card')
    expect(screen.getByTestId('home-deck-card')).toHaveTextContent(
      /CVE-2023-38408 on 192\.168\.1\.42\./,
    )
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      '2 things need your review.',
    )
    expect(screen.getByTestId('home-footer-pi')).toHaveTextContent(
      /Pi status: online · last seen .+/,
    )
    expect(screen.queryByTestId('home-footer-scan')).not.toBeInTheDocument()
  })

  it('items-pending order is finding deck → failed-scan card → stale-coverage card', async () => {
    overrideScans(failedScan, staleSuccessfulScan)
    renderWithProviders(<Home />)

    await screen.findByTestId('home-deck-card')
    const deck = screen.getByTestId('home-deck')
    const scanCard = screen.getByTestId('home-item-scan')
    const coverageCard = screen.getByTestId('home-item-coverage')

    expect(
      deck.compareDocumentPosition(scanCard) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(
      scanCard.compareDocumentPosition(coverageCard) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      '4 things need your review.',
    )
  })

  it('AC 12 — the failed-scan card renders outside the deck, with the singular verdict copy', async () => {
    overrideFindings()
    overrideScans(failedScan, latestSuccessfulScan)
    renderWithProviders(<Home />)

    await screen.findByTestId('home-item-scan')
    expect(screen.getByTestId('home-item-scan')).toHaveTextContent(
      "Last night's scan didn't finish.",
    )
    expect(screen.queryByTestId('home-deck')).not.toBeInTheDocument()
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      '1 thing needs your review.',
    )
  })

  it('AC 13 — the stale-coverage card renders outside the deck', async () => {
    overrideFindings()
    overrideScans(latestScan, staleSuccessfulScan)
    renderWithProviders(<Home />)

    await screen.findByTestId('home-item-coverage')
    expect(screen.getByTestId('home-item-coverage')).toHaveTextContent(
      'No successful scan in 9 days.',
    )
    expect(screen.queryByTestId('home-deck')).not.toBeInTheDocument()
  })

  it('AC 14 — admin blank links to the first scan and retires the Pi sentence', async () => {
    overrideUser(adminProfile)
    overrideScans(null, null)
    renderWithProviders(<Home />)

    expect(await screen.findByTestId('home-blank-body')).toHaveTextContent(
      'Dmitri scans your network for devices and known vulnerabilities, then reports anything worth your attention here.',
    )
    const cta = screen.getByTestId('first-scan-cta')
    expect(cta).toHaveAttribute('href', '/agents')
    expect(screen.queryByTestId('first-scan-note')).not.toBeInTheDocument()
    expect(
      screen.queryByText('Scanning is set up on the Pi itself.'),
    ).not.toBeInTheDocument()
    expect(screen.queryByTestId('home-footer')).not.toBeInTheDocument()
  })

  it('AC 14 — viewer blank shows only the admin-direction note', async () => {
    overrideUser(viewerProfile)
    overrideScans(null, null)
    renderWithProviders(<Home />)

    expect(await screen.findByTestId('first-scan-note')).toHaveTextContent(
      'Ask your admin to run the first scan.',
    )
    expect(screen.queryByTestId('first-scan-cta')).not.toBeInTheDocument()
    expect(screen.queryAllByRole('button')).toHaveLength(0)
    expect(screen.queryAllByRole('link')).toHaveLength(0)
    expect(screen.queryByTestId('home-footer')).not.toBeInTheDocument()
  })

  it('AC 15 — error renders the copy and Retry, with no verdict text present', async () => {
    overrideScansUnfilteredError()
    renderWithProviders(<Home />)

    await screen.findByTestId('home-error')
    expect(screen.getByTestId('home-error')).toHaveTextContent(
      "Couldn't load your network's status.",
    )
    expect(screen.getByRole('button', { name: 'Retry' })).toBeEnabled()
    expect(screen.queryByTestId('home-verdict')).not.toBeInTheDocument()
  })

  it('AC 16 — retry recovers to the right state after a transient failure', async () => {
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

    await user.click(screen.getByRole('button', { name: 'Retry' }))

    await screen.findByTestId('home-verdict')
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      'Nothing needs your attention.',
    )
  })

  it('AC 17 — the verdict states the total-derived number when it exceeds the rows shown', async () => {
    overrideFindings({ criticalData: [criticalFinding], criticalTotal: 37 })
    renderWithProviders(<Home />)

    await screen.findByTestId('home-verdict')
    expect(screen.getByTestId('home-verdict')).toHaveTextContent(
      '37 things need your review.',
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
    'AC 7 — every rendered control is enabled with no aria-disabled, %s / %s',
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
