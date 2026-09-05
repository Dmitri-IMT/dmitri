import type { ReactNode } from 'react'
import EmptyMark from '@/components/EmptyMark'
import Timestamp from '@/components/Timestamp'
import { formatScanDuration } from '@/lib/scanDuration'
import { SCAN_MODE_LABEL } from '@/lib/scanModes'
import type { components } from '@/types/openapi'

type ScanSummary = components['schemas']['ScanSummary']

export function scanWhenCell(scan: ScanSummary): ReactNode {
  return (
    <span className="block truncate">
      <Timestamp value={scan.timestamp} />
    </span>
  )
}

export function scanModeCell(scan: ScanSummary): ReactNode {
  return SCAN_MODE_LABEL[scan.scan_mode]
}

export function scanDurationCell(
  scan: ScanSummary,
  testId?: string,
): ReactNode {
  const copy = formatScanDuration(scan.duration)
  return (
    <span data-testid={testId} className="block text-right tabular-nums">
      {copy ?? <EmptyMark />}
    </span>
  )
}
