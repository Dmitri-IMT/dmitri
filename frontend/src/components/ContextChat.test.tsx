import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/renderWithProviders'
import { askContextAI } from '@/api/ai'
import ContextChat from './ContextChat'

vi.mock('@/api/ai', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/ai')>()),
  askContextAI: vi.fn(),
}))

describe('ContextChat', () => {
  it('raises a toast when the ask fails, and adds no error text inside the card', async () => {
    vi.mocked(askContextAI).mockRejectedValue(new Error('boom'))
    const user = userEvent.setup()
    renderWithProviders(<ContextChat scope="scan" contextId="scan-1" />)

    await user.type(screen.getByLabelText('Your question'), 'What is wrong?')
    await user.click(screen.getByRole('button', { name: 'Ask' }))

    expect(await screen.findByTestId('toast')).toHaveTextContent(
      'Unable to get an answer right now. Try again.',
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
