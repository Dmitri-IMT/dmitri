import { useCallback, useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getAgentUpdate,
  getAgentUpdateAvailability,
  listAgentUpdates,
  requestAgentUpdate,
  type AgentUpdateHistoryPage,
  type UpdateOperationView,
} from '@/api/agentUpdates'
import { queryKeys } from '@/api/queryKeys'

export const ACTIVE_PHASES: UpdateOperationView['phase'][] = [
  'requested',
  'preparing',
  'installing',
  'verifying',
  'awaiting_confirmation',
  'recovering',
]

const TERMINAL_PHASES: UpdateOperationView['phase'][] = [
  'succeeded',
  'failed',
  'expired',
  'rolled_back',
  'needs_intervention',
]

export function useAgentUpdate(agentId: string) {
  const queryClient = useQueryClient()
  const idempotencyKey = useRef<string | null>(null)
  const requestPending = useRef(false)
  const historyRefreshKey = useRef<string | null>(null)
  const terminalRefreshKey = useRef<string | null>(null)

  const availability = useQuery({
    queryKey: queryKeys.agentUpdates.availability(agentId),
    queryFn: () => getAgentUpdateAvailability(agentId),
    enabled: agentId !== '',
  })
  const history = useQuery({
    queryKey: queryKeys.agentUpdates.history(agentId),
    queryFn: () => listAgentUpdates(agentId),
    enabled: agentId !== '',
  })

  const latest = history.data?.data[0]
  const operation = useQuery({
    queryKey: queryKeys.agentUpdates.operation(latest?.update_id ?? ''),
    queryFn: () => getAgentUpdate(latest!.update_id),
    enabled: Boolean(latest?.update_id),
    refetchInterval: (query) => {
      const phase = query.state.data?.phase ?? latest?.phase
      return phase && ACTIVE_PHASES.includes(phase) ? 5000 : false
    },
  })

  useEffect(() => {
    const current = operation.data
    const historical = history.data?.data[0]
    const refreshKey = current ? `${current.update_id}:${current.phase}` : null
    if (
      current &&
      TERMINAL_PHASES.includes(current.phase) &&
      terminalRefreshKey.current !== refreshKey
    ) {
      terminalRefreshKey.current = refreshKey
      void Promise.all([
        queryClient.invalidateQueries({
          queryKey: queryKeys.agents.detail(agentId),
        }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.agentUpdates.availability(agentId),
        }),
      ])
    }
    if (
      current &&
      historical?.update_id === current.update_id &&
      historical.phase !== current.phase &&
      historyRefreshKey.current !== refreshKey
    ) {
      historyRefreshKey.current = refreshKey
      void queryClient.invalidateQueries({
        queryKey: queryKeys.agentUpdates.history(agentId),
      })
    }
  }, [agentId, history.data, operation.data, queryClient])

  const refresh = useCallback(async () => {
    await Promise.allSettled([
      availability.refetch(),
      history.refetch(),
      ...(latest ? [operation.refetch()] : []),
      queryClient.invalidateQueries({
        queryKey: queryKeys.agents.detail(agentId),
      }),
    ])
  }, [agentId, availability, history, latest, operation, queryClient])

  const request = useCallback(
    async (releaseId: string, expectedObservedVersion: string) => {
      if (requestPending.current) return null
      requestPending.current = true
      idempotencyKey.current ??= crypto.randomUUID()
      try {
        const result = await requestAgentUpdate(
          agentId,
          {
            release_id: releaseId,
            expected_observed_version: expectedObservedVersion,
          },
          idempotencyKey.current,
        )
        idempotencyKey.current = null
        queryClient.setQueryData(
          queryKeys.agentUpdates.operation(result.update_id),
          result,
        )
        queryClient.setQueryData(
          queryKeys.agentUpdates.history(agentId),
          (current: AgentUpdateHistoryPage | undefined) => ({
            ...current,
            data: [
              result,
              ...(current?.data ?? []).filter(
                (item) => item.update_id !== result.update_id,
              ),
            ],
          }),
        )
        await Promise.all([
          queryClient.invalidateQueries({
            queryKey: queryKeys.agents.detail(agentId),
          }),
          queryClient.invalidateQueries({
            queryKey: queryKeys.agentUpdates.availability(agentId),
          }),
          queryClient.invalidateQueries({
            queryKey: queryKeys.agentUpdates.history(agentId),
          }),
        ])
        return result
      } finally {
        requestPending.current = false
      }
    },
    [agentId, queryClient],
  )

  return {
    availability,
    history,
    operation,
    refresh,
    request,
  }
}
