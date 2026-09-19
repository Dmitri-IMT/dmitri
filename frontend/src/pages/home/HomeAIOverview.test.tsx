import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import { latestSuccessfulScan } from '@/test/mswHandlers'
import type { components } from '@/types/openapi'
import HomeAIOverview from './HomeAIOverview'

const baseURL = 'http://localhost:8000/api/v1'

const completedAnalysis = {
  scan_id: latestSuccessfulScan.scan_id,
  analysis_id: '00000000-0000-4000-8000-000000000001',
  status: 'completed' as const,
  provider: 'groq',
  model: 'openai/gpt-oss-120b',
  context_version: '1',
  prompt_version: '1',
  created_at: '2026-09-12T12:00:00Z',
  updated_at: '2026-09-12T12:00:00Z',
  completed_at: '2026-09-12T12:01:00Z',
  analysis: {
    executive_summary: 'A rede precisa de atenção.',
    plain_language_summary: 'Há uma atualização importante para fazer.',
    overall_assessment: 'A varredura encontrou riscos conhecidos.',
    priority_actions: [
      {
        priority: 'high' as const,
        title: 'Atualizar o equipamento',
        description: 'Instale as atualizações recomendadas.',
        related_finding_ids: [],
      },
    ],
    important_findings: [],
    uncertainties: [],
  },
} satisfies components['schemas']['ScanAIAnalysisCompleted']

describe('HomeAIOverview', () => {
  it('presents the persisted summary and links to the scan', async () => {
    server.use(
      http.get(`${baseURL}/scans/:scanId/analysis`, () =>
        HttpResponse.json(completedAnalysis),
      ),
    )

    renderWithProviders(<HomeAIOverview latestScan={latestSuccessfulScan} />)

    expect(await screen.findByTestId('home-ai-overview')).toHaveTextContent(
      'A rede precisa de atenção.',
    )
    expect(screen.getByRole('link')).toHaveAttribute(
      'href',
      `/scans/${latestSuccessfulScan.scan_id}`,
    )
  })

  it('does not render when AI is unavailable', async () => {
    server.use(
      http.get(`${baseURL}/scans/:scanId/analysis`, () =>
        HttpResponse.json({
          scan_id: latestSuccessfulScan.scan_id,
          status: 'unavailable',
        }),
      ),
    )

    renderWithProviders(<HomeAIOverview latestScan={latestSuccessfulScan} />)

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(screen.queryByTestId('home-ai-overview')).not.toBeInTheDocument()
  })
})
