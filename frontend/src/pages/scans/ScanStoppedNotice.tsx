import { scanStatusLabel } from '@/lib/scanStatus'

// `empty`: stopped before the Pi sent results; replaces the results view.
// `partial`: stopped early with results; sits above what was found.
function ScanStoppedNotice({ variant }: { variant: 'empty' | 'partial' }) {
  if (variant === 'partial') {
    return (
      <div data-testid="scan-stopped-early" className="flex flex-col gap-1">
        <p className="text-body-md font-medium">
          {scanStatusLabel('completed', 'user_cancel')}
        </p>
        <p className="text-body-md text-muted-foreground">
          This scan was stopped early. It shows what was found before the stop.
        </p>
      </div>
    )
  }
  return (
    <div
      data-testid="scan-stopped"
      className="flex flex-col items-center gap-2 py-16 text-center"
    >
      <p className="text-body-md">{scanStatusLabel('cancelled')}</p>
      <p className="text-title-sm">
        This scan was stopped before the Pi sent any results.
      </p>
    </div>
  )
}

export default ScanStoppedNotice
