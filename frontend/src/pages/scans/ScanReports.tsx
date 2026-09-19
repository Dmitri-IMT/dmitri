import { useEffect, useState } from 'react'
import { downloadScanReport, type ScanReportKind } from '@/api/scans'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

type Preview = {
  kind: ScanReportKind
  blob: Blob
  url: string
}

function ScanReports({ scanId }: { scanId: string }) {
  const [preparing, setPreparing] = useState<ScanReportKind | null>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview.url)
    }
  }, [preview])

  async function openPreview(kind: ScanReportKind) {
    setPreparing(kind)
    setError(false)
    try {
      const blob = await downloadScanReport(scanId, kind)
      const url = URL.createObjectURL(blob)
      setPreview((current) => {
        if (current) URL.revokeObjectURL(current.url)
        return { kind, blob, url }
      })
    } catch {
      setError(true)
    } finally {
      setPreparing(null)
    }
  }

  function closePreview() {
    setPreview((current) => {
      if (current) URL.revokeObjectURL(current.url)
      return null
    })
  }

  function confirmDownload() {
    if (!preview) return
    const link = document.createElement('a')
    link.href = preview.url
    link.download = `dmitri-scan-${scanId}-${preview.kind}.pdf`
    link.click()
    closePreview()
  }

  return (
    <Card data-testid="scan-reports">
      <CardHeader>
        <h2 className="text-title-sm">Scan reports</h2>
        <p className="text-body-sm text-muted-foreground">
          Escolha qual tipo de relatório você quer fazer o download.
        </p>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-3">
        {(['explained', 'technical'] as const).map((kind) => (
          <Button
            key={kind}
            type="button"
            variant="outline"
            size="sm"
            disabled={preparing !== null || preview !== null}
            onClick={() => void openPreview(kind)}
          >
            {preparing === kind
              ? 'Preparando relatório...'
              : kind === 'explained'
                ? 'Baixar relatório explicado'
                : 'Baixar relatório técnico'}
          </Button>
        ))}
        {error && (
          <p className="basis-full text-body-sm text-destructive" role="alert">
            Não foi possível preparar o relatório. Tente novamente.
          </p>
        )}
      </CardContent>
      <Dialog open={preview !== null} onOpenChange={(open) => !open && closePreview()}>
        <DialogContent
          className="h-screen w-full max-w-5xl p-4 sm:max-w-5xl"
          style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}
        >
          <DialogHeader>
            <DialogTitle>
              {preview?.kind === 'technical'
                ? 'Prévia do relatório técnico'
                : 'Prévia do relatório explicado'}
            </DialogTitle>
          </DialogHeader>
          {preview && (
            <iframe
              title="Prévia do relatório PDF"
              src={preview.url}
              className="min-h-0 w-full flex-1 rounded border border-border bg-white"
            />
          )}
          <DialogFooter className="flex-row justify-end">
            <Button type="button" variant="outline" onClick={closePreview}>
              Cancelar
            </Button>
            <Button type="button" onClick={confirmDownload}>
              Confirmar download
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

export default ScanReports
