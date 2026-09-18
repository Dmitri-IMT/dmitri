import type { ReactNode } from 'react'
import BackLink from '@/components/BackLink'
import EmptyMark from '@/components/EmptyMark'
import Timestamp from '@/components/Timestamp'
import { formatScanDuration } from '@/lib/scanDuration'
import { SCAN_MODE_LABEL } from '@/lib/scanModes'
import { hidesCounts } from '@/lib/scanStatus'
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
  const needsReview = scan.exposures.filter(
    (exposure) => exposure.attention !== 'informational',
  ).length
  const attackSurface =
    scan.assessment_status === 'unavailable'
      ? 'Unavailable'
      : `${scan.exposures.length} reachable ${scan.exposures.length === 1 ? 'service' : 'services'} · ${needsReview} ${needsReview === 1 ? 'needs' : 'need'} review`
  return (
    <div data-testid="scan-assessment-summary">
      <div
        data-testid="scan-summary-strip"
        className="flex gap-12 border-y border-border py-4"
      >
        <StripEntry label="Mode" value={SCAN_MODE_LABEL[scan.scan_mode]} />
        <StripEntry label="Network" value={scan.subnet} />
        {!hidesCounts(scan.status) && (
          <>
            <StripEntry label="Machines seen" value={String(scan.host_count)} />
            <StripEntry label="Attack surface" value={attackSurface} />
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
    </div>
  )
}

function ScanDetailHeader({ scan }: { scan: ScanDetailResponse }) {
  return (
    <div data-testid="scan-detail-header" className="flex flex-col gap-2">
      <BackLink fallback="/scans" />
      <h1 className="text-title-lg">
        Scan · <Timestamp value={scan.timestamp} />
      </h1>
    </div>
  )
}

export default ScanDetailHeader
