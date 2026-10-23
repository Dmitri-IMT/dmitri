import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import ScanDetail from '@/pages/ScanDetail'
import LocationProbe from '@/test/LocationProbe'
import {
  latestScan,
  latestSuccessfulScan,
  scanDetailFixtures,
  viewerProfile,
} from '@/test/mswHandlers'
import { renderWithProviders } from '@/test/renderWithProviders'
import { baseURL, scanDetail } from '@/test/scansHarness'
import { server } from '@/test/setup'
import { signedInAs } from '@/test/usersHarness'

function fixture(scanId: string) {
  const scan = scanDetailFixtures.find((row) => row.scan_id === scanId)
  if (!scan) throw new Error(`missing fixture ${scanId}`)
  return scan
}

function renderScan(scanId: string) {
  return renderWithProviders(
    <>
      <Routes>
        <Route path="/scans/:scanId" element={<ScanDetail />} />
        <Route path="/scans" element={<div data-testid="scans-route" />} />
      </Routes>
      <LocationProbe />
    </>,
    { route: `/scans/${scanId}` },
  )
}

function deleteResponds(response: () => Response) {
  const requests: string[] = []
  server.use(
    http.delete(`${baseURL}/scans/:scanId`, ({ params }) => {
      requests.push(String(params.scanId))
      return response()
    }),
  )
  return requests
}

describe('ScanDelete', () => {
  it('deletes a finished scan and returns to the scan list', async () => {
    const scan = fixture(latestSuccessfulScan.scan_id)
    scanDetail(scan)
    const requests = deleteResponds(
      () => new HttpResponse(null, { status: 204 }),
    )
    const user = userEvent.setup()
    renderScan(scan.scan_id)

    await user.click(await screen.findByTestId('scan-delete-trigger'))
    await user.click(screen.getByTestId('scan-delete-confirm'))

    expect(await screen.findByTestId('scans-route')).toBeInTheDocument()
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/scans')
    expect(screen.getByTestId('toast')).toHaveTextContent('Scan deleted.')
    expect(requests).toEqual([scan.scan_id])
  })

  it('shows the running-scan refusal inside the dialog', async () => {
    const scan = fixture(latestSuccessfulScan.scan_id)
    scanDetail(scan)
    deleteResponds(() =>
      HttpResponse.json(
        {
          error: {
            code: 'scan_running',
            message: 'Stop the scan before you delete it.',
            details: {},
          },
        },
        { status: 409 },
      ),
    )
    const user = userEvent.setup()
    renderScan(scan.scan_id)

    await user.click(await screen.findByTestId('scan-delete-trigger'))
    await user.click(screen.getByTestId('scan-delete-confirm'))

    const dialog = screen.getByTestId('scan-delete-dialog')
    expect(
      await within(dialog).findByText('Stop the scan before you delete it.'),
    ).toBeInTheDocument()
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      `/scans/${scan.scan_id}`,
    )
  })

  it('has no delete control for an unfinished scan', async () => {
    const scan = fixture(latestScan.scan_id)
    scanDetail(scan)
    renderScan(scan.scan_id)

    expect(await screen.findByTestId('scan-detail')).toBeInTheDocument()
    expect(screen.queryByTestId('scan-delete')).not.toBeInTheDocument()
  })

  it('has no delete control for a viewer', async () => {
    signedInAs(viewerProfile)
    const scan = fixture(latestSuccessfulScan.scan_id)
    scanDetail(scan)
    renderScan(scan.scan_id)

    expect(await screen.findByTestId('it-section-machines')).toBeInTheDocument()
    expect(screen.queryByTestId('scan-delete')).not.toBeInTheDocument()
  })
})
