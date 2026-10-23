import { expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import HostDetail from '@/pages/HostDetail'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import {
  baseURL,
  hostDetail,
  hostNotFound,
  withHostAssessment,
} from '@/test/hostsHarness'
import { criticalFinding, hostDetailFixtures } from '@/test/mswHandlers'
import { readyAnalysis } from '@/test/aiFixtures'
const host = hostDetailFixtures[1]
const finding = {
  ...criticalFinding,
  host_id: host.host_id,
  host_hostname: host.hostname,
  scan_id: host.scan_history[0].scan_id,
}
function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/network/:hostId" element={<HostDetail />} />
    </Routes>,
    { route: `/network/${host.host_id}` },
  )
}
it('puts about, best fix and problems before counted IT sections', async () => {
  hostDetail(host, [finding])
  renderPage()
  const about = await screen.findByTestId('machine-about')
  const best = screen.getByTestId('machine-best-fix')
  expect(
    about.compareDocumentPosition(best) & Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy()
  expect(
    best.compareDocumentPosition(screen.getByTestId('machine-problems')) &
      Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy()
  expect(
    within(screen.getByTestId('problems-table')).queryByRole('columnheader', {
      name: 'Machine',
    }),
  ).not.toBeInTheDocument()
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
    host.hostname,
  )
  expect(screen.getByTestId('machine-explain-open')).toBeVisible()
})
it('requests this machine’s latest scan and keeps historical findings out of its advice', async () => {
  hostDetail(host, [])
  let requested: URL | undefined
  server.use(
    http.get(`${baseURL}/findings`, ({ request }) => {
      requested = new URL(request.url)
      return HttpResponse.json({ data: [finding], total: 1, page: 1 })
    }),
  )
  renderPage()
  await screen.findByTestId('machine-about')
  expect(requested?.searchParams.get('host_id')).toBe(host.host_id)
  expect(requested?.searchParams.get('scan_id')).toBe(
    host.scan_history[0].scan_id,
  )
})
it('chooses the task that fixes the most of this machine’s findings, even if it is not task one', async () => {
  const second = { ...finding, finding_id: 'machine-finding-2' }
  const analysis = {
    ...readyAnalysis,
    analysis: {
      ...readyAnalysis.analysis,
      tasks: [
        {
          ...readyAnalysis.analysis.tasks[0],
          finding_ids: [finding.finding_id],
        },
        {
          ...readyAnalysis.analysis.tasks[0],
          rank: 2,
          title: 'Update both services',
          finding_ids: [finding.finding_id, second.finding_id],
        },
      ],
    },
  }
  server.use(
    http.get(`${baseURL}/scans/:id/analysis`, () =>
      HttpResponse.json(analysis),
    ),
  )
  hostDetail(host, [finding, second])
  renderPage()
  const fix = await screen.findByTestId('machine-best-fix')
  expect(await within(fix).findByText('Update both services')).toBeVisible()
  expect(fix).toHaveTextContent('It fixes 2 of 2 problems.')
  expect(
    within(fix).getByRole('link', { name: 'Task 2 on your to-do list' }),
  ).toHaveAttribute(
    'href',
    `/scans/${host.scan_history[0].scan_id}#todo-task-2`,
  )
})
it('uses scanner advice if no AI task covers its findings', async () => {
  hostDetail(host, [finding])
  renderPage()
  expect(await screen.findByTestId('machine-best-fix')).toHaveTextContent(
    finding.recommendation,
  )
})
it('shows no-known-problems copy without claiming safety', async () => {
  hostDetail(host, [])
  renderPage()
  expect(await screen.findByTestId('machine-best-fix')).toHaveTextContent(
    'No known problems on this machine.',
  )
  expect(screen.getByTestId('machine-best-fix')).toHaveTextContent(
    'This does not prove the network is safe.',
  )
})
it('opens its shared vulnerability view inline', async () => {
  const user = userEvent.setup()
  hostDetail(host, [finding])
  renderPage()
  await user.click(
    await screen.findByTestId(`problems-table-caret-${finding.finding_id}`),
  )
  expect(screen.getByTestId('finding-facts')).toBeVisible()
  expect(screen.queryByTestId('context-chat')).not.toBeInTheDocument()
})
it('keeps profile and observed identity behind the IT disclosure', async () => {
  const user = userEvent.setup()
  hostDetail(withHostAssessment(host), [])
  renderPage()
  const section = await screen.findByTestId('it-section-profile')
  await user.click(within(section).getByRole('button'))
  expect(screen.getByTestId('host-profile-identity')).toHaveTextContent(host.ip)
  expect(section).toHaveTextContent('Samsung')
})
it('keeps IT sections usable and shows a toast when findings fail', async () => {
  hostDetail(host, [])
  server.use(
    http.get(
      `${baseURL}/findings`,
      () => new HttpResponse(null, { status: 500 }),
    ),
  )
  renderPage()
  expect(await screen.findByTestId('it-section-history')).toBeVisible()
  expect(await screen.findByTestId('toast')).toHaveTextContent(
    "Couldn't load this machine's vulnerabilities.",
  )
  expect(screen.queryByTestId('machine-best-fix')).not.toBeInTheDocument()
})
it('loads every findings page before selecting a best task', async () => {
  const pages: number[] = []
  hostDetail(host, [])
  server.use(
    http.get(`${baseURL}/findings`, ({ request }) => {
      const page = Number(new URL(request.url).searchParams.get('page') ?? 1)
      pages.push(page)
      return HttpResponse.json({
        data:
          page === 1
            ? Array.from({ length: 100 }, (_, i) => ({
                ...finding,
                finding_id: `finding-${i}`,
              }))
            : [{ ...finding, finding_id: 'last' }],
        total: 101,
        page,
      })
    }),
  )
  renderPage()
  expect(await screen.findByTestId('machine-about')).toHaveTextContent('101')
  expect(pages).toEqual([1, 2])
})
it('uses the IP as the title if no hostname was observed', async () => {
  hostDetail({ ...host, hostname: '' }, [])
  renderPage()
  expect(await screen.findByTestId('host-detail-identity')).toHaveTextContent(
    host.ip,
  )
})
it('shows a not-found response without an empty scan claim', async () => {
  hostNotFound()
  renderPage()
  expect(await screen.findByText("That machine doesn't exist.")).toBeVisible()
  expect(screen.queryByTestId('machine-best-fix')).not.toBeInTheDocument()
})
