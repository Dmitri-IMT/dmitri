import Timestamp from '@/components/Timestamp'
import { cn } from '@/lib/utils'
import type { components } from '@/types/openapi'

type ScanSummary = components['schemas']['ScanSummary']

interface VerdictProps {
  reviewCount: number
  latestSuccessfulScan: ScanSummary | null
}

function Verdict({ reviewCount, latestSuccessfulScan }: VerdictProps) {
  const isClear = reviewCount === 0

  return (
    <div
      className={cn(
        'flex flex-col gap-2',
        isClear ? 'items-center text-center' : 'items-start text-left',
      )}
    >
      <p data-testid="home-verdict" className="text-title-lg">
        {isClear
          ? 'Nothing needs your attention'
          : reviewCount === 1
            ? '1 thing needs your attention'
            : `${reviewCount} things need your attention`}
      </p>
      {latestSuccessfulScan && (
        <p
          data-testid="home-context"
          className="text-body-md text-muted-foreground"
        >
          Last scan finished{' '}
          <Timestamp value={latestSuccessfulScan.timestamp} />
        </p>
      )}
    </div>
  )
}

export default Verdict
