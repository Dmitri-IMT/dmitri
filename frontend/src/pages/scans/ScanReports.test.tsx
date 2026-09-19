import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/renderWithProviders'
import { downloadScanReport } from '@/api/scans'
import ScanReports from './ScanReports'

vi.mock('@/api/scans', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/scans')>()),
  downloadScanReport: vi.fn(),
}))

describe('ScanReports', () => {
  beforeEach(() => {
    vi.mocked(downloadScanReport).mockReset()
    vi.mocked(downloadScanReport).mockResolvedValue(new Blob(['pdf']))
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:report-preview'),
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    })
  })

  it('previews first and downloads only after confirmation', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ScanReports scanId="scan-1" />)

    await user.click(
      screen.getByRole('button', { name: 'Download explained report' }),
    )

    expect(await screen.findByTitle('PDF report preview')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Confirm download' }),
    ).toBeVisible()
    expect(downloadScanReport).toHaveBeenCalledWith('scan-1', 'explained', 'en')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByTitle('PDF report preview')).not.toBeInTheDocument()
  })

  it('supports the technical report confirmation flow', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ScanReports scanId="scan-1" />)

    await user.click(
      screen.getByRole('button', { name: 'Download technical report' }),
    )
    expect(await screen.findByText('Technical report preview')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Confirm download' }))

    expect(
      screen.queryByText('Technical report preview'),
    ).not.toBeInTheDocument()
  })
})
