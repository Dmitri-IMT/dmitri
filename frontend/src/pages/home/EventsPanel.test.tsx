import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import EventsPanel from './EventsPanel'
import { HOME_EVENTS_PER_PAGE } from '@/api/home'
import type { components } from '@/types/openapi'

type HomeEvent = components['schemas']['HomeEvent']

function renderPanel({
  data = [],
  total = data.length,
  page = 1,
}: {
  data?: HomeEvent[]
  total?: number
  page?: number
} = {}) {
  const onPageChange = vi.fn()

  render(
    <EventsPanel
      data={data}
      total={total}
      page={page}
      onPageChange={onPageChange}
    />,
  )

  return onPageChange
}

describe('EventsPanel', () => {
  it('prints each row text verbatim from the server', () => {
    renderPanel({
      data: [
        {
          kind: 'box_offline',
          text: 'Rontho HQ has been offline for 3 days',
          occurred_at: '2026-09-01T12:00:00Z',
        },
        {
          kind: 'member_idle',
          text: 'maria@ronthocorp.com has not signed in for 62 days',
          occurred_at: '2026-09-01T12:00:00Z',
        },
      ],
    })

    expect(screen.getByTestId('home-events-row-0')).toHaveTextContent(
      'Rontho HQ has been offline for 3 days',
    )
    expect(screen.getByTestId('home-events-row-1')).toHaveTextContent(
      'maria@ronthocorp.com has not signed in for 62 days',
    )
  })

  it('shows the blank sentence and omits the list when there are no rows', () => {
    renderPanel({ data: [], total: 0 })

    expect(screen.getByTestId('home-events-blank')).toHaveTextContent(
      'Nothing to report right now.',
    )
    expect(screen.queryByTestId('home-events-list')).not.toBeInTheDocument()
  })

  it('hides pagination when every row fits on one page', () => {
    renderPanel({
      data: [
        {
          kind: 'box_offline',
          text: 'One event',
          occurred_at: '2026-09-01T12:00:00Z',
        },
      ],
      total: HOME_EVENTS_PER_PAGE,
    })

    expect(
      screen.queryByTestId('home-events-pagination'),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('navigation', { name: 'Events pages' }),
    ).not.toBeInTheDocument()
  })

  it('shows pagination named Events pages when total exceeds the page size', () => {
    renderPanel({
      data: [
        {
          kind: 'box_offline',
          text: 'One event',
          occurred_at: '2026-09-01T12:00:00Z',
        },
      ],
      total: HOME_EVENTS_PER_PAGE + 1,
      page: 1,
    })

    expect(
      screen.getByRole('navigation', { name: 'Events pages' }),
    ).toBeInTheDocument()
    expect(screen.getByTestId('home-events-pagination')).toBeInTheDocument()
    expect(screen.getByTestId('home-events-previous')).toBeInTheDocument()
    expect(screen.getByTestId('home-events-next')).toBeInTheDocument()
    expect(screen.getByTestId('home-events-page-1')).toBeInTheDocument()
    expect(screen.getByTestId('home-events-page-2')).toBeInTheDocument()
  })

  it('calls onPageChange when a page number is clicked', async () => {
    const user = userEvent.setup()
    const onPageChange = renderPanel({
      data: [
        {
          kind: 'box_offline',
          text: 'One event',
          occurred_at: '2026-09-01T12:00:00Z',
        },
      ],
      total: HOME_EVENTS_PER_PAGE + 1,
      page: 1,
    })

    await user.click(screen.getByRole('button', { name: '2' }))
    expect(onPageChange).toHaveBeenCalledWith(2)
  })

  it('exposes the widget and heading test ids from the design contract', () => {
    renderPanel()

    expect(screen.getByTestId('home-events-heading')).toHaveTextContent(
      'Events',
    )
    expect(document.getElementById('home-events-panel')).toBe(
      screen.getByTestId('home-events-heading').closest('#home-events-panel'),
    )
  })
})
