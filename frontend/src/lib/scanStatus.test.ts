import { describe, expect, it } from 'vitest'
import type { components } from '@/types/openapi'
import { hidesCounts, isUnfinished, scanStatusLabel } from './scanStatus'

type ScanStatus = components['schemas']['ScanStatus']

const EXPECTED_LABELS: Record<ScanStatus, string> = {
  pending: 'Running…',
  accepted: 'Running…',
  processing: 'Running…',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Stopped',
}

describe('scanStatusLabel', () => {
  it('maps every scan status to a label and nothing else', () => {
    for (const status of Object.keys(EXPECTED_LABELS) as ScanStatus[]) {
      expect(scanStatusLabel(status)).toBe(EXPECTED_LABELS[status])
    }
  })

  it('labels a completed user-cancel scan as Stopped early', () => {
    expect(scanStatusLabel('completed', 'user_cancel')).toBe('Stopped early')
  })

  it('keeps Completed for other terminated_by values', () => {
    expect(scanStatusLabel('completed', 'timeout')).toBe('Completed')
    expect(scanStatusLabel('completed', 'error')).toBe('Completed')
    expect(scanStatusLabel('completed', null)).toBe('Completed')
  })
})

describe('isUnfinished', () => {
  it.each<ScanStatus>(['pending', 'accepted', 'processing'])(
    'returns true for %s',
    (status) => {
      expect(isUnfinished(status)).toBe(true)
    },
  )

  it.each<ScanStatus>(['completed', 'failed', 'cancelled'])(
    'returns false for %s',
    (status) => {
      expect(isUnfinished(status)).toBe(false)
    },
  )
})

describe('hidesCounts', () => {
  it.each<ScanStatus>([
    'pending',
    'accepted',
    'processing',
    'failed',
    'cancelled',
  ])('hides counts for %s', (status) => {
    expect(hidesCounts(status)).toBe(true)
  })

  it('shows counts for completed scans, including stopped early', () => {
    expect(hidesCounts('completed')).toBe(false)
  })
})
