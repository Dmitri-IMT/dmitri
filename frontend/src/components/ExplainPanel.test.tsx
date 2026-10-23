import { screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'
import { http, HttpResponse, delay } from 'msw'
import ExplainPanel from './ExplainPanel'
import GlobalAssistant from './GlobalAssistant'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/setup'
import { readyAnalysis } from '@/test/aiFixtures'
const api = 'http://localhost:8000/api/v1'
const id = readyAnalysis.scan_id
const scanExplanation = {
  scope: 'scan',
  context_id: id,
  language: 'en',
  created_at: '2026-10-23T12:00:00Z',
  explanation: {
    in_short: 'The camera needs an update.',
    meanings: [
      {
        lead: '1 critical problem.',
        text: 'Ask your IT person to check it this week.',
      },
    ],
    not_seen: ['Online accounts were not checked.'],
  },
}
it('requests only on open, renders structured text and code pointer, restores focus on Escape', async () => {
  const user = userEvent.setup()
  let calls = 0
  server.use(
    http.post(`${api}/ai/explain`, async ({ request }) => {
      calls++
      expect(await request.json()).toEqual({
        scope: 'scan',
        context_id: id,
        language: 'en',
      })
      return HttpResponse.json(scanExplanation)
    }),
    http.get(`${api}/scans/:id/analysis`, () =>
      HttpResponse.json(readyAnalysis),
    ),
  )
  renderWithProviders(<ExplainPanel scope="scan" contextId={id} scanId={id} />)
  expect(calls).toBe(0)
  const trigger = screen.getByTestId('scan-explain-open')
  await user.click(trigger)
  const panel = screen.getByTestId('scan-explain-panel')
  expect(
    await within(panel).findByText('The camera needs an update.'),
  ).toBeVisible()
  expect(
    await within(panel).findByText(
      'Start with task 1: Update the camera software.',
    ),
  ).toBeVisible()
  expect(within(panel).getByText('1 critical problem.').tagName).toBe('STRONG')
  await user.keyboard('{Escape}')
  expect(trigger).toHaveFocus()
  await user.click(trigger)
  expect(calls).toBe(1)
})
it('cancels the waiting request without a false error toast', async () => {
  const user = userEvent.setup()
  server.use(
    http.post(`${api}/ai/explain`, async () => {
      await delay('infinite')
      return HttpResponse.json(scanExplanation)
    }),
  )
  renderWithProviders(<ExplainPanel scope="scan" contextId={id} scanId={id} />)
  await user.click(screen.getByTestId('scan-explain-open'))
  expect(await screen.findByTestId('explain-waiting')).toBeVisible()
  await user.click(screen.getByTestId('explain-cancel'))
  expect(screen.queryByTestId('explain-waiting')).not.toBeInTheDocument()
  expect(screen.queryByTestId('toast')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Try again' })).toBeEnabled()
})
it('shows failures in a toast and supports retry', async () => {
  const user = userEvent.setup()
  let calls = 0
  server.use(
    http.post(`${api}/ai/explain`, () =>
      ++calls === 1
        ? new HttpResponse(null, { status: 502 })
        : HttpResponse.json(scanExplanation),
    ),
  )
  renderWithProviders(<ExplainPanel scope="scan" contextId={id} scanId={id} />)
  await user.click(screen.getByTestId('scan-explain-open'))
  expect(await screen.findByTestId('toast')).toHaveTextContent(
    'Dmitri could not explain this right now.',
  )
  await user.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByText('The camera needs an update.')).toBeVisible()
})
it('renders the machine schema instead of free chat and hands off to the assistant', async () => {
  const user = userEvent.setup()
  server.use(
    http.post(`${api}/ai/explain`, () =>
      HttpResponse.json({
        scope: 'host',
        context_id: id,
        language: 'en',
        created_at: '2026-10-23T12:00:00Z',
        explanation: {
          what_it_is: 'This is probably a camera.',
          problems: 'Its old software may allow access.',
        },
      }),
    ),
  )
  renderWithProviders(
    <>
      <GlobalAssistant />
      <ExplainPanel scope="host" contextId={id} scanId={id} />
    </>,
    { route: `/network/${id}` },
  )
  await user.click(screen.getByTestId('machine-explain-open'))
  expect(await screen.findByText('This is probably a camera.')).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Ask a question' }))
  await waitFor(() =>
    expect(screen.getByRole('dialog')).toHaveTextContent('Ask Dmitri'),
  )
  expect(screen.getByRole('dialog')).toHaveTextContent('can search the web')
})
