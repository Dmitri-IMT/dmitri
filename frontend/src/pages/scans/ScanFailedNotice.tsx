import StatusPill from '@/components/StatusPill'
import { scanFailureReason } from '@/lib/scanFailureReasons'

function ScanFailedNotice({
  errorCode,
}: {
  errorCode: string | null | undefined
}) {
  const reason = scanFailureReason(errorCode)
  return (
    <div
      data-testid="scan-failed"
      className="flex flex-col items-center gap-6 py-16 text-center"
    >
      <StatusPill tone="failed" label="Failed" />
      <p className="font-title text-title-sm">This scan didn&apos;t finish.</p>
      <p
        data-testid="scan-failed-reason"
        className="max-w-prose text-body-md text-muted-foreground"
      >
        {reason}
      </p>
    </div>
  )
}

export default ScanFailedNotice
