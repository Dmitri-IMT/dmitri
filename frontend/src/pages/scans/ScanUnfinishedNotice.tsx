import StatusPill from '@/components/StatusPill'
import { Button } from '@/components/ui/button'

function ScanUnfinishedNotice({
  onCheck,
  isChecking,
}: {
  onCheck: () => void
  isChecking: boolean
}) {
  return (
    <div
      data-testid="scan-unfinished"
      className="flex flex-col items-center gap-6 py-16 text-center"
    >
      <StatusPill tone="running" label="Running…" />
      <p className="font-title text-title-sm">This scan is still running.</p>
      <p className="max-w-prose text-body-md text-muted-foreground">
        Findings appear here when it finishes. This page doesn&apos;t update on
        its own.
      </p>
      <Button
        type="button"
        variant="outline"
        data-testid="scan-unfinished-check"
        disabled={isChecking}
        onClick={onCheck}
      >
        {isChecking ? 'Checking…' : 'Check again'}
      </Button>
    </div>
  )
}

export default ScanUnfinishedNotice
