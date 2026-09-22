import { describe, expect, it } from 'vitest'
import { dotWindow } from '@/lib/dotWindow'

describe('dotWindow', () => {
  const cases: [number, number, number[]][] = [
    [1, 0, []],
    [1, 1, [1]],
    [1, 5, [1, 2, 3, 4, 5]],
    [3, 10, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]],
    [1, 20, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]],
    [10, 20, [5, 6, 7, 8, 9, 10, 11, 12, 13, 14]],
    [20, 20, [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]],
  ]

  it.each(cases)(
    'windows page %i of %i pages to at most 10 dots',
    (page, pageCount, expected) => {
      const result = dotWindow(page, pageCount)
      expect(result).toEqual(expected)
      expect(result.length).toBeLessThanOrEqual(10)
    },
  )

  it('never renders more than 10 dots however large the page count grows', () => {
    expect(dotWindow(500, 100_000).length).toBe(10)
  })
})
