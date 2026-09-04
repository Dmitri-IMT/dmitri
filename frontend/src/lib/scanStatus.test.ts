import { describe, expect, it } from 'vitest'
import type { components } from '@/types/openapi'
import { isUnfinished, scanStatusLabel } from './scanStatus'

type ScanStatus = components['schemas']['ScanStatus']

const EXPECTED_LABELS: Record<ScanStatus, string> = {
  pending: 'Running…',
  accepted: 'Running…',
  processing: 'Running…',
  completed: 'Completed',
  failed: 'Failed',
}

describe('scanStatusLabel', () => {
  it('maps every scan status to a label and nothing else', () => {
    for (const status of Object.keys(EXPECTED_LABELS) as ScanStatus[]) {
      expect(scanStatusLabel(status)).toBe(EXPECTED_LABELS[status])
    }
  })
})

describe('isUnfinished', () => {
  it.each<ScanStatus>(['pending', 'accepted', 'processing'])(
    'returns true for %s',
    (status) => {
      expect(isUnfinished(status)).toBe(true)
    },
  )

  it.each<ScanStatus>(['completed', 'failed'])(
    'returns false for %s',
    (status) => {
      expect(isUnfinished(status)).toBe(false)
    },
  )
})
