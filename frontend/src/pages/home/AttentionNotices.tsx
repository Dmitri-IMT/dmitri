import type { CoverageItem, ScanItem } from '@/lib/review'

function AttentionNotices({
  scanItem,
  coverageItem,
}: {
  scanItem: ScanItem | null
  coverageItem: CoverageItem | null
}) {
  return (
    <>
      {scanItem && (
        <p
          data-testid="home-item-scan"
          className="text-body-md text-muted-foreground"
        >
          Last night&apos;s scan didn&apos;t finish.
        </p>
      )}
      {coverageItem && (
        <p
          data-testid="home-item-coverage"
          className="text-body-md text-muted-foreground"
        >
          No successful scan in {coverageItem.daysSinceLastSuccess} days.
        </p>
      )}
    </>
  )
}

export default AttentionNotices
