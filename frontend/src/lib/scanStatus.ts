import type { components } from '@/types/openapi'

type ScanStatus = components['schemas']['ScanStatus']
type TerminatedBy = components['schemas']['TerminatedBy']

export function scanStatusLabel(
  status: ScanStatus,
  terminatedBy?: TerminatedBy | null,
): string {
  if (status === 'completed' && terminatedBy === 'user_cancel') {
    return 'Stopped early'
  }
  switch (status) {
    case 'pending':
    case 'accepted':
    case 'processing':
      return 'Running…'
    case 'completed':
      return 'Completed'
    case 'failed':
      return 'Failed'
    case 'cancelled':
      return 'Stopped'
    default: {
      const _exhaustive: never = status
      return _exhaustive
    }
  }
}

export function isUnfinished(status: ScanStatus): boolean {
  switch (status) {
    case 'pending':
    case 'accepted':
    case 'processing':
      return true
    case 'completed':
    case 'failed':
    case 'cancelled':
      return false
    default: {
      const _exhaustive: never = status
      return _exhaustive
    }
  }
}

export function hidesCounts(status: ScanStatus): boolean {
  switch (status) {
    case 'pending':
    case 'accepted':
    case 'processing':
    case 'failed':
    case 'cancelled':
      return true
    case 'completed':
      return false
    default: {
      const _exhaustive: never = status
      return _exhaustive
    }
  }
}
