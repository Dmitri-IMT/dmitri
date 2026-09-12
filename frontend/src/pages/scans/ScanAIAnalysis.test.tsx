import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import ScanAIAnalysis from './ScanAIAnalysis'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/setup'
import { criticalFinding } from '@/test/mswHandlers'
import type { components } from '@/types/openapi'

type ScanAIAnalysisResponse = components['schemas']['ScanAIAnalysisResponse']

const baseURL = 'http://localhost:8000/api/v1'
const scanId = criticalFinding.scan_id

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

function renderAnalysis() {
  return renderWithProviders(
    <ScanAIAnalysis scanId={scanId} findings={[criticalFinding]} />,
  )
}

describe('ScanAIAnalysis', () => {
  it.each(['pending', 'processing'] as const)(
    'keeps deterministic results available while analysis is %s',
    async (status) => {
      serve(response({ status }))
      renderAnalysis()

      const panel = await screen.findByTestId('scan-ai-pending')
      expect(panel).toHaveTextContent('The scan is complete.')
      expect(panel).toHaveTextContent('technical results below are ready now')
    },
  )

  it('stays out of the page when AI is unavailable', async () => {
    let requests = 0
    server.use(
      http.get(`${baseURL}/scans/:scanId/analysis`, () => {
        requests += 1
        return HttpResponse.json(response({ status: 'unavailable' }))
      }),
    )
    renderAnalysis()

    await waitFor(() => expect(requests).toBe(1))
    await waitFor(() =>
      expect(screen.queryByText('AI overview')).not.toBeInTheDocument(),
    )
  })

  it('contains provider failure without hiding the scan results', async () => {
    serve(response({ status: 'failed' }))
    renderAnalysis()

    const panel = await screen.findByTestId('scan-ai-failed')
    expect(panel).toHaveTextContent('AI overview unavailable')
    expect(panel).toHaveTextContent(
      'This does not affect the technical scan results below.',
    )
  })

  it('renders the plain-language summary, priorities, and grounded findings', async () => {
    const user = userEvent.setup()
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
          executive_summary: 'Uma vulnerabilidade precisa de atenção.',
          overall_assessment:
            'O resultado mostra risco alto em um serviço observado.',
          plain_language_summary:
            'Um equipamento possui software que deve ser revisado.',
          priority_actions: [
            {
              priority: 'high',
              title: 'Peça a revisão do equipamento',
              description:
                'Solicite que um profissional confirme e atualize o serviço.',
              related_finding_ids: [criticalFinding.finding_id],
            },
          ],
          important_findings: [
            {
              finding_id: criticalFinding.finding_id,
              why_it_matters: 'O serviço está acessível pela rede.',
              plain_language_explanation:
                'O software observado pode conter uma falha conhecida.',
              recommendation: 'Confirme a versão antes de realizar alterações.',
              evidence_used: ['A versão do serviço foi registrada pelo scan.'],
              uncertainty: null,
            },
          ],
          uncertainties: [
            'O scan não confirma se a vulnerabilidade foi explorada.',
          ],
        },
      }),
    )
    renderAnalysis()

    const panel = await screen.findByTestId('scan-ai-completed')
    expect(panel).toHaveTextContent('Uma vulnerabilidade precisa de atenção.')
    expect(panel).toHaveTextContent('Peça a revisão do equipamento')
    expect(panel).toHaveTextContent(criticalFinding.title)
    expect(panel).toHaveTextContent('O serviço está acessível pela rede.')

    const limitation = screen.getByText(
      'O scan não confirma se a vulnerabilidade foi explorada.',
    )
    expect(limitation).not.toBeVisible()
    await user.click(screen.getByTestId('scan-ai-details-toggle'))
    expect(limitation).toBeVisible()
  })

  it('offers an explicit retry when the read fails', async () => {
    const user = userEvent.setup()
    let shouldFail = true
    server.use(
      http.get(`${baseURL}/scans/:scanId/analysis`, () =>
        shouldFail
          ? new HttpResponse(null, { status: 500 })
          : HttpResponse.json(response({ status: 'unavailable' })),
      ),
    )
    renderAnalysis()

    const error = await screen.findByTestId('scan-ai-error')
    expect(error).toHaveTextContent(
      'technical scan results below are still available',
    )

    shouldFail = false
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    await waitFor(() =>
      expect(screen.queryByTestId('scan-ai-error')).not.toBeInTheDocument(),
    )
  })
})
