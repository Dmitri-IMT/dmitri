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
      className="flex flex-col items-center gap-8 py-16 text-center"
    >
      <div className="flex flex-col items-center gap-2">
        <p className="text-body-md">Running…</p>
        <p className="text-title-sm">This scan is still running.</p>
        <p className="max-w-prose text-body-md text-muted-foreground">
          Vulnerabilities appear here when it finishes. This page doesn&apos;t
          update on its own.
        </p>
      </div>
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
