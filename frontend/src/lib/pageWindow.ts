export type PageWindowItem = number | 'ellipsis'

export function pageWindow(page: number, pageCount: number): PageWindowItem[] {
  const shown = [...new Set([1, page - 1, page, page + 1, pageCount])]
    .filter((candidate) => candidate >= 1 && candidate <= pageCount)
    .sort((a, b) => a - b)

  return shown.flatMap((candidate, index) =>
    index > 0 && candidate - shown[index - 1] > 1
      ? (['ellipsis', candidate] as PageWindowItem[])
      : [candidate],
  )
}
