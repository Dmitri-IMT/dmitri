import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { getHome, type HomePages, type HomeSnapshot } from '@/api/home'
import { queryKeys } from '@/api/queryKeys'

export type HomeView =
  | { state: 'loading'; retry: () => void }
  | { state: 'error'; retry: () => void }
  | {
      state: 'blank' | 'clear' | 'pending'
      snapshot: HomeSnapshot
      retry: () => void
    }

export function useHome(pages: HomePages): HomeView {
  const query = useQuery({
    queryKey: queryKeys.home.snapshot(pages),
    queryFn: () => getHome(pages),
    placeholderData: keepPreviousData,
  })

  const retry = () => {
    query.refetch()
  }

  if (query.isError) {
    return { state: 'error', retry }
  }
  if (query.data === undefined) {
    return { state: 'loading', retry }
  }
  return { state: query.data.review_state, snapshot: query.data, retry }
}
