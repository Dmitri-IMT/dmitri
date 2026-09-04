import { describe, expect, it } from 'vitest'
import {
  isQuietHost,
  partitionQuietHosts,
  weeksSinceLastSeen,
} from '@/lib/hostLastSeen'

const now = new Date('2026-09-04T12:00:00Z')

function daysAgo(days: number): string {
  return new Date(now.getTime() - days * 24 * 60 * 60 * 1000).toISOString()
}

describe('isQuietHost', () => {
  it.each([
    [0, false],
    [13, false],
    [14, false],
    [15, true],
    [90, true],
  ])('reads %i days since the last report as quiet=%s', (days, expected) => {
    expect(isQuietHost(daysAgo(days), now)).toBe(expected)
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

describe('partitionQuietHosts', () => {
  it('splits rows by last-seen quietness', () => {
    const rows = [
      { host_id: 'a', last_seen_at: daysAgo(1) },
      { host_id: 'b', last_seen_at: daysAgo(20) },
      { host_id: 'c', last_seen_at: daysAgo(3) },
    ]

    expect(partitionQuietHosts(rows, now)).toEqual({
      recent: [rows[0], rows[2]],
      quiet: [rows[1]],
    })
  })
})
