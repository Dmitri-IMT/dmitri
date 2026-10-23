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
  it('shows severity, method, status, and confidence as separate evidence fields', () => {
    renderPanel(
      <FindingPanel
        finding={{
          ...criticalFinding,
          detection_method: 'version_correlation',
          evidence_status: 'conflicting',
          confidence: 'probable',
          evidence_observations: [
            {
              condition_key: 'ssh:version:CVE-2023-38408',
              method: 'version_correlation',
              result: 'negative',
              source: 'nvd_enrichment',
              source_script: null,
              rule_id: 'cpe-match',
              rule_version: '1',
              evidence:
                'Installed package version differs from the affected range.',
              ip: '192.168.1.42',
              port: 22,
              protocol: 'tcp',
              unit_id: 1,
            },
            {
              condition_key: 'ssh:version:CVE-2023-38408',
              method: 'specific_check',
              result: 'positive',
              source: 'ssh-audit',
              source_script: null,
              rule_id: 'cve-check',
              rule_version: '2',
              evidence: 'Affected version signature reported by the check.',
              ip: '192.168.1.42',
              port: 22,
              protocol: 'tcp',
              unit_id: 2,
            },
          ],
          evidence_truncated: true,
        }}
      />,
    )

    expect(
      screen.getByTestId(`finding-severity-${criticalFinding.finding_id}`),
    ).toHaveTextContent('SeverityCritical')
    expect(
      screen.getByTestId(`finding-method-${criticalFinding.finding_id}`),
    ).toHaveTextContent('Detection methodVersion association')
    expect(
      screen.getByTestId(`finding-status-${criticalFinding.finding_id}`),
    ).toHaveTextContent('Evidence statusConflicting evidence')
    expect(
      screen.getByTestId(`finding-confidence-${criticalFinding.finding_id}`),
    ).toHaveTextContent('Evidence confidenceProbable')
    expect(
      screen.getByTestId(`finding-evidence-${criticalFinding.finding_id}`),
    ).toHaveTextContent('The recorded checks disagree.')
    expect(
      screen.getByTestId(`finding-observations-${criticalFinding.finding_id}`),
    ).toHaveTextContent('ssh:version:CVE-2023-38408')
    expect(
      screen.getByTestId(`finding-observations-${criticalFinding.finding_id}`),
    ).toHaveTextContent('192.168.1.42:22/tcp')
    expect(
      screen.getByTestId(`finding-observations-${criticalFinding.finding_id}`),
    ).toHaveTextContent(/Modbus unit ID\s*1/)
    expect(
      screen.getByTestId(`finding-observations-${criticalFinding.finding_id}`),
    ).toHaveTextContent(/Modbus unit ID\s*2/)
    expect(
      screen.getByTestId(
        `finding-observations-${criticalFinding.finding_id}-truncated`,
      ),
    ).toBeVisible()
  })

  it('does not infer evidence method or confidence from legacy fields', () => {
    renderPanel(
      <FindingPanel
        finding={{
          ...criticalFinding,
          source: 'nmap',
          detection_method: 'unknown',
          evidence_status: 'unknown',
          evidence_observations: [],
          confidence: null,
        }}
      />,
    )

    expect(
      screen.getByTestId(`finding-method-${criticalFinding.finding_id}`),
    ).toHaveTextContent('Unknown')
    expect(
      screen.getByTestId(`finding-status-${criticalFinding.finding_id}`),
    ).toHaveTextContent('Unknown')
    expect(
      screen.getByTestId(`finding-confidence-${criticalFinding.finding_id}`),
    ).toHaveTextContent('Not reported')
    expect(
      screen.getByTestId(`finding-evidence-${criticalFinding.finding_id}`),
    ).toHaveTextContent('This record predates evidence details.')
  })

  it('does not copy the finding Modbus unit ID into observations without one', () => {
    renderPanel(
      <FindingPanel
        finding={{
          ...criticalFinding,
          modbus_unit: { id: 1, unit_id: 7, port: 502 },
          evidence_observations: [
            {
              condition_key: 'modbus:register:holding:1',
              method: 'specific_check',
              result: 'inconclusive',
              source: 'modbus-discover',
              source_script: null,
              rule_id: 'modbus-check',
              rule_version: '1',
              evidence: 'No unit identifier was recorded for this observation.',
              ip: '192.168.1.42',
              port: 502,
              protocol: 'tcp',
              unit_id: null,
            },
            {
              condition_key: 'modbus:register:holding:2',
              method: 'specific_check',
              result: 'inconclusive',
              source: 'modbus-discover',
              source_script: null,
              rule_id: 'modbus-check',
              rule_version: '1',
              evidence: 'This observation omitted its unit identifier.',
              ip: '192.168.1.42',
              port: 502,
              protocol: 'tcp',
            },
          ],
        }}
      />,
    )

    const observations = screen.getByTestId(
      `finding-observations-${criticalFinding.finding_id}`,
    )
    expect(observations).not.toHaveTextContent(/Modbus unit ID\s*7/)
  })

  it('describes a supported version association as needing validation', () => {
    renderPanel(
      <FindingPanel
        finding={{
          ...criticalFinding,
          detection_method: 'version_correlation',
          evidence_status: 'supported',
          confidence: 'probable',
          evidence_observations: [],
          evidence_truncated: false,
        }}
      />,
    )

    expect(
      screen.getByTestId(`finding-status-${criticalFinding.finding_id}`),
    ).toHaveTextContent('Supported for the version association')
    expect(
      screen.getByTestId(`finding-evidence-${criticalFinding.finding_id}`),
    ).toHaveTextContent('Its presence on this machine still needs validation.')
  })

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
      expect.any(AbortSignal),
    )
    expect(
      screen.queryByRole('button', { name: 'Explain with AI' }),
    ).not.toBeInTheDocument()
    expect(askContextAI).toHaveBeenCalledTimes(1)
  })
})
