import type { components } from '@/types/openapi'

type ScanStatus = components['schemas']['ScanStatus']

const SCAN_STATUS_LABELS: Record<ScanStatus, string> = {
  pending: 'Running…',
  accepted: 'Running…',
  processing: 'Running…',
  completed: 'Completed',
  failed: 'Failed',
}

export function scanStatusLabel(status: ScanStatus): string {
  return SCAN_STATUS_LABELS[status]
}

export function isUnfinished(status: ScanStatus): boolean {
  return (
    status === 'pending' || status === 'accepted' || status === 'processing'
  )
}

// A scan only reports host and finding counts once it completes: while it is still
// running there is nothing to count yet, and a failed scan never produced a total.
export function hidesCounts(status: ScanStatus): boolean {
  return isUnfinished(status) || status === 'failed'
}
