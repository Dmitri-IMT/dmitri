import { useEffect, useState } from 'react'
import { FileText } from 'lucide-react'
import { downloadScanReport, type ScanReportKind } from '@/api/scans'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useToast } from '@/hooks/useToast'
import useI18n from '@/i18n/useI18n'

type Preview = {
  kind: ScanReportKind
  blob: Blob
  url: string
}

function ScanReports({ scanId }: { scanId: string }) {
  const { language, t } = useI18n()
  const { show } = useToast()
  const [preparing, setPreparing] = useState<ScanReportKind | null>(null)
  const [preview, setPreview] = useState<Preview | null>(null)

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview.url)
    }
  }, [preview])

  async function openPreview(kind: ScanReportKind) {
    setPreparing(kind)
    try {
      const blob = await downloadScanReport(scanId, kind, language)
      const url = URL.createObjectURL(blob)
      setPreview((current) => {
        if (current) URL.revokeObjectURL(current.url)
        return { kind, blob, url }
      })
    } catch {
      show(t('reports.error'))
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

  const busy = preparing !== null || preview !== null

  return (
    <div
      data-testid="scan-reports"
      className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-border bg-card p-6"
    >
      <div className="flex items-center gap-4">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-md bg-accent/10">
          <FileText aria-hidden="true" className="size-5 text-accent" />
        </div>
        <div className="flex flex-col">
          <span className="text-body-md font-semibold">{t('reports.title')}</span>
          <span className="text-body-sm text-muted-foreground">
            {t('reports.description')}
          </span>
        </div>
      </div>
      <div className="flex gap-3">
        <Button
          type="button"
          variant="outline"
          disabled={busy}
          onClick={() => void openPreview('explained')}
        >
          {preparing === 'explained'
            ? t('reports.preparing')
            : t('reports.downloadExplained')}
        </Button>
        <Button
          type="button"
          disabled={busy}
          onClick={() => void openPreview('technical')}
        >
          {preparing === 'technical'
            ? t('reports.preparing')
            : t('reports.downloadTechnical')}
        </Button>
      </div>
      <Dialog
        open={preview !== null}
        onOpenChange={(open) => !open && closePreview()}
      >
        <DialogContent
          className="h-screen w-full max-w-5xl p-4 sm:max-w-5xl"
          style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}
        >
          <DialogHeader>
            <DialogTitle>
              {preview?.kind === 'technical'
                ? t('reports.previewTechnical')
                : t('reports.previewExplained')}
            </DialogTitle>
          </DialogHeader>
          {preview && (
            <iframe
              title={t('reports.previewTitle')}
              src={preview.url}
              className="min-h-0 w-full flex-1 rounded border border-border bg-white"
            />
          )}
          <DialogFooter className="flex-row justify-end">
            <Button type="button" variant="outline" onClick={closePreview}>
              {t('common.cancel')}
            </Button>
            <Button type="button" onClick={confirmDownload}>
              {t('common.confirmDownload')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default ScanReports
