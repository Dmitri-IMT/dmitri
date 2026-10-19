import { useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/api/queryKeys'

const DELETED_DATA_KEYS = [
  queryKeys.home.all,
  queryKeys.scans.all,
  queryKeys.hosts.all,
  queryKeys.findings.all,
  queryKeys.commands.all,
]

export function useRefreshAfterDelete(): () => Promise<void> {
  const queryClient = useQueryClient()
  return async () => {
    await Promise.all(
      DELETED_DATA_KEYS.map((queryKey) =>
        queryClient.invalidateQueries({ queryKey }),
      ),
    )
  }
}
