import type { UseQueryResult } from '@tanstack/react-query'
import { readApiError } from '@/api/apiError'

export type DetailState<T> =
  | { state: 'notFound' }
  | { state: 'error'; retry: () => void }
  | { state: 'loading' }
  | { state: 'ready'; data: T }

export function readDetailState<T>(
  id: string,
  query: UseQueryResult<T>,
): DetailState<T> {
  if (
    id === '' ||
    (query.isError && readApiError(query.error).status === 404)
  ) {
    return { state: 'notFound' }
  }

  if (query.isError) {
    return {
      state: 'error',
      retry: () => {
        void query.refetch()
      },
    }
  }

  if (query.isPending) return { state: 'loading' }

  return { state: 'ready', data: query.data }
}
