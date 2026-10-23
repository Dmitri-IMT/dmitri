import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import TodoList from './TodoList'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/setup'
import { criticalFinding, highFinding } from '@/test/mswHandlers'
import type { ScanAIAnalysisResponse } from '@/api/scans'

const baseURL = 'http://localhost:8000/api/v1'
const scanId = criticalFinding.scan_id

const completedAnalysis = {
  summary: 'One camera needs new software this week.',
  tasks: [
    {
      rank: 1,
      priority: 'immediate' as const,
      title: 'Update the camera software',
      who: 'it_person' as const,
      time: '30_minutes' as const,
      steps: [
        'Download firmware 5.7.3 from the vendor.',
        'Install it from the settings page.',
      ],
      fallback: 'If you cannot update now, unplug the camera.',
      fixes_fully: true,
      finding_ids: [criticalFinding.finding_id],
      highest_risk_score: 91.4,
      sources: [
        { name: 'Vendor advisory', url: 'https://vendor.example.com/a' },
      ],
    },
    {
      rank: 2,
      priority: 'low' as const,
      title: 'Turn off the old file sharing',
      who: 'owner' as const,
      time: '5_minutes' as const,
      steps: ['Open the settings and turn it off.'],
      fallback: null,
      fixes_fully: true,
      finding_ids: [criticalFinding.finding_id],
      highest_risk_score: null,
      sources: [],
    },
  ],
  findings: [
    {
      finding_id: criticalFinding.finding_id,
      plain_title: 'Anyone on your network can take control of this camera',
      cause: 'The camera runs old software with a known flaw.',
      what_could_happen: 'Someone could watch the video.',
      task_rank: 1,
    },
  ],
  not_checked: null,
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

function renderList(findings = [criticalFinding]) {
  return renderWithProviders(<TodoList scanId={scanId} findings={findings} />)
}

describe('TodoList', () => {
  it.each([
    ['pending', undefined, 'Waiting to start', 'Usually 2 to 4 minutes.'],
    [
      'processing',
      { stage: 'fixes', done: 0, total: 0 },
      'Looking up vendor fixes',
      'Usually 2 to 4 minutes.',
    ],
    [
      'processing',
      { stage: 'groups', done: 2, total: 7 },
      'Finding the easiest fixes',
      'Reading group 3 of 7 · usually 2 to 4 minutes',
    ],
    [
      'processing',
      { stage: 'summary', done: 7, total: 7 },
      'Writing the summary',
      'Usually 2 to 4 minutes.',
    ],
  ] as const)(
    'shows the waiting state while analysis is %s %j',
    async (status, progress, stage, detail) => {
      serve({ ...job, status, progress })
      renderList()

      const waiting = await screen.findByTestId('todo-waiting')
      expect(within(waiting).getByRole('status')).toHaveTextContent(stage)
      expect(waiting).toHaveTextContent(detail)
      expect(screen.getByTestId('todo-waiting-elapsed')).toHaveAttribute(
        'aria-hidden',
        'true',
      )
      expect(screen.getByTestId('todo-list-waiting')).toHaveTextContent(
        'You can leave this page.',
      )
    },
  )

  it('draws the tasks with who, time, risk and the first task open', async () => {
    const user = userEvent.setup()
    serve(completed)
    renderList()

    const list = await screen.findByTestId('todo-list')
    expect(screen.getByTestId('todo-count')).toHaveTextContent(
      '2 tasks · fixes 1 of 1 problems',
    )
    const first = screen.getByTestId('todo-task-1')
    expect(first).toHaveTextContent('Update the camera software')
    expect(first).toHaveTextContent(
      'Your IT person · about 30 minutes · fixes 1 problem',
    )
    expect(first).toHaveTextContent('91')
    expect(
      within(first).getByText('Download firmware 5.7.3 from the vendor.'),
    ).toBeVisible()
    expect(
      within(first).getByRole('link', { name: 'Vendor advisory' }),
    ).toHaveAttribute('href', 'https://vendor.example.com/a')
    expect(first).toHaveTextContent(
      'If you cannot update now, unplug the camera.',
    )

    const secondStep = within(screen.getByTestId('todo-task-2')).getByText(
      'Open the settings and turn it off.',
    )
    expect(secondStep).not.toBeVisible()
    const toggle = screen.getByTestId('todo-task-toggle-2')
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(secondStep).toBeVisible()
    expect(screen.getByTestId('todo-task-2')).toHaveTextContent('—')
    expect(list).toHaveTextContent('Written by Dmitri AI')
  })

  it('counts the problems that no task covers', async () => {
    serve(completed)
    renderList([criticalFinding, highFinding])

    expect(await screen.findByTestId('todo-list')).toHaveTextContent(
      '1 problem has no simple fix yet. It is in the list below.',
    )
  })

  it('says there is nothing to fix without claiming the network is safe', async () => {
    serve({ ...completed, analysis: { ...completedAnalysis, tasks: [] } })
    renderList()

    const empty = await screen.findByTestId('todo-empty')
    expect(empty).toHaveTextContent('Nothing to fix from this scan.')
    expect(empty).toHaveTextContent('This does not prove the network is safe.')
  })

  it('makes the list on request, waits, then shows it and stops polling', async () => {
    const user = userEvent.setup()
    let getCount = 0
    let postCount = 0
    server.use(
      http.get(`${baseURL}/scans/:scanId/analysis`, () => {
        getCount += 1
        if (getCount === 1) return HttpResponse.json(notRequested)
        if (getCount <= 2) return HttpResponse.json(pending)
        return HttpResponse.json(completed)
      }),
      http.post(`${baseURL}/scans/:scanId/analysis`, () => {
        postCount += 1
        return HttpResponse.json(pending, { status: 202 })
      }),
    )

    renderList()
    await user.click(await screen.findByTestId('todo-request'))

    expect(postCount).toBe(1)
    expect(screen.getByTestId('todo-list-waiting')).toBeInTheDocument()
    await waitFor(
      () => expect(screen.getByTestId('todo-list')).toBeInTheDocument(),
      { timeout: 10_000 },
    )
    const getsAfterCompleted = getCount
    await new Promise((resolve) => setTimeout(resolve, 4_000))
    expect(getCount).toBe(getsAfterCompleted)
  }, 20_000)

  it('offers Try again after a failure', async () => {
    serve(failed)
    renderList()

    const panel = await screen.findByTestId('todo-failed')
    expect(panel).toHaveTextContent(
      'Dmitri could not write the list this time. Your scan results are safe and complete.',
    )
    expect(screen.getByTestId('todo-retry')).toHaveTextContent('Try again')
  })

  it('refetches status on 409', async () => {
    const user = userEvent.setup()
    let getCount = 0
    server.use(
      http.get(`${baseURL}/scans/:scanId/analysis`, () => {
        getCount += 1
        return HttpResponse.json(getCount === 1 ? notRequested : pending)
      }),
      http.post(
        `${baseURL}/scans/:scanId/analysis`,
        () => new HttpResponse(null, { status: 409 }),
      ),
    )

    renderList()
    await user.click(await screen.findByTestId('todo-request'))

    await screen.findByTestId('todo-list-waiting')
    expect(getCount).toBeGreaterThanOrEqual(2)
  })

  it('falls back to the highest-risk scanner advice when AI is off', async () => {
    serve(unavailable)
    renderList([criticalFinding])

    const panel = await screen.findByTestId('todo-fallback')
    expect(panel).toHaveTextContent('Start here')
    expect(panel).toHaveTextContent(criticalFinding.recommendation)
  })

  it('raises a toast and shows the fallback when the read fails', async () => {
    server.use(
      http.get(
        `${baseURL}/scans/:scanId/analysis`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    )
    renderList()

    expect(await screen.findByTestId('todo-fallback')).toBeInTheDocument()
    expect(await screen.findByTestId('toast')).toHaveTextContent(
      "Couldn't load your to-do list.",
    )
  })
})
