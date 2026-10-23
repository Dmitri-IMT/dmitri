import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CanceledError } from 'axios'
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

describe('ContextChat waiting', () => {
  beforeEach(() => {
    vi.mocked(askContextAI).mockReset()
  })

  it('shows the waiting state while asking and Cancel stops it without a toast', async () => {
    vi.mocked(askContextAI).mockImplementation(
      (_scope, _id, _question, _language, signal) =>
        new Promise((_resolve, reject) => {
          signal?.addEventListener('abort', () => reject(new CanceledError()))
        }),
    )
    const user = userEvent.setup()
    renderWithProviders(<ContextChat scope="scan" contextId="scan-1" />)

    await user.type(screen.getByLabelText('Your question'), 'What is wrong?')
    await user.click(screen.getByRole('button', { name: 'Ask' }))

    const waiting = await screen.findByTestId('assistant-waiting')
    expect(waiting).toHaveTextContent('Looking for an answer')
    expect(screen.getByLabelText('Your question')).toBeDisabled()

    await user.click(screen.getByTestId('assistant-cancel'))

    expect(screen.queryByTestId('assistant-waiting')).not.toBeInTheDocument()
    expect(screen.queryByTestId('toast')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Your question')).toBeEnabled()
  })
})
