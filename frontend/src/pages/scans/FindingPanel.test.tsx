import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { ReactElement } from 'react'
import ToastProvider from '@/components/Toast'
import FindingPanel from './FindingPanel'
import { criticalFinding } from '@/test/mswHandlers'
import { askContextAI } from '@/api/ai'

vi.mock('@/api/ai', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/ai')>()),
  askContextAI: vi.fn(),
}))

function renderPanel(ui: ReactElement) {
  return render(<ToastProvider>{ui}</ToastProvider>)
}

describe('FindingPanel risk', () => {
  it('distinguishes unavailable scores from zero and displays the explanation', () => {
    const { rerender } = renderPanel(<FindingPanel finding={criticalFinding} />)
    expect(screen.getByText('Not calculated')).toBeVisible()
    rerender(
      <ToastProvider>
        <FindingPanel
          finding={{
            ...criticalFinding,
            risk_score: 0,
            exploitability: 0,
            confidence: 'tentative',
            risk_rationale: 'severity=low, confidence=tentative',
          }}
        />
      </ToastProvider>,
    )
    expect(screen.getByText('0 of 100')).toBeVisible()
    expect(screen.getByText('Exploitability index: 0.00 / 1')).toBeVisible()
    expect(screen.getByText('severity=low, confidence=tentative')).toBeVisible()
    expect(screen.queryByText('Not calculated')).not.toBeInTheDocument()
  })

  it('shows risk as a rounded integer of 100', () => {
    renderPanel(
      <FindingPanel finding={{ ...criticalFinding, risk_score: 81.25 }} />,
    )
    expect(screen.getByText('81 of 100')).toBeVisible()
    expect(screen.queryByText(/81\.25/)).not.toBeInTheDocument()
  })

  it('renders an AI explanation for the selected finding', async () => {
    vi.mocked(askContextAI).mockResolvedValueOnce({
      answer: 'Esta vulnerabilidade expõe um serviço importante.',
      uncertainties: [],
      referenced_finding_ids: [criticalFinding.finding_id],
    })
    const user = userEvent.setup()
    renderPanel(<FindingPanel finding={criticalFinding} />)

    await user.click(screen.getByRole('button', { name: 'Explain with AI' }))

    expect(
      await screen.findByText(
        'Esta vulnerabilidade expõe um serviço importante.',
      ),
    ).toBeVisible()
    expect(askContextAI).toHaveBeenCalledWith(
      'finding',
      criticalFinding.finding_id,
      'Explain this vulnerability in plain language and tell me what to do.',
      'en',
    )
  })
})
