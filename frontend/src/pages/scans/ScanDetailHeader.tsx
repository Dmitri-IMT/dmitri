import BackLink from '@/components/BackLink'
import Timestamp from '@/components/Timestamp'
import { SCAN_MODE_LABEL } from '@/lib/scanModes'
import { hidesCounts } from '@/lib/scanStatus'
import type { components } from '@/types/openapi'

type ScanDetailResponse = components['schemas']['ScanDetailResponse']

function StripEntry({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <span className="text-caption-md uppercase text-edge">{label}</span>
      <span className="truncate text-body-md tabular-nums">{value}</span>
    </div>
  )
}

export function ScanSummaryStrip({ scan }: { scan: ScanDetailResponse }) {
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
