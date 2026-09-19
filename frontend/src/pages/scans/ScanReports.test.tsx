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

    await user.click(screen.getByRole('button', { name: 'Baixar relatório explicado' }))

    expect(await screen.findByTitle('Prévia do relatório PDF')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirmar download' })).toBeVisible()
    expect(downloadScanReport).toHaveBeenCalledWith('scan-1', 'explained')

    await user.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(screen.queryByTitle('Prévia do relatório PDF')).not.toBeInTheDocument()
  })

  it('supports the technical report confirmation flow', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ScanReports scanId="scan-1" />)

    await user.click(screen.getByRole('button', { name: 'Baixar relatório técnico' }))
    expect(await screen.findByText('Prévia do relatório técnico')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Confirmar download' }))

    expect(screen.queryByText('Prévia do relatório técnico')).not.toBeInTheDocument()
  })
})
