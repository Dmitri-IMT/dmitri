import { beforeEach, describe, expect, it, vi } from 'vitest'
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
  beforeEach(() => {
    vi.mocked(askContextAI).mockReset()
  })

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

  it('removes the one-shot ask button once it has an answer, so it cannot be asked again', async () => {
    vi.mocked(askContextAI).mockResolvedValue({
      answer: 'It is fine.',
      uncertainties: [],
      referenced_finding_ids: [],
    })
    const user = userEvent.setup()
    renderWithProviders(
      <ContextChat
        scope="finding"
        contextId="finding-1"
        presetQuestion="Explain this."
        askLabel="Explain with AI"
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Explain with AI' }))

    expect(await screen.findByText('It is fine.')).toBeVisible()
    expect(
      screen.queryByRole('button', { name: 'Explain with AI' }),
    ).not.toBeInTheDocument()
    expect(askContextAI).toHaveBeenCalledTimes(1)
  })
})
