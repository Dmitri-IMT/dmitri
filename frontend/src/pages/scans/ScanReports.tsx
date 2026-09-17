import { useState } from 'react'
import { downloadScanReport, type ScanReportKind } from '@/api/scans'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'

function ScanReports({ scanId }: { scanId: string }) {
  const [downloading, setDownloading] = useState<ScanReportKind | null>(null)
  const [error, setError] = useState(false)

  async function handleDownload(kind: ScanReportKind) {
    setDownloading(kind)
    setError(false)
    try {
      const blob = await downloadScanReport(scanId, kind)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `dmitri-scan-${scanId}-${kind}.pdf`
      link.click()
      URL.revokeObjectURL(url)
    } catch {
      setError(true)
    } finally {
      setDownloading(null)
    }
  }

  return (
    <Card data-testid="scan-reports">
      <CardHeader>
        <h2 className="text-title-sm">Scan reports</h2>
        <p className="text-body-sm text-muted-foreground">
          Download a clear PDF explanation or the complete technical PDF.
        </p>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={downloading !== null}
          onClick={() => void handleDownload('explained')}
        >
          {downloading === 'explained'
            ? 'Preparing report...'
            : 'Download explained PDF'}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={downloading !== null}
          onClick={() => void handleDownload('technical')}
        >
          {downloading === 'technical'
            ? 'Preparing report...'
            : 'Download technical PDF'}
        </Button>
        {error && (
          <p className="basis-full text-body-sm text-destructive" role="alert">
            Couldn&apos;t download the report. Try again.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export default ScanReports
