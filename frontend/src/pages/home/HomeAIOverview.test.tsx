import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import HomeAIOverview from './HomeAIOverview'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/setup'
import { latestSuccessfulScan } from '@/test/mswHandlers'
import type { components } from '@/types/openapi'

type ScanAIAnalysisResponse = components['schemas']['ScanAIAnalysisResponse']

const baseURL = 'http://localhost:8000/api/v1'
const scanId = latestSuccessfulScan.scan_id

function response(
  overrides: Partial<ScanAIAnalysisResponse>,
): ScanAIAnalysisResponse {
  return {
    scan_id: scanId,
    analysis_id: null,
    status: 'unavailable',
    analysis: null,
    provider: null,
    model: null,
    context_version: null,
    prompt_version: null,
    created_at: null,
    updated_at: null,
    completed_at: null,
    ...overrides,
  }
}

function serve(payload: ScanAIAnalysisResponse) {
  server.use(
    http.get(`${baseURL}/scans/:scanId/analysis`, () =>
      HttpResponse.json(payload),
    ),
  )
}

describe('HomeAIOverview', () => {
  it('keeps the overview off Home when AI is unavailable', async () => {
    let requests = 0
    server.use(
      http.get(`${baseURL}/scans/:scanId/analysis`, () => {
        requests += 1
        return HttpResponse.json(response({ status: 'unavailable' }))
      }),
    )
    renderWithProviders(<HomeAIOverview scanId={scanId} />)

    await waitFor(() => expect(requests).toBe(1))
    expect(screen.queryByTestId('home-ai-completed')).not.toBeInTheDocument()
  })

  it.each(['pending', 'processing'] as const)(
    'explains that the summary is still being prepared when status is %s',
    async (status) => {
      serve(response({ status }))
      renderWithProviders(<HomeAIOverview scanId={scanId} />)

      expect(await screen.findByTestId('home-ai-pending')).toHaveTextContent(
        "We're preparing a simpler explanation",
      )
    },
  )

  it('shows the summary, actions, and a link to the technical scan', async () => {
    serve(
      response({
        analysis_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        status: 'completed',
        provider: 'groq',
        model: 'openai/gpt-oss-120b',
        context_version: '1',
        prompt_version: '1',
        created_at: '2026-09-12T12:00:00Z',
        updated_at: '2026-09-12T12:00:10Z',
        completed_at: '2026-09-12T12:00:10Z',
        analysis: {
          executive_summary: 'Uma vulnerabilidade precisa de atenÃ§Ã£o.',
          overall_assessment: 'O risco precisa de acompanhamento.',
          plain_language_summary:
            'Um equipamento possui software que deve ser revisado.',
          priority_actions: [
            {
              priority: 'high',
              title: 'PeÃ§a uma revisÃ£o do equipamento',
              description:
                'Solicite a confirmaÃ§Ã£o e atualizaÃ§Ã£o do serviÃ§o.',
              related_finding_ids: [],
            },
          ],
          important_findings: [],
          uncertainties: [],
        },
      }),
    )
    renderWithProviders(<HomeAIOverview scanId={scanId} />)

    const overview = await screen.findByTestId('home-ai-completed')
    expect(overview).toHaveTextContent(
      'Uma vulnerabilidade precisa de atenÃ§Ã£o.',
    )
    expect(overview).toHaveTextContent('PeÃ§a uma revisÃ£o do equipamento')
    expect(
      screen.getByRole('link', { name: 'View full scan results' }),
    ).toHaveAttribute('href', `/scans/${scanId}`)
  })

  it('states that a provider failure does not affect scan results', async () => {
    serve(response({ status: 'failed' }))
    renderWithProviders(<HomeAIOverview scanId={scanId} />)

    expect(await screen.findByTestId('home-ai-failed')).toHaveTextContent(
      'This does not affect your scan results.',
    )
  })
})
