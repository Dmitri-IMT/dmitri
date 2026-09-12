import { describe, expect, it } from 'vitest'
import * as hostLastSeen from '@/lib/hostLastSeen'
import { weeksSinceLastSeen } from '@/lib/hostLastSeen'

const now = new Date('2026-09-04T12:00:00Z')

function daysAgo(days: number): string {
  return new Date(now.getTime() - days * 24 * 60 * 60 * 1000).toISOString()
}

describe('hostLastSeen exports', () => {
  it('keeps weeksSinceLastSeen and drops the client quiet split', () => {
    expect(typeof hostLastSeen.weeksSinceLastSeen).toBe('function')
    expect('isQuietHost' in hostLastSeen).toBe(false)
    expect('partitionQuietHosts' in hostLastSeen).toBe(false)
    expect('QUIET_AFTER_MS' in hostLastSeen).toBe(false)
  })
})

describe('weeksSinceLastSeen', () => {
  it.each([
    [6, 0],
    [7, 1],
    [20, 2],
    [21, 3],
    [38, 5],
  ])('rounds %i days down to %i weeks', (days, expected) => {
    expect(weeksSinceLastSeen(daysAgo(days), now)).toBe(expected)
  })
})
