import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ActivityPanel from './ActivityPanel'
import { HOME_ACTIVITY_PER_PAGE } from '@/api/home'
import type { components } from '@/types/openapi'

type HomeActivityItem = components['schemas']['HomeActivityItem']

const NOW = new Date('2026-09-05T12:00:00Z')

function renderPanel({
  data = [],
  total = data.length,
  page = 1,
}: {
  data?: HomeActivityItem[]
  total?: number
  page?: number
} = {}) {
  const onPageChange = vi.fn()

  render(
    <ActivityPanel
      data={data}
      total={total}
      page={page}
      onPageChange={onPageChange}
      now={NOW}
    />,
  )

  return onPageChange
}

describe('ActivityPanel', () => {
  it('prints each row text verbatim from the server', () => {
    renderPanel({
      data: [
        {
          kind: 'scan_finished',
          occurred_at: '2026-09-05T06:12:00Z',
          text: 'Standard scan finished',
        },
        {
          kind: 'role_changed',
          occurred_at: '2026-09-04T19:22:00Z',
          text: "gui@ronthocorp.com changed maria@ronthocorp.com's role to Viewer",
        },
      ],
    })

    expect(screen.getByTestId('home-activity-row-0-text')).toHaveTextContent(
      'Standard scan finished',
    )
    expect(screen.getByTestId('home-activity-row-1-text')).toHaveTextContent(
      "gui@ronthocorp.com changed maria@ronthocorp.com's role to Viewer",
    )
  })

  it('renders Timestamp on occurred_at in the time cell', () => {
    renderPanel({
      data: [
        {
          kind: 'scan_finished',
          occurred_at: '2026-09-05T06:12:00Z',
          text: 'Standard scan finished',
        },
      ],
    })

    const timeCell = screen.getByTestId('home-activity-row-0-time')
    const time = timeCell.querySelector('time')

    expect(time).toBeInTheDocument()
    expect(time).toHaveAttribute('datetime', '2026-09-05T06:12:00Z')
    expect(time?.textContent?.length).toBeGreaterThan(0)
  })

  it('shows the blank sentence and omits the list when there are no rows', () => {
    renderPanel({ data: [], total: 0 })

    expect(screen.getByTestId('home-activity-blank')).toHaveTextContent(
      'Nothing has been recorded yet.',
    )
    expect(screen.queryByTestId('home-activity-list')).not.toBeInTheDocument()
  })

  it('hides pagination when every row fits on one page', () => {
    renderPanel({
      data: [
        {
          kind: 'scan_finished',
          occurred_at: '2026-09-05T06:12:00Z',
          text: 'Standard scan finished',
        },
      ],
      total: HOME_ACTIVITY_PER_PAGE,
    })

    expect(
      screen.queryByTestId('home-activity-pagination'),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('navigation', { name: 'Activity pages' }),
    ).not.toBeInTheDocument()
  })

  it('shows pagination named Activity pages when total exceeds the page size', () => {
    renderPanel({
      data: [
        {
          kind: 'scan_finished',
          occurred_at: '2026-09-05T06:12:00Z',
          text: 'Standard scan finished',
        },
      ],
      total: HOME_ACTIVITY_PER_PAGE + 1,
      page: 1,
    })

    expect(
      screen.getByRole('navigation', { name: 'Activity pages' }),
    ).toBeInTheDocument()
    expect(screen.getByTestId('home-activity-pagination')).toBeInTheDocument()
    expect(screen.getByTestId('home-activity-previous')).toBeInTheDocument()
    expect(screen.getByTestId('home-activity-next')).toBeInTheDocument()
    expect(screen.getByTestId('home-activity-page-1')).toBeInTheDocument()
    expect(screen.getByTestId('home-activity-page-2')).toBeInTheDocument()
  })

  it('calls onPageChange when a page number is clicked', async () => {
    const user = userEvent.setup()
    const onPageChange = renderPanel({
      data: [
        {
          kind: 'scan_finished',
          occurred_at: '2026-09-05T06:12:00Z',
          text: 'Standard scan finished',
        },
      ],
      total: HOME_ACTIVITY_PER_PAGE + 1,
      page: 1,
    })

    await user.click(screen.getByRole('button', { name: '2' }))
    expect(onPageChange).toHaveBeenCalledWith(2)
  })

  it('exposes the widget, row, and heading test ids from the design contract', () => {
    renderPanel({
      data: [
        {
          kind: 'scan_finished',
          occurred_at: '2026-09-05T06:12:00Z',
          text: 'Standard scan finished',
        },
      ],
    })

    expect(screen.getByTestId('home-activity-heading')).toHaveTextContent(
      'Activity',
    )
    expect(screen.getByTestId('home-activity-list')).toBeInTheDocument()
    expect(screen.getByTestId('home-activity-row-0')).toBeInTheDocument()
    expect(screen.getByTestId('home-activity-row-0-time')).toBeInTheDocument()
    expect(screen.getByTestId('home-activity-row-0-text')).toBeInTheDocument()
    expect(document.getElementById('home-activity-panel')).toBe(
      screen
        .getByTestId('home-activity-heading')
        .closest('#home-activity-panel'),
    )
  })
})
