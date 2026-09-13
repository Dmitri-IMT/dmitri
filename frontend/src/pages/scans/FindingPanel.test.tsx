import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import FindingPanel from './FindingPanel'
import { criticalFinding } from '@/test/mswHandlers'

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
    render(
      <FindingPanel finding={{ ...criticalFinding, risk_score: 81.25 }} />,
    )
    expect(screen.getByText('81 of 100')).toBeVisible()
    expect(screen.queryByText(/81\.25/)).not.toBeInTheDocument()
  })
})
