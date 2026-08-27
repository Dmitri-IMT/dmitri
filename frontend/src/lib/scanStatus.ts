import type { components } from '@/types/openapi'

type ScanStatus = components['schemas']['ScanStatus']

export type ScanStatusTone = 'running' | 'failed' | 'neutral'

export interface ScanStatusPill {
  tone: ScanStatusTone
  label: string
}

const SCAN_STATUS_PILLS: Record<ScanStatus, ScanStatusPill> = {
  pending: { tone: 'running', label: 'Running…' },
  accepted: { tone: 'running', label: 'Running…' },
  processing: { tone: 'running', label: 'Running…' },
  completed: { tone: 'neutral', label: 'Completed' },
  failed: { tone: 'failed', label: 'Failed' },
}

export function scanStatusPill(status: ScanStatus): ScanStatusPill {
  return SCAN_STATUS_PILLS[status]
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
