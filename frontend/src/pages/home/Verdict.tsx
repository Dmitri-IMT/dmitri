import Timestamp from '@/components/Timestamp'
import type { components } from '@/types/openapi'
import useI18n from '@/i18n/useI18n'

type ScanSummary = components['schemas']['ScanSummary']

interface VerdictProps {
  reviewCount: number
  latestSuccessfulScan: ScanSummary | null
}

function Verdict({ reviewCount, latestSuccessfulScan }: VerdictProps) {
  const isClear = reviewCount === 0
  const { t } = useI18n()

  return (
    <div className="flex flex-col gap-2 items-start text-left">
      <p data-testid="home-verdict" className="text-title-lg">
        {isClear
          ? t('home.nothingNeedsAttention')
          : reviewCount === 1
            ? t('home.oneNeedsAttention')
            : t('home.manyNeedAttention', { count: reviewCount })}
      </p>
      {latestSuccessfulScan && (
        <p
          data-testid="home-context"
          className="text-body-md text-muted-foreground"
        >
          {t('home.lastScan')}{' '}
          <Timestamp value={latestSuccessfulScan.timestamp} />
        </p>
      )}
    </div>
  )
}

export default Verdict
