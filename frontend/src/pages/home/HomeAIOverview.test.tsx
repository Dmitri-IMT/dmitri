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
  language: 'en',
  context_version: '1',
  prompt_version: '1',
  created_at: '2026-09-12T12:00:00Z',
  updated_at: '2026-09-12T12:00:00Z',
  completed_at: '2026-09-12T12:01:00Z',
  analysis: {
    summary: 'A rede precisa de atenção.',
    tasks: [
      {
        rank: 1,
        priority: 'high' as const,
        title: 'Atualizar o equipamento',
        who: 'it_person' as const,
        time: '30_minutes' as const,
        steps: ['Instale as atualizações recomendadas.'],
        fallback: null,
        fixes_fully: true,
        finding_ids: ['44444444-4444-4444-8444-444444444444'],
        highest_risk_score: 80,
        sources: [],
      },
    ],
    findings: [],
    not_checked: null,
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
    expect(screen.getByTestId('home-ai-overview')).toHaveTextContent(
      'Atualizar o equipamentoYour IT person · about 30 minutes',
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
