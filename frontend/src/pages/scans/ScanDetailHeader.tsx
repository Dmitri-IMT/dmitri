import type { ReactNode } from 'react'
import BackLink from '@/components/BackLink'
import EmptyMark from '@/components/EmptyMark'
import Timestamp from '@/components/Timestamp'
import { formatScanDuration } from '@/lib/scanDuration'
import { SCAN_MODE_LABEL } from '@/lib/scanModes'
import { hidesCounts, isUnfinished, scanStatusLabel } from '@/lib/scanStatus'
import type { components } from '@/types/openapi'

type ScanDetailResponse = components['schemas']['ScanDetailResponse']

function StripEntry({
  label,
  value,
  testId,
}: {
  label: string
  value: ReactNode
  testId?: string
}) {
  return (
    <div data-testid={testId} className="flex min-w-0 flex-col gap-1">
      <span className="text-caption-md uppercase text-edge">{label}</span>
      <span className="truncate text-body-md tabular-nums">{value}</span>
    </div>
  )
}

export function ScanSummaryStrip({ scan }: { scan: ScanDetailResponse }) {
  const durationCopy = formatScanDuration(scan.duration)
  return (
    <div
      data-testid="scan-summary-strip"
      className="flex gap-12 border-y border-border py-4"
    >
      <StripEntry label="Mode" value={SCAN_MODE_LABEL[scan.scan_mode]} />
      <StripEntry label="Network" value={scan.subnet} />
      {!hidesCounts(scan.status) && (
        <>
          <StripEntry label="Machines seen" value={String(scan.host_count)} />
          <StripEntry
            label="Vulnerabilities"
            value={String(scan.finding_count)}
          />
        </>
      )}
      <StripEntry
        label="Duration"
        value={durationCopy ?? <EmptyMark />}
        testId="scan-summary-duration"
      />
    </div>
  )
}

function ScanDetailHeader({ scan }: { scan: ScanDetailResponse }) {
  const progress =
    scan.status === 'pending'
      ? 15
      : scan.status === 'accepted'
        ? 35
        : scan.status === 'processing'
          ? 70
          : 100
  return (
    <div data-testid="scan-detail-header" className="flex flex-col gap-4">
      <BackLink fallback="/scans" />
      <h1 className="text-title-lg">
        Scan · <Timestamp value={scan.timestamp} />
      </h1>
      {isUnfinished(scan.status) && (
        <div className="flex flex-col gap-2" data-testid="scan-progress">
          <div className="flex items-center justify-between text-body-sm">
            <span className="font-medium">{scanStatusLabel(scan.status)}</span>
            {scan.status !== 'failed' && (
              <span className="tabular-nums text-muted-foreground">
                {progress}%
              </span>
            )}
          </div>
          <div
            className="h-2 w-full overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-label="Scan progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
          >
            <div
              className={`h-full rounded-full transition-all duration-500 ${scan.status === 'failed' ? 'bg-destructive' : 'bg-primary'}`}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

export default ScanDetailHeader
