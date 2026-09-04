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
  it('names the previous and next controls without writing the words', () => {
    renderPagination(2)

    expect(
      screen.getByRole('button', { name: 'Previous page' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Next page' }),
    ).toBeInTheDocument()
    expect(screen.getByTestId('scans-pagination')).not.toHaveTextContent(
      /Previous|Next|Showing/,
    )
  })

  it('lists every page and marks the current one', async () => {
    const user = userEvent.setup()
    const onPageChange = renderPagination(2)

    expect(screen.getByRole('button', { name: '2' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.getByRole('button', { name: '1' })).not.toHaveAttribute(
      'aria-current',
    )

    await user.click(screen.getByRole('button', { name: '3' }))
    expect(onPageChange).toHaveBeenCalledWith(3)
  })

  it('elides the middle of a long run of pages', () => {
    renderPagination(1, 400)

    expect(screen.getByRole('button', { name: '20' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '10' })).not.toBeInTheDocument()
    expect(screen.getByText('More pages')).toBeInTheDocument()
  })

  it('keeps the previous control rendered, inert, and out of the tab order on the first page', async () => {
    const user = userEvent.setup()
    const onPageChange = renderPagination(1)

    const previous = screen.getByTestId('scans-previous')

    expect(previous).toBeDisabled()
    expect(previous).toHaveAttribute('tabindex', '-1')
    expect(screen.getByTestId('scans-next')).toBeEnabled()
    await user.click(previous)
    expect(onPageChange).not.toHaveBeenCalled()
  })

  it('keeps the next control rendered, inert, and out of the tab order on the last page', async () => {
    const user = userEvent.setup()
    const onPageChange = renderPagination(3)

    const next = screen.getByTestId('scans-next')

    expect(next).toBeDisabled()
    expect(next).toHaveAttribute('tabindex', '-1')
    expect(screen.getByTestId('scans-previous')).toBeEnabled()
    await user.click(next)
    expect(onPageChange).not.toHaveBeenCalled()
  })

  it('does not render when all rows fit on one page', () => {
    renderPagination(1, 20)

    expect(screen.queryByTestId('scans-pagination')).not.toBeInTheDocument()
  })
})
