import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import WaitingState from './WaitingState'

describe('WaitingState', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
    vi.setSystemTime(new Date('2026-10-23T12:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('counts elapsed time outside the announced status', () => {
    render(
      <WaitingState
        size="large"
        stage="Finding the easiest fixes"
        detail="Reading group 3 of 7"
        startedAt={Date.now() - 65_000}
        progress={{ done: 2, total: 7 }}
        testId="waiting"
      />,
    )

    const elapsed = screen.getByTestId('waiting-elapsed')
    expect(elapsed).toHaveTextContent('1:05')
    expect(elapsed).toHaveAttribute('aria-hidden', 'true')
    expect(screen.getByRole('status')).toHaveTextContent(
      'Finding the easiest fixesReading group 3 of 7',
    )
    expect(screen.getByRole('status')).not.toContainElement(elapsed)

    act(() => {
      vi.advanceTimersByTime(2_000)
    })
    expect(elapsed).toHaveTextContent('1:07')
  })

  it('stops the grid animation for reduced motion and offers Cancel only when given', async () => {
    vi.useRealTimers()
    const onCancel = vi.fn()
    const { container, rerender } = render(
      <WaitingState
        size="small"
        stage="Looking for an answer"
        detail="This can take up to a minute"
        startedAt={Date.now()}
      />,
    )

    const squares = container.querySelectorAll('.animate-grid-pulse')
    expect(squares).toHaveLength(9)
    squares.forEach((square) =>
      expect(square).toHaveClass('motion-reduce:animate-none'),
    )
    expect(screen.queryByRole('button')).not.toBeInTheDocument()

    rerender(
      <WaitingState
        size="small"
        stage="Looking for an answer"
        detail="This can take up to a minute"
        startedAt={Date.now()}
        cancelLabel="Cancel"
        onCancel={onCancel}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})
