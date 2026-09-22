import { useEffect, useState } from 'react'
import { downloadScanReport, type ScanReportKind } from '@/api/scans'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
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

  return (
    <div data-testid="scan-reports" className="flex justify-end">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="outline"
            disabled={preparing !== null || preview !== null}
          >
            {preparing !== null ? t('reports.preparing') : t('reports.title')}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem onSelect={() => void openPreview('explained')}>
            {t('reports.downloadExplained')}
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => void openPreview('technical')}>
            {t('reports.downloadTechnical')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
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
