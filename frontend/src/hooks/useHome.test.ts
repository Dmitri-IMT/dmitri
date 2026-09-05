import { act, createElement, type ReactNode } from 'react'
import { beforeEach, describe, expect, it } from 'vitest'
import { delay, http, HttpResponse } from 'msw'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { server } from '@/test/setup'
import { criticalFinding, latestSuccessfulScan } from '@/test/mswHandlers'
import { queryKeys } from '@/api/queryKeys'
import {
  HOME_ACTIVITY_PER_PAGE,
  HOME_ATTENTION_PER_PAGE,
  HOME_EVENTS_PER_PAGE,
  type HomePages,
  type HomeSnapshot,
} from '@/api/home'
import { useHome } from './useHome'

const baseURL = 'http://localhost:8000/api/v1'

const firstPages: HomePages = {
  attentionPage: 1,
  eventsPage: 1,
  activityPage: 1,
}

function snapshotFixture(
  reviewState: HomeSnapshot['review_state'],
  attentionPage = 1,
): HomeSnapshot {
  return {
    review_state: reviewState,
    review_count: reviewState === 'pending' ? 1 : 0,
    latest_successful_scan:
      reviewState === 'blank' ? null : latestSuccessfulScan,
    notices: [],
    attention: {
      data: reviewState === 'pending' ? [criticalFinding] : [],
      total: reviewState === 'pending' ? 9 : 0,
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
  }
}

let requestUrls: URL[] = []

function serveHome(resolve: (url: URL) => Response | Promise<Response>): void {
  server.use(
    http.get(`${baseURL}/home`, async ({ request }) => {
      const url = new URL(request.url)
      requestUrls.push(url)
      return resolve(url)
    }),
  )
}

function serveSnapshot(reviewState: HomeSnapshot['review_state']): void {
  serveHome((url) =>
    HttpResponse.json(
      snapshotFixture(
        reviewState,
        Number(url.searchParams.get('attention_page') ?? '1'),
      ),
    ),
  )
}

function renderHome(pages: HomePages = firstPages) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
  return renderHook((props: HomePages) => useHome(props), {
    initialProps: pages,
    wrapper,
  })
}

beforeEach(() => {
  requestUrls = []
})

describe('useHome', () => {
  it('reports loading while the snapshot is in flight', async () => {
    serveHome(async () => {
      await delay('infinite')
      return HttpResponse.json(snapshotFixture('clear'))
    })

    const { result } = renderHome()

    expect(result.current.state).toBe('loading')
    expect(result.current).not.toHaveProperty('snapshot')
  })

  it.each(['blank', 'clear', 'pending'] as const)(
    'reports %s from the snapshot review state',
    async (reviewState) => {
      serveSnapshot(reviewState)

      const { result } = renderHome()

      await waitFor(() => expect(result.current.state).toBe(reviewState))
      if (
        result.current.state === 'loading' ||
        result.current.state === 'error'
      )
        throw new Error('unreachable')
      expect(result.current.snapshot.review_state).toBe(reviewState)
    },
  )

  it('reports error and refetches the snapshot on retry', async () => {
    let calls = 0
    serveHome(() => {
      calls += 1
      if (calls === 1) return new HttpResponse(null, { status: 500 })
      return HttpResponse.json(snapshotFixture('pending'))
    })

    const { result } = renderHome()

    await waitFor(() => expect(result.current.state).toBe('error'))
    const { retry } = result.current

    await act(async () => {
      retry()
    })

    await waitFor(() => expect(result.current.state).toBe('pending'))
    expect(calls).toBe(2)
  })

  it('pages attention without disturbing events or activity', async () => {
    serveSnapshot('pending')

    const { result, rerender } = renderHome()

    await waitFor(() => expect(result.current.state).toBe('pending'))

    rerender({ ...firstPages, attentionPage: 3 })

    await waitFor(() => {
      if (
        result.current.state === 'loading' ||
        result.current.state === 'error'
      )
        throw new Error('unreachable')
      expect(result.current.snapshot.attention.page).toBe(3)
    })

    expect(
      queryKeys.home.snapshot({ ...firstPages, attentionPage: 3 }),
    ).toEqual(['home', 'snapshot', 3, 1, 1])
    expect(
      requestUrls.map((url) => [
        url.searchParams.get('attention_page'),
        url.searchParams.get('events_page'),
        url.searchParams.get('activity_page'),
      ]),
    ).toEqual([
      ['1', '1', '1'],
      ['3', '1', '1'],
    ])
  })

  it('keeps the previous snapshot rendered across a page change', async () => {
    let calls = 0
    serveHome(async (url) => {
      calls += 1
      if (calls > 1) await delay(20)
      return HttpResponse.json(
        snapshotFixture(
          'pending',
          Number(url.searchParams.get('attention_page') ?? '1'),
        ),
      )
    })

    const { result, rerender } = renderHome()

    await waitFor(() => expect(result.current.state).toBe('pending'))

    rerender({ ...firstPages, attentionPage: 2 })

    expect(result.current.state).toBe('pending')
    if (result.current.state === 'loading' || result.current.state === 'error')
      throw new Error('unreachable')
    expect(result.current.snapshot.attention.page).toBe(1)

    await waitFor(() => {
      if (
        result.current.state === 'loading' ||
        result.current.state === 'error'
      )
        throw new Error('unreachable')
      expect(result.current.snapshot.attention.page).toBe(2)
    })
  })

  it('never sends a per_page parameter', async () => {
    serveSnapshot('clear')

    const { result, rerender } = renderHome()

    await waitFor(() => expect(result.current.state).toBe('clear'))
    rerender({ attentionPage: 2, eventsPage: 2, activityPage: 2 })
    await waitFor(() => expect(requestUrls).toHaveLength(2))

    for (const url of requestUrls) {
      for (const name of url.searchParams.keys()) {
        expect(name).not.toContain('per_page')
      }
    }
  })

  it('exports the server page sizes', () => {
    expect(HOME_ATTENTION_PER_PAGE).toBe(8)
    expect(HOME_EVENTS_PER_PAGE).toBe(5)
    expect(HOME_ACTIVITY_PER_PAGE).toBe(8)
  })
})
