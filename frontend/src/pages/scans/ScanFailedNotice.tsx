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
      className="flex flex-col items-center gap-2 py-16 text-center"
    >
      <p className="text-body-md">Failed</p>
      <p className="text-title-sm">This scan didn&apos;t finish.</p>
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
