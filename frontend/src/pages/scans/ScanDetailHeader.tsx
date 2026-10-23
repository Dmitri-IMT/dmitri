import BackLink from '@/components/BackLink'
import Timestamp from '@/components/Timestamp'
import ExplainPanel from '@/components/ExplainPanel'
import ScanReports from '@/pages/scans/ScanReports'
import ScanPartialWarning from '@/pages/scans/ScanPartialWarning'
import { isUnfinished, scanStatusLabel } from '@/lib/scanStatus'
import useI18n from '@/i18n/useI18n'
import type { components } from '@/types/openapi'

type ScanDetailResponse = components['schemas']['ScanDetailResponse']

function ScanDetailHeader({ scan }: { scan: ScanDetailResponse }) {
  const { t } = useI18n()
  const progress = scan.progress
  return (
    <div data-testid="scan-detail-header" className="flex flex-col gap-4">
      <BackLink fallback="/scans" />
      <div className="flex items-end justify-between gap-6">
        <div className="flex flex-col gap-2">
          <p className="text-caption-md text-ink-muted">
            Scan · <Timestamp value={scan.timestamp} /> ·{' '}
            {scanStatusLabel(scan.status)}
          </p>
          <h1 className="text-title-lg">
            Scan · <Timestamp value={scan.timestamp} />
          </h1>
        </div>
        {scan.status === 'completed' && (
          <div className="flex items-center gap-3">
            <ExplainPanel
              scope="scan"
              contextId={scan.scan_id}
              scanId={scan.scan_id}
            />
            <ScanReports scanId={scan.scan_id} />
          </div>
        )}
      </div>
      <ScanPartialWarning scan={scan} />
      {isUnfinished(scan.status) && (
        <div className="flex flex-col gap-2" data-testid="scan-progress">
          <div className="flex items-center justify-between text-body-sm">
            <span className="font-medium">{scanStatusLabel(scan.status)}</span>
            {progress && (
              <span className="tabular-nums text-muted-foreground">
                {progress.percent}%
              </span>
            )}
          </div>
          <div
            className="h-2 w-full overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-label="Scan progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress?.percent}
            aria-valuetext={
              progress ? `${t(`scans.stage.${progress.stage}`)}` : undefined
            }
          >
            <div
              className={`h-full rounded-full transition-all duration-500 ${progress ? 'bg-primary' : 'w-1/3 animate-pulse bg-primary/70'}`}
              style={progress ? { width: `${progress.percent}%` } : undefined}
            />
          </div>
          {progress && (
            <span className="text-caption-md text-muted-foreground">
              {t(`scans.stage.${progress.stage}`)}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

export default ScanDetailHeader
