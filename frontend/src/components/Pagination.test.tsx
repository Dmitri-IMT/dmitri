import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Pagination from './Pagination'

function renderPagination(page: number, total = 47) {
  const onPageChange = vi.fn()

  render(
    <Pagination
      page={page}
      perPage={20}
      total={total}
      onPageChange={onPageChange}
      testId="scans"
    />,
  )

  return onPageChange
}

describe('Pagination', () => {
  it('shows the range for a middle page', () => {
    renderPagination(2)

    expect(screen.getByTestId('scans-range')).toHaveTextContent(
      'Showing 21–40 of 47',
    )
  })

  it('keeps Previous rendered, greyed, inert, and out of the tab order on the first page', async () => {
    const user = userEvent.setup()
    const onPageChange = renderPagination(1)

    const previous = screen.getByTestId('scans-previous')

    expect(previous).toBeDisabled()
    expect(previous).toHaveAttribute('tabindex', '-1')
    expect(previous).toHaveClass(
      'disabled:pointer-events-none',
      'disabled:opacity-50',
    )
    expect(screen.getByTestId('scans-next')).toBeEnabled()
    await user.click(previous)
    expect(onPageChange).not.toHaveBeenCalled()
  })

  it('keeps Next rendered, greyed, inert, and out of the tab order on the last page', async () => {
    const user = userEvent.setup()
    const onPageChange = renderPagination(3)

    const next = screen.getByTestId('scans-next')

    expect(next).toBeDisabled()
    expect(next).toHaveAttribute('tabindex', '-1')
    expect(next).toHaveClass(
      'disabled:pointer-events-none',
      'disabled:opacity-50',
    )
    expect(screen.getByTestId('scans-previous')).toBeEnabled()
    await user.click(next)
    expect(onPageChange).not.toHaveBeenCalled()
  })

  it('does not render when all rows fit on one page', () => {
    renderPagination(1, 20)

    expect(screen.queryByTestId('scans-pagination')).not.toBeInTheDocument()
  })
})
