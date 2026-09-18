import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import FindingPanel from './FindingPanel'
import { criticalFinding } from '@/test/mswHandlers'
import { explainFinding } from '@/api/findings'

vi.mock('@/api/findings', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/findings')>()),
  explainFinding: vi.fn(),
}))

describe('FindingPanel risk', () => {
  it('distinguishes unavailable scores from zero and displays the explanation', () => {
    const { rerender } = render(<FindingPanel finding={criticalFinding} />)
    expect(screen.getByText('Not calculated')).toBeVisible()
    rerender(
      <FindingPanel
        finding={{
          ...criticalFinding,
          risk_score: 0,
          exploitability: 0,
          confidence: 'tentative',
          risk_rationale: 'severity=low, confidence=tentative',
        }}
      />,
    )
    expect(screen.getByText('0 of 100')).toBeVisible()
    expect(screen.getByText('Exploitability index: 0.00 / 1')).toBeVisible()
    expect(screen.getByText('severity=low, confidence=tentative')).toBeVisible()
    expect(screen.queryByText('Not calculated')).not.toBeInTheDocument()
  })

  it('shows risk as a rounded integer of 100', () => {
    render(<FindingPanel finding={{ ...criticalFinding, risk_score: 81.25 }} />)
    expect(screen.getByText('81 of 100')).toBeVisible()
    expect(screen.queryByText(/81\.25/)).not.toBeInTheDocument()
  })

  it('renders an AI explanation for the selected finding', async () => {
    vi.mocked(explainFinding).mockResolvedValueOnce({
      answer: 'Esta vulnerabilidade expõe um serviço importante.',
      uncertainties: [],
      referenced_finding_ids: [criticalFinding.finding_id],
    })
    const user = userEvent.setup()
    render(<FindingPanel finding={criticalFinding} />)

    await user.click(screen.getByRole('button', { name: 'Explicar com IA' }))

    expect(
      await screen.findByText(
        'Esta vulnerabilidade expõe um serviço importante.',
      ),
    ).toBeVisible()
    expect(explainFinding).toHaveBeenCalledWith(criticalFinding.finding_id)
  })
})
