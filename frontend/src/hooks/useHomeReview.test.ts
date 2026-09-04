import { act, createElement, type ReactNode } from 'react'
import { describe, expect, it, afterEach } from 'vitest'
import { delay, http, HttpResponse } from 'msw'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { server } from '@/test/setup'
import {
  latestScan,
  latestSuccessfulScan,
  criticalFinding,
  highFinding,
} from '@/test/mswHandlers'
import { getLatestScan, getLatestSuccessfulScan } from '@/api/scans'
import { HOME_FINDINGS_PER_PAGE, listFindings } from '@/api/findings'
import { useHomeReview } from './useHomeReview'

const baseURL = 'http://localhost:8000/api/v1'

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children)
  }
}

function renderHomeReview() {
  return renderHook(() => useHomeReview(), { wrapper: createWrapper() })
}

describe('useHomeReview', () => {
  it('reports loading while the reads are in flight', async () => {
    server.use(
      http.get(`${baseURL}/scans`, async () => {
        await delay('infinite')
        return HttpResponse.json({ data: [], total: 0, page: 1 })
      }),
    )

    const { result } = renderHomeReview()

    expect(result.current.state).toBe('loading')
  })

  it('reports blank when the unfiltered latest scan is empty, without touching findings', async () => {
    let scansRequests = 0
    let findingsRequests = 0
    server.use(
      http.get(`${baseURL}/scans`, ({ request }) => {
        scansRequests += 1
        const status = new URL(request.url).searchParams.get('status')
        if (!status) {
          return HttpResponse.json({ data: [], total: 0, page: 1 })
        }
        return HttpResponse.json({ data: [latestScan], total: 1, page: 1 })
      }),
      http.get(`${baseURL}/findings`, () => {
        findingsRequests += 1
        return HttpResponse.json({ data: [], total: 0, page: 1 })
      }),
    )

    const { result } = renderHomeReview()

    await waitFor(() => expect(result.current.state).toBe('blank'))

    expect(scansRequests).toBe(2)
    expect(findingsRequests).toBe(0)
  })

  it('reports clear when the unfiltered scan exists but no critical or high findings do', async () => {
    server.use(
      http.get(`${baseURL}/findings`, () =>
        HttpResponse.json({ data: [], total: 0, page: 1 }),
      ),
    )

    const { result } = renderHomeReview()

    await waitFor(() => expect(result.current.state).toBe('clear'))
  })

  it('reports pending with the deck populated when critical or high findings exist', async () => {
    server.use(
      http.get(`${baseURL}/findings`, ({ request }) => {
        const severity = new URL(request.url).searchParams.get('severity')
        if (severity === 'critical') {
          return HttpResponse.json({
            data: [criticalFinding],
            total: 1,
            page: 1,
          })
        }
        return HttpResponse.json({ data: [], total: 0, page: 1 })
      }),
    )

    const { result } = renderHomeReview()

    await waitFor(() => expect(result.current.state).toBe('pending'))
    if (result.current.state !== 'pending') throw new Error('unreachable')
    expect(result.current.reviewCount).toBe(1)
    expect(result.current.deckFindings).toEqual([criticalFinding])
  })

  it('treats a 404 on the unfiltered scan read as an error, never as blank', async () => {
    server.use(
      http.get(`${baseURL}/scans`, ({ request }) => {
        const status = new URL(request.url).searchParams.get('status')
        if (!status) {
          return new HttpResponse(null, { status: 404 })
        }
        return HttpResponse.json({ data: [latestScan], total: 1, page: 1 })
      }),
    )

    const { result } = renderHomeReview()

    await waitFor(() => expect(result.current.state).toBe('error'))
  })

  it('reports error when the unfiltered scan read 500s', async () => {
    server.use(
      http.get(`${baseURL}/scans`, ({ request }) => {
        const status = new URL(request.url).searchParams.get('status')
        if (!status) {
          return new HttpResponse(null, { status: 500 })
        }
        return HttpResponse.json({ data: [latestScan], total: 1, page: 1 })
      }),
    )

    const { result } = renderHomeReview()

    await waitFor(() => expect(result.current.state).toBe('error'))
  })

  it('reports error when the latest-successful scan read 500s', async () => {
    server.use(
      http.get(`${baseURL}/scans`, ({ request }) => {
        const status = new URL(request.url).searchParams.get('status')
        if (status === 'completed') {
          return new HttpResponse(null, { status: 500 })
        }
        return HttpResponse.json({ data: [latestScan], total: 1, page: 1 })
      }),
    )

    const { result } = renderHomeReview()

    await waitFor(() => expect(result.current.state).toBe('error'))
  })

  it('reports error when the critical findings read 500s', async () => {
    server.use(
      http.get(`${baseURL}/findings`, ({ request }) => {
        const severity = new URL(request.url).searchParams.get('severity')
        if (severity === 'critical') {
          return new HttpResponse(null, { status: 500 })
        }
        return HttpResponse.json({ data: [], total: 0, page: 1 })
      }),
    )

    const { result } = renderHomeReview()

    await waitFor(() => expect(result.current.state).toBe('error'))
  })

  it('reports error when the high findings read 500s', async () => {
    server.use(
      http.get(`${baseURL}/findings`, ({ request }) => {
        const severity = new URL(request.url).searchParams.get('severity')
        if (severity === 'high') {
          return new HttpResponse(null, { status: 500 })
        }
        return HttpResponse.json({ data: [], total: 0, page: 1 })
      }),
    )

    const { result } = renderHomeReview()

    await waitFor(() => expect(result.current.state).toBe('error'))
  })

  it('recovers to the right terminal state on retry after a transient failure', async () => {
    let scanCalls = 0
    server.use(
      http.get(`${baseURL}/findings`, () =>
        HttpResponse.json({ data: [], total: 0, page: 1 }),
      ),
      http.get(`${baseURL}/scans`, ({ request }) => {
        const status = new URL(request.url).searchParams.get('status')
        if (!status) {
          scanCalls += 1
          if (scanCalls === 1) {
            return new HttpResponse(null, { status: 500 })
          }
          return HttpResponse.json({ data: [latestScan], total: 1, page: 1 })
        }
        return HttpResponse.json({ data: [latestScan], total: 1, page: 1 })
      }),
    )

    const { result } = renderHomeReview()

    await waitFor(() => expect(result.current.state).toBe('error'))

    await act(async () => {
      result.current.retry()
    })

    await waitFor(() => expect(result.current.state).toBe('clear'))
  })

  describe('request shape', () => {
    afterEach(() => {
      server.events.removeAllListeners()
    })

    it('issues exactly four requests on load, none after, and only retry adds more', async () => {
      const requests: URL[] = []
      server.events.on('request:match', ({ request }) => {
        requests.push(new URL(request.url))
      })
      server.use(
        http.get(`${baseURL}/findings`, ({ request }) => {
          const severity = new URL(request.url).searchParams.get('severity')
          if (severity === 'critical') {
            return HttpResponse.json({
              data: [criticalFinding],
              total: 1,
              page: 1,
            })
          }
          return HttpResponse.json({ data: [], total: 0, page: 1 })
        }),
      )

      const { result } = renderHomeReview()

      await waitFor(() => expect(result.current.state).toBe('pending'))

      expect(requests).toHaveLength(4)

      const scanRequests = requests.filter((url) =>
        url.pathname.endsWith('/scans'),
      )
      const findingRequests = requests.filter((url) =>
        url.pathname.endsWith('/findings'),
      )
      expect(scanRequests).toHaveLength(2)
      expect(findingRequests).toHaveLength(2)

      for (const url of requests) {
        const perPage = url.searchParams.get('per_page')
        if (perPage !== null) {
          expect(['1', '100']).toContain(perPage)
        }
      }
      for (const url of findingRequests) {
        expect(url.searchParams.getAll('severity')).toHaveLength(1)
      }
      const severities = findingRequests.map((url) =>
        url.searchParams.get('severity'),
      )
      expect(new Set(severities)).toEqual(new Set(['critical', 'high']))

      await new Promise((resolve) => setTimeout(resolve, 0))
      expect(requests).toHaveLength(4)

      await act(async () => {
        result.current.retry()
      })
      await waitFor(() => expect(requests.length).toBeGreaterThan(4))
      expect(requests).toHaveLength(8)
    })
  })

  describe('resource modules over MSW', () => {
    it('getLatestScan and getLatestSuccessfulScan send the documented query and parse genuinely different records from the default handler', async () => {
      const unfiltered = await getLatestScan()
      const successful = await getLatestSuccessfulScan()

      expect(unfiltered?.scan_id).toBe(latestScan.scan_id)
      expect(successful?.scan_id).toBe(latestSuccessfulScan.scan_id)
      expect(unfiltered?.scan_id).not.toBe(successful?.scan_id)
    })

    it('getLatestScan returns null on an empty envelope', async () => {
      server.use(
        http.get(`${baseURL}/scans`, () =>
          HttpResponse.json({ data: [], total: 0, page: 1 }),
        ),
      )

      await expect(getLatestScan()).resolves.toBeNull()
    })

    it('getLatestScan rejects rather than nulling out a 404', async () => {
      server.use(
        http.get(
          `${baseURL}/scans`,
          () => new HttpResponse(null, { status: 404 }),
        ),
      )

      await expect(getLatestScan()).rejects.toBeTruthy()
    })

    it('listFindings branches on severity and returns the whole envelope with total', async () => {
      const critical = await listFindings({
        scan_id: latestScan.scan_id,
        severity: 'critical',
        per_page: HOME_FINDINGS_PER_PAGE,
      })
      const high = await listFindings({
        scan_id: latestScan.scan_id,
        severity: 'high',
        per_page: HOME_FINDINGS_PER_PAGE,
      })

      expect(critical.data).toEqual([criticalFinding])
      expect(critical.total).toBe(1)
      expect(high.data).toEqual([highFinding])
      expect(high.total).toBe(1)
    })
  })
})
