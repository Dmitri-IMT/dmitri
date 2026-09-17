import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ScanChat from './ScanChat'
import { askScanAI } from '@/api/scans'
import { renderWithProviders } from '@/test/renderWithProviders'

vi.mock('@/api/scans', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/scans')>()),
  askScanAI: vi.fn(),
}))

describe('ScanChat', () => {
  beforeEach(() => {
    vi.mocked(askScanAI).mockReset()
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
})
