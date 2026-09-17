import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ScanReports from './ScanReports'
import { downloadScanReport } from '@/api/scans'
import { renderWithProviders } from '@/test/renderWithProviders'

vi.mock('@/api/scans', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/scans')>()),
  downloadScanReport: vi.fn(),
}))

describe('ScanReports', () => {
  beforeEach(() => {
    vi.mocked(downloadScanReport).mockReset()
    vi.mocked(downloadScanReport).mockResolvedValue(
      new Blob(['%PDF-1.7'], { type: 'application/pdf' }),
    )
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(
      () => undefined,
    )
  })

  it('downloads either report variant', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ScanReports scanId="scan-1" />)

    await user.click(
      screen.getByRole('button', { name: 'Download explained PDF' }),
    )
    expect(downloadScanReport).toHaveBeenCalledWith('scan-1', 'explained')

    await user.click(
      screen.getByRole('button', { name: 'Download technical PDF' }),
    )
    expect(downloadScanReport).toHaveBeenCalledWith('scan-1', 'technical')
  })

  it('shows a retryable error when download fails', async () => {
    vi.mocked(downloadScanReport).mockRejectedValueOnce(new Error('network'))
    const user = userEvent.setup()
    renderWithProviders(<ScanReports scanId="scan-1" />)

    await user.click(
      screen.getByRole('button', { name: 'Download explained PDF' }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Couldn't download the report. Try again.",
    )
  })
})
