import { act } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ToastProvider from './Toast'
import { useToast } from '@/hooks/useToast'

function Raiser() {
  const { show } = useToast()
  return (
    <>
      <button
        type="button"
        onClick={() => show('sam@acme.com is now an admin.')}
      >
        Promote
      </button>
      <button type="button" onClick={() => show('sam@acme.com was removed.')}>
        Remove
      </button>
    </>
  )
}

function renderRaiser() {
  return render(
    <ToastProvider>
      <Raiser />
    </ToastProvider>,
  )
}

describe('ToastProvider', () => {
  it('renders the raised message in a single toast', async () => {
    const user = userEvent.setup()
    renderRaiser()

    expect(screen.queryByTestId('toast')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Promote' }))

    expect(screen.getByTestId('toast')).toHaveTextContent(
      'sam@acme.com is now an admin.',
    )
  })

  it('replaces the showing toast instead of queueing a second', async () => {
    const user = userEvent.setup()
    renderRaiser()

    await user.click(screen.getByRole('button', { name: 'Promote' }))
    await user.click(screen.getByRole('button', { name: 'Remove' }))

    expect(screen.getAllByTestId('toast')).toHaveLength(1)
    expect(screen.getByTestId('toast')).toHaveTextContent(
      'sam@acme.com was removed.',
    )
    expect(screen.getByTestId('toast')).not.toHaveTextContent(
      'sam@acme.com is now an admin.',
    )
  })

  it('auto-dismisses after five seconds', async () => {
    vi.useFakeTimers()
    try {
      renderRaiser()

      fireEvent.click(screen.getByRole('button', { name: 'Promote' }))
      expect(screen.getByTestId('toast')).toBeInTheDocument()

      await act(async () => {
        vi.advanceTimersByTime(4999)
      })
      expect(screen.getByTestId('toast')).toBeInTheDocument()

      await act(async () => {
        vi.advanceTimersByTime(1)
      })
      expect(screen.queryByTestId('toast')).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('dismisses on the Dismiss affordance before the timer elapses', async () => {
    const user = userEvent.setup()
    renderRaiser()

    await user.click(screen.getByRole('button', { name: 'Promote' }))
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))

    expect(screen.queryByTestId('toast')).not.toBeInTheDocument()
  })
})
