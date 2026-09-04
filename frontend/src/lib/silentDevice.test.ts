import { describe, expect, it } from 'vitest'
import { isSilent, weeksSince } from '@/lib/silentDevice'

const now = new Date('2026-09-04T12:00:00Z')

function daysAgo(days: number): string {
  return new Date(now.getTime() - days * 24 * 60 * 60 * 1000).toISOString()
}

describe('isSilent', () => {
  it.each([
    [0, false],
    [13, false],
    [14, false],
    [15, true],
    [90, true],
  ])('reads %i days since the last report as silent=%s', (days, expected) => {
    expect(isSilent(daysAgo(days), now)).toBe(expected)
  })
})

describe('weeksSince', () => {
  it.each([
    [6, 0],
    [7, 1],
    [20, 2],
    [21, 3],
    [38, 5],
  ])('rounds %i days down to %i weeks', (days, expected) => {
    expect(weeksSince(daysAgo(days), now)).toBe(expected)
  })
})
