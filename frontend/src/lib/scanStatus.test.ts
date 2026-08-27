import { describe, expect, it } from 'vitest'
import type { components } from '@/types/openapi'
import { isUnfinished, scanStatusPill } from './scanStatus'

type ScanStatus = components['schemas']['ScanStatus']

const EXPECTED_STATUS_PILLS: Record<
  ScanStatus,
  { tone: 'running' | 'failed' | 'neutral'; label: string }
> = {
  pending: { tone: 'running', label: 'Running…' },
  accepted: { tone: 'running', label: 'Running…' },
  processing: { tone: 'running', label: 'Running…' },
  completed: { tone: 'neutral', label: 'Completed' },
  failed: { tone: 'failed', label: 'Failed' },
}

describe('scanStatusPill', () => {
  it('maps every scan status to its pill presentation', () => {
    for (const status of Object.keys(EXPECTED_STATUS_PILLS) as ScanStatus[]) {
      expect(scanStatusPill(status)).toEqual(EXPECTED_STATUS_PILLS[status])
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
