import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/renderWithProviders'
import { downloadScanReport, getScanReport } from '@/api/scans'
import ScanReports from './ScanReports'

vi.mock('@/api/scans', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/scans')>()),
  downloadScanReport: vi.fn(),
  getScanReport: vi.fn(),
}))

describe('ScanReports', () => {
  beforeEach(() => {
    vi.mocked(downloadScanReport).mockReset()
    vi.mocked(downloadScanReport).mockResolvedValue(new Blob(['pdf']))
    vi.mocked(getScanReport).mockReset()
    vi.mocked(getScanReport).mockResolvedValue({
      scan_id: 'scan-1',
      kind: 'technical',
      language: 'en',
      generated_at: '2026-10-07T12:00:00Z',
      filename: 'dmitri-scan-scan-1-technical.json',
      content_type: 'application/json',
      sections: { scan: { findings: [{ title: 'Raw scan finding' }] } },
    })
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:report-preview'),
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    })
  })

  it('renders a single borderless icon button, not a card or full-width row', () => {
    renderWithProviders(<ScanReports scanId="scan-1" />)

    const trigger = screen.getByRole('button', { name: 'Scan reports' })
    expect(trigger).toBeInTheDocument()
    expect(trigger).toHaveAttribute('data-variant', 'ghost')
    expect(screen.getByTestId('scan-reports')).not.toHaveClass('border-border')
  })

  it('previews first and downloads only after confirmation', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ScanReports scanId="scan-1" />)

    await user.click(screen.getByRole('button', { name: 'Scan reports' }))
    await user.click(
      await screen.findByRole('menuitem', {
        name: 'Download explained report',
      }),
    )

    expect(await screen.findByTitle('PDF report preview')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Confirm download' }),
    ).toBeVisible()
    expect(downloadScanReport).toHaveBeenCalledWith('scan-1', 'explained', 'en')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByTitle('PDF report preview')).not.toBeInTheDocument()
  })

  it('previews and downloads the technical report as raw JSON', async () => {
    const user = userEvent.setup()
    const clickedDownloads: HTMLAnchorElement[] = []
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(function (this: HTMLAnchorElement) {
        clickedDownloads.push(this)
      })
    renderWithProviders(<ScanReports scanId="scan-1" />)

    await user.click(screen.getByRole('button', { name: 'Scan reports' }))
    await user.click(
      await screen.findByRole('menuitem', {
        name: 'Download technical report',
      }),
    )
    const preview = await screen.findByTestId('technical-report-json')
    expect(preview).toBeVisible()
    expect(preview.textContent).toContain('"Raw scan finding"')
    expect(getScanReport).toHaveBeenCalledWith('scan-1', 'technical', 'en')
    expect(downloadScanReport).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Confirm download' }))

    expect(clickedDownloads).toHaveLength(1)
    expect(clickedDownloads[0].download).toBe(
      'dmitri-scan-scan-1-technical.json',
    )
    expect(
      screen.queryByTestId('technical-report-json'),
    ).not.toBeInTheDocument()
    clickSpy.mockRestore()
  })

  it('raises a toast instead of inline text when the report fails', async () => {
    vi.mocked(downloadScanReport).mockRejectedValue(new Error('boom'))
    const user = userEvent.setup()
    renderWithProviders(<ScanReports scanId="scan-1" />)

    await user.click(screen.getByRole('button', { name: 'Scan reports' }))
    await user.click(
      await screen.findByRole('menuitem', {
        name: 'Download explained report',
      }),
    )

    expect(await screen.findByTestId('toast')).toHaveTextContent(
      "Couldn't prepare the report. Try again.",
    )
    expect(screen.queryByTitle('PDF report preview')).not.toBeInTheDocument()
  })
})
