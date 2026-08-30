import { usePrimaryAgent } from '@/hooks/usePrimaryAgent'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']

export type AgentScreen =
  | { state: 'loading' }
  | { state: 'error'; retry: () => void }
  | { state: 'blank' }
  | { state: 'ready'; agent: AgentDetail }

export function useAgentScreen(): AgentScreen {
  const { listQuery, detailQuery, refetch } = usePrimaryAgent()

  if (detailQuery.data) return { state: 'ready', agent: detailQuery.data }
  if (listQuery.isError || detailQuery.isError) {
    return { state: 'error', retry: refetch }
  }
  if (listQuery.isPending) return { state: 'loading' }
  if (listQuery.data.data.length === 0) return { state: 'blank' }
  if (detailQuery.isPending) return { state: 'loading' }
  return { state: 'loading' }
}
