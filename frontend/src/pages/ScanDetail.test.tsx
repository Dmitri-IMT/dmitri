import { expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import ScanDetail from '@/pages/ScanDetail'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import LocationProbe from '@/test/LocationProbe'
import {
  scanDetail,
  scanDetailFails,
  scanNotFound,
  relatedExposure,
} from '@/test/scansHarness'
import { criticalFinding, scanDetailFixtures } from '@/test/mswHandlers'
import { readyAnalysis } from '@/test/aiFixtures'
import { LanguageProvider, LANGUAGE_STORAGE_KEY } from '@/i18n/LanguageProvider'
import type { components } from '@/types/openapi'
const api = 'http://localhost:8000/api/v1'
const base = scanDetailFixtures.find((scan) => scan.status === 'completed')!
function completed(
  overrides: Partial<components['schemas']['ScanDetailResponse']> = {},
) {
  return {
    ...base,
    findings: [criticalFinding],
    finding_count: 1,
    coverage: [],
    evidence_completeness: 'unknown' as const,
    ...overrides,
  }
}
function renderPage(search = '', state?: unknown) {
  return renderWithProviders(
    <>
      <Routes>
        <Route path="/scans/:scanId" element={<ScanDetail />} />
      </Routes>
      <LocationProbe />
    </>,
    { route: `/scans/${base.scan_id}${search}`, state },
  )
}
it('orders the story, to-do, meaning, problems and collapsed IT sections', async () => {
  scanDetail(completed())
  renderPage()
  const story = await screen.findByTestId('scan-story')
  const todo = await screen.findByTestId('todo-fallback')
  const meaning = screen.getByTestId('meaning-table')
  const problems = screen.getByTestId('problems-table')
  expect(
    story.compareDocumentPosition(todo) & Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy()
  expect(
    todo.compareDocumentPosition(meaning) & Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy()
  expect(
    meaning.compareDocumentPosition(problems) &
      Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy()
  expect(screen.queryByTestId('scan-summary-strip')).not.toBeInTheDocument()
  for (const section of ['ports', 'machines', 'coverage'])
    expect(
      within(screen.getByTestId(`it-section-${section}`)).getByRole('button'),
    ).toHaveAttribute('aria-expanded', 'false')
  expect(screen.getByTestId('scan-explain-open')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Download report' })).toBeVisible()
})
it('shows code counts and unknown coverage without claiming completion', async () => {
  scanDetail(completed())
  renderPage()
  expect(await screen.findByTestId('scan-story-finished')).toHaveTextContent(
    'Not reported',
  )
  expect(screen.getByTestId('meaning-row-critical')).toHaveTextContent('1')
  expect(screen.getByTestId('scan-story-looked')).toHaveTextContent(base.subnet)
})
it('shows complete and incomplete checks from coverage, never a fabricated percentage', async () => {
  scanDetail(
    completed({
      evidence_completeness: 'partial',
      coverage: [
        {
          ip: '192.168.0.1',
          stage: 'ports',
          port: null,
          protocol: null,
          tool: null,
          outcome: 'completed',
          evidence_source: 'nmap_ports',
          reason_code: null,
          issue_keys: [],
          observations: [],
        },
        {
          ip: '192.168.0.2',
          stage: 'ports',
          port: null,
          protocol: null,
          tool: null,
          outcome: 'timed_out',
          evidence_source: 'not_run',
          reason_code: 'timeout',
          issue_keys: [],
          observations: [],
        },
      ],
    }),
  )
  renderPage()
  expect(await screen.findByTestId('scan-story-finished')).toHaveTextContent(
    '1 of 2 checks',
  )
  expect(screen.getByRole('img', { name: '1 of 2 checks' })).toBeVisible()
  expect(screen.getByTestId('meaning-row-not-checked')).toHaveTextContent('1')
})
it('shows an honest empty state for zero findings and zero machines', async () => {
  scanDetail(
    completed({ findings: [], finding_count: 0, hosts: [], host_count: 0 }),
  )
  renderPage()
  expect(await screen.findByTestId('scan-story-found')).toHaveTextContent(
    'No machines',
  )
  expect(screen.getByTestId('meaning-table')).toHaveTextContent(
    'This does not prove the network is safe.',
  )
  expect(screen.getByTestId('problems-table')).toHaveTextContent(
    'No confirmed vulnerabilities were found in this scan.',
  )
})
it('opens the deep-linked problem inline and closes it without changing the route', async () => {
  const user = userEvent.setup()
  scanDetail(completed())
  renderPage(`?finding=${criticalFinding.finding_id}`)
  const panel = await screen.findByTestId(
    `problems-table-panel-${criticalFinding.finding_id}`,
  )
  expect(panel).toBeVisible()
  expect(screen.getByTestId('finding-tech-toggle')).toHaveAttribute(
    'aria-expanded',
    'false',
  )
  await user.click(
    screen.getByTestId(`problems-table-caret-${criticalFinding.finding_id}`),
  )
  expect(panel).not.toBeInTheDocument()
  expect(screen.getByTestId('location-probe')).toHaveTextContent(
    `/scans/${base.scan_id}`,
  )
})
it('does not open an unknown deep link', async () => {
  scanDetail(completed())
  renderPage('?finding=missing')
  await screen.findByTestId('problems-table')
  expect(screen.queryByTestId('finding-facts')).not.toBeInTheDocument()
})
it('opens targeted checks and the right severity group for their deep link', async () => {
  const finding = {
    ...criticalFinding,
    source: 'targeted_service_assessment',
    finding_id: 'targeted-1',
  }
  scanDetail(completed({ findings: [finding] }))
  renderPage('?finding=targeted-1')
  expect(
    await screen.findByTestId('targeted-critical-panel-targeted-1'),
  ).toBeVisible()
  expect(
    within(screen.getByTestId('it-section-targeted')).getByRole('button', {
      name: 'Toggle targeted service findings',
    }),
  ).toHaveAttribute('aria-expanded', 'true')
})
it('opens a related problem from an exposure in the ports section', async () => {
  const user = userEvent.setup()
  const exposure = {
    ...relatedExposure,
    related_finding_ids: [criticalFinding.finding_id],
  }
  scanDetail(
    completed({ assessment_status: 'available', exposures: [exposure] }),
  )
  renderPage()
  const section = await screen.findByTestId('it-section-ports')
  await user.click(within(section).getByRole('button'))
  await user.click(
    screen.getByTestId(`scan-exposures-table-caret-${exposure.exposure_id}`),
  )
  await user.click(
    screen.getByTestId(
      `exposure-related-finding-${criticalFinding.finding_id}`,
    ),
  )
  expect(
    screen.getByTestId(`problems-table-panel-${criticalFinding.finding_id}`),
  ).toBeVisible()
})
it('leaves the problem table usable while AI never resolves', async () => {
  server.use(http.get(`${api}/scans/:id/analysis`, () => new Promise(() => {})))
  scanDetail(completed())
  renderPage()
  expect(await screen.findByTestId('problems-table')).toHaveTextContent(
    criticalFinding.title,
  )
})
it('shows task prose from the existing analysis without replacing the raw evidence', async () => {
  server.use(
    http.get(`${api}/scans/:id/analysis`, () =>
      HttpResponse.json(readyAnalysis),
    ),
  )
  scanDetail(completed())
  renderPage()
  expect(await screen.findByTestId('todo-list')).toHaveTextContent(
    'Update the camera software',
  )
  expect(await screen.findByTestId('problems-table')).toHaveTextContent(
    'Someone could control this camera',
  )
})
it('keeps partial user-cancel evidence and its notice', async () => {
  scanDetail(
    completed({
      terminated_by: 'user_cancel',
      evidence_completeness: 'partial',
    }),
  )
  renderPage()
  expect(await screen.findByTestId('scan-story')).toBeVisible()
  expect(screen.getByTestId('problems-table')).toHaveTextContent(
    criticalFinding.title,
  )
  expect(screen.getByTestId('scan-story-finished')).toHaveTextContent(
    'Stopped early',
  )
})
it('keeps failed-scan evidence available but hides AI and report controls', async () => {
  scanDetail(completed({ status: 'failed', error_code: 'device_offline' }))
  renderPage()
  expect(await screen.findByTestId('scan-failed-evidence')).toBeVisible()
  expect(screen.queryByTestId('scan-explain-open')).not.toBeInTheDocument()
  expect(screen.queryByTestId('todo-list')).not.toBeInTheDocument()
})
it('shows live progress instead of the redesign during a running scan', async () => {
  scanDetail(
    completed({
      status: 'processing',
      findings: [],
      hosts: [],
      host_count: 0,
      finding_count: 0,
    }),
  )
  renderPage()
  expect(await screen.findByTestId('scan-progress')).toBeVisible()
  expect(screen.queryByTestId('scan-story')).not.toBeInTheDocument()
  expect(screen.queryByTestId('problems-table')).not.toBeInTheDocument()
})
it('shows not-found and request failure without false results', async () => {
  scanNotFound()
  const first = renderPage()
  expect(await screen.findByText("That scan doesn't exist.")).toBeVisible()
  first.unmount()
  scanDetailFails()
  renderPage()
  expect(await screen.findByTestId('scan-detail-error')).toBeVisible()
  expect(screen.queryByTestId('scan-story')).not.toBeInTheDocument()
})
it('keeps the back destination from the opening screen', async () => {
  scanDetail(completed())
  renderPage('', { from: '/devices' })
  const link = await screen.findByRole('link', { name: /Back/ })
  expect(link).toHaveAttribute('href', '/devices')
})
it('localizes the new page labels in Brazilian Portuguese', async () => {
  localStorage.setItem(LANGUAGE_STORAGE_KEY, 'pt-BR')
  scanDetail(completed())
  renderWithProviders(
    <LanguageProvider>
      <Routes>
        <Route path="/scans/:scanId" element={<ScanDetail />} />
      </Routes>
    </LanguageProvider>,
    { route: `/scans/${base.scan_id}` },
  )
  expect(await screen.findByText('O que esta varredura fez')).toBeVisible()
  expect(
    screen.getByRole('button', { name: 'Explique esta varredura' }),
  ).toBeVisible()
  localStorage.removeItem(LANGUAGE_STORAGE_KEY)
})

it('shows completed coverage when the scanner reports terminated_by completed', async () => {
  scanDetail(
    completed({
      terminated_by: 'completed',
      evidence_completeness: 'complete',
      coverage: [
        {
          ip: '192.168.0.1',
          stage: 'ports',
          port: null,
          protocol: null,
          tool: null,
          outcome: 'completed',
          evidence_source: 'nmap_ports',
          reason_code: null,
          issue_keys: [],
          observations: [],
        },
      ],
    }),
  )
  renderPage()
  expect(await screen.findByTestId('scan-story-finished')).toHaveTextContent(
    '1 of 1 checks',
  )
  expect(screen.getByRole('img', { name: '1 of 1 checks' })).toBeVisible()
})
