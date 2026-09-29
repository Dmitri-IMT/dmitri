import { scanStatusLabel } from '@/lib/scanStatus'

function ScanStoppedNotice() {
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
