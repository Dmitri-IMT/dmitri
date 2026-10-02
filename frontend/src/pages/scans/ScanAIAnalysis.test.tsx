import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import ScanAIAnalysis from './ScanAIAnalysis'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/setup'
import { criticalFinding } from '@/test/mswHandlers'
import type { ScanAIAnalysisResponse } from '@/api/scans'

const baseURL = 'http://localhost:8000/api/v1'
const scanId = criticalFinding.scan_id

const completedAnalysis = {
  executive_summary: 'Uma vulnerabilidade precisa de atenção.',
  overall_assessment: 'O resultado mostra risco alto em um serviço observado.',
  plain_language_summary:
    'Um equipamento possui software que deve ser revisado.',
  priority_actions: [
    {
      priority: 'high' as const,
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
  uncertainties: ['O scan não confirma se a vulnerabilidade foi explorada.'],
}

const unavailable: ScanAIAnalysisResponse = {
  scan_id: scanId,
  status: 'unavailable',
}

const notRequested: ScanAIAnalysisResponse = {
  scan_id: scanId,
  status: 'not_requested',
}

const job = {
  scan_id: scanId,
  analysis_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  provider: 'groq',
  model: 'openai/gpt-oss-120b',
  language: 'en' as const,
  context_version: '1',
  prompt_version: '1',
  created_at: '2026-09-12T12:00:00Z',
  updated_at: '2026-09-12T12:00:10Z',
}

const pending: ScanAIAnalysisResponse = { ...job, status: 'pending' }

const failed: ScanAIAnalysisResponse = {
  ...job,
  status: 'failed',
  completed_at: '2026-09-12T12:00:10Z',
}

const completed: ScanAIAnalysisResponse = {
  ...job,
  status: 'completed',
  completed_at: '2026-09-12T12:00:10Z',
  analysis: completedAnalysis,
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
    <ScanAIAnalysis
      scanId={scanId}
      findings={[criticalFinding]}
      completeness="complete"
    />,
  )
}

describe('ScanAIAnalysis', () => {
  it.each(['pending', 'processing'] as const)(
    'keeps deterministic results available while analysis is %s',
    async (status) => {
      serve({ ...job, status })
      renderAnalysis()

      const panel = await screen.findByTestId('scan-ai-pending')
      expect(panel).toHaveTextContent(
        'Preparing a plain-language overview of this scan.',
      )
      expect(screen.queryByTestId('scan-ai-request')).not.toBeInTheDocument()
    },
  )

  it('shows the request button when analysis has not been requested', async () => {
    serve(notRequested)
    renderAnalysis()

    const panel = await screen.findByTestId('scan-ai-not-requested')
    expect(panel).toHaveTextContent(
      'Get a plain-language overview of this scan.',
    )
    expect(screen.getByTestId('scan-ai-request')).toHaveTextContent(
      'Explain this scan',
    )
  })

  it('pressing sends one POST, hides the button, shows pending, then completed, and polling stops', async () => {
    const user = userEvent.setup()
    let getCount = 0
    let postCount = 0

    server.use(
      http.get(`${baseURL}/scans/:scanId/analysis`, () => {
        getCount += 1
        if (getCount === 1) {
          return HttpResponse.json(notRequested)
        }
        if (getCount <= 2) {
          return HttpResponse.json(pending)
        }
        return HttpResponse.json(completed)
      }),
      http.post(`${baseURL}/scans/:scanId/analysis`, () => {
        postCount += 1
        return HttpResponse.json(pending, { status: 202 })
      }),
    )

    renderAnalysis()
    await user.click(await screen.findByTestId('scan-ai-request'))

    expect(postCount).toBe(1)
    expect(screen.queryByTestId('scan-ai-request')).not.toBeInTheDocument()
    expect(screen.getByTestId('scan-ai-pending')).toBeInTheDocument()

    await waitFor(
      () => expect(screen.getByTestId('scan-ai-completed')).toBeInTheDocument(),
      { timeout: 10_000 },
    )

    const getsAfterCompleted = getCount
    await new Promise((resolve) => setTimeout(resolve, 4_000))
    expect(getCount).toBe(getsAfterCompleted)
  }, 20_000)

  it('stays out of the page when AI is unavailable', async () => {
    let requests = 0
    server.use(
      http.get(`${baseURL}/scans/:scanId/analysis`, () => {
        requests += 1
        return HttpResponse.json(unavailable)
      }),
    )
    const { container } = renderAnalysis()

    await waitFor(() => expect(requests).toBe(1))
    expect(
      container.querySelector('[data-testid^="scan-ai-"]'),
    ).not.toBeInTheDocument()
  })

  it('contains provider failure without hiding the scan results', async () => {
    serve(failed)
    renderAnalysis()

    const panel = await screen.findByTestId('scan-ai-failed')
    expect(panel).toHaveTextContent(
      "Couldn't prepare the overview. The scan results are complete without it.",
    )
    expect(screen.getByTestId('scan-ai-request')).toBeInTheDocument()
  })

  it('does not show the request button on completed analysis', async () => {
    serve(completed)
    renderAnalysis()

    await screen.findByTestId('scan-ai-completed')
    expect(screen.queryByTestId('scan-ai-request')).not.toBeInTheDocument()
  })

  it('refetches status on 409 and hides the button', async () => {
    const user = userEvent.setup()
    let getCount = 0

    server.use(
      http.get(`${baseURL}/scans/:scanId/analysis`, () => {
        getCount += 1
        if (getCount === 1) {
          return HttpResponse.json(notRequested)
        }
        return HttpResponse.json(pending)
      }),
      http.post(
        `${baseURL}/scans/:scanId/analysis`,
        () => new HttpResponse(null, { status: 409 }),
      ),
    )

    renderAnalysis()
    await user.click(await screen.findByTestId('scan-ai-request'))

    await waitFor(() =>
      expect(screen.getByTestId('scan-ai-pending')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('scan-ai-request')).not.toBeInTheDocument()
    expect(getCount).toBeGreaterThanOrEqual(2)
  })

  it('renders the plain-language summary, priorities, and grounded findings', async () => {
    const user = userEvent.setup()
    serve(completed)
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
          : HttpResponse.json(unavailable),
      ),
    )
    renderAnalysis()

    const error = await screen.findByTestId('scan-ai-error')
    expect(error).toHaveTextContent("Couldn't load the overview.")

    shouldFail = false
    await user.click(screen.getByTestId('scan-ai-retry'))
    await waitFor(() =>
      expect(screen.queryByTestId('scan-ai-error')).not.toBeInTheDocument(),
    )
  })
})
