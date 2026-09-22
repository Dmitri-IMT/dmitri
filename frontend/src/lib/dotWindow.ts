export function dotWindow(
  page: number,
  pageCount: number,
  max = 10,
): number[] {
  if (pageCount <= 0) return []
  if (pageCount <= max) {
    return Array.from({ length: pageCount }, (_, index) => index + 1)
  }

  const start = Math.max(
    1,
    Math.min(page - Math.floor(max / 2), pageCount - max + 1),
  )
  return Array.from({ length: max }, (_, index) => start + index)
}
