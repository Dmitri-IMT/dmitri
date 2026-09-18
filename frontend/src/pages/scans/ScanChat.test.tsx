import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ScanChat from './ScanChat'
import { askScanAI, getScanAIChat } from '@/api/scans'
import { renderWithProviders } from '@/test/renderWithProviders'

vi.mock('@/api/scans', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/scans')>()),
  askScanAI: vi.fn(),
  getScanAIChat: vi.fn(),
}))

describe('ScanChat', () => {
  beforeEach(() => {
    vi.mocked(askScanAI).mockReset()
    vi.mocked(getScanAIChat).mockResolvedValue({ data: [] })
  })

  it('loads and renders the previous conversation history', async () => {
    vi.mocked(getScanAIChat).mockResolvedValue({
      data: [
        {
          message_id: 'message-1',
          question: 'Qual host devo priorizar?',
          answer: 'Priorize o host 192.168.1.10.',
          uncertainties: [],
          referenced_finding_ids: [],
          created_at: '2026-09-18T00:00:00Z',
        },
      ],
    })

    renderWithProviders(<ScanChat scanId="scan-1" />)

    expect(getScanAIChat).not.toHaveBeenCalled()
    await userEvent.setup().click(
      screen.getByRole('button', { name: 'Mostrar histórico' }),
    )
    expect(await screen.findByText('Qual host devo priorizar?')).toBeVisible()
    expect(screen.getByText('Priorize o host 192.168.1.10.')).toBeVisible()
    expect(getScanAIChat).toHaveBeenCalledWith('scan-1')
  })

  it('links referenced findings back to the scan detail', async () => {
    vi.mocked(askScanAI).mockResolvedValue({
      answer: 'Veja o achado relacionado.',
      uncertainties: [],
      referenced_finding_ids: ['finding-1'],
    })
    const user = userEvent.setup()
    renderWithProviders(<ScanChat scanId="scan-1" />)

    await user.type(screen.getByLabelText('Sua pergunta'), 'O que corrigir?')
    await user.click(screen.getByRole('button', { name: 'Perguntar' }))

    expect(await screen.findByRole('link', { name: 'Ver achado 1' })).toHaveAttribute(
      'href',
      '/scans/scan-1?finding=finding-1',
    )
  })

  it('sends a question and renders the grounded answer', async () => {
    vi.mocked(askScanAI).mockResolvedValue({
      answer: 'Priorize a atualização do serviço exposto.',
      uncertainties: ['O scan não confirma exploração ativa.'],
      referenced_finding_ids: [],
    })
    const user = userEvent.setup()
    renderWithProviders(<ScanChat scanId="scan-1" />)

    await user.type(
      screen.getByLabelText('Sua pergunta'),
      'O que devo corrigir primeiro?',
    )
    await user.click(screen.getByRole('button', { name: 'Perguntar' }))

    expect(askScanAI).toHaveBeenCalledWith(
      'scan-1',
      'O que devo corrigir primeiro?',
    )
    expect(
      await screen.findByText('Priorize a atualização do serviço exposto.'),
    ).toBeVisible()
    expect(
      screen.getByText('O scan não confirma exploração ativa.'),
    ).toBeVisible()
  })

  it('explains when the provider token limit was reached', async () => {
    vi.mocked(askScanAI).mockRejectedValueOnce({
      response: {
        data: {
          error: {
            code: 'ai_rate_limited',
            message:
              'Limite de tokens da IA atingido. Tente novamente em aproximadamente 8 segundos.',
          },
        },
      },
    })
    const user = userEvent.setup()
    renderWithProviders(<ScanChat scanId="scan-1" />)

    await user.type(screen.getByLabelText('Sua pergunta'), 'O que aconteceu?')
    await user.click(screen.getByRole('button', { name: 'Perguntar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Limite de tokens da IA atingido. Tente novamente em aproximadamente 8 segundos.',
    )
  })
})
