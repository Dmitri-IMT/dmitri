import { describe, expect, it } from 'vitest'
import { pageWindow, type PageWindowItem } from '@/lib/pageWindow'

describe('pageWindow', () => {
  const cases: [number, number, PageWindowItem[]][] = [
    [1, 1, [1]],
    [1, 2, [1, 2]],
    [1, 3, [1, 2, 3]],
    [2, 4, [1, 2, 3, 4]],
    [1, 5, [1, 2, 'ellipsis', 5]],
    [3, 5, [1, 2, 3, 4, 5]],
    [5, 5, [1, 'ellipsis', 4, 5]],
    [1, 20, [1, 2, 'ellipsis', 20]],
    [10, 20, [1, 'ellipsis', 9, 10, 11, 'ellipsis', 20]],
    [19, 20, [1, 'ellipsis', 18, 19, 20]],
  ]

  it.each(cases)('windows page %i of %i pages', (page, pageCount, expected) => {
    expect(pageWindow(page, pageCount)).toEqual(expected)
  })

  it('returns nothing when there are no pages', () => {
    expect(pageWindow(1, 0)).toEqual([])
  })
})
