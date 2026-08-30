import { skipToken, useQuery } from '@tanstack/react-query'
import { getAgent, listAgents } from '@/api/agents'
import { queryKeys } from '@/api/queryKeys'

export function usePrimaryAgent() {
  const listQuery = useQuery({
    queryKey: queryKeys.agents.list(),
    queryFn: listAgents,
  })
  const agentId = listQuery.data?.data[0]?.agent_id
  const detailQuery = useQuery({
    queryKey: queryKeys.agents.detail(agentId ?? ''),
    queryFn: agentId ? () => getAgent(agentId) : skipToken,
  })

  return {
    listQuery,
    detailQuery,
    agent: detailQuery.data ?? null,
    refetch: () => {
      void listQuery.refetch()
      if (agentId) void detailQuery.refetch()
    },
  }
}
