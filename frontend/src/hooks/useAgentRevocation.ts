import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { restoreAgent, revokeAgent } from '@/api/agents'
import { queryKeys } from '@/api/queryKeys'
import { useToast } from '@/hooks/useToast'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']

export function useAgentRevocation(agent: AgentDetail) {
  const queryClient = useQueryClient()
  const { show } = useToast()
  const [restoring, setRestoring] = useState(false)
  const [revokeError, setRevokeError] = useState<string | null>(null)
  const [restoreError, setRestoreError] = useState<string | null>(null)

  async function revoke(): Promise<boolean> {
    setRevokeError(null)
    try {
      await revokeAgent(agent.agent_id)
      await queryClient.invalidateQueries({ queryKey: queryKeys.agents.all })
      show(`${agent.display_name} was revoked.`)
      return true
    } catch {
      setRevokeError("Couldn't revoke this device. Try again.")
      return false
    }
  }

  async function restore(): Promise<boolean> {
    setRestoreError(null)
    setRestoring(true)
    try {
      await restoreAgent(agent.agent_id)
      await queryClient.invalidateQueries({ queryKey: queryKeys.agents.all })
      show(
        `${agent.display_name} was restored. It reconnects on its next hourly attempt, within the hour.`,
      )
      return true
    } catch {
      setRestoreError("Couldn't restore this device. Try again.")
      return false
    } finally {
      setRestoring(false)
    }
  }

  return {
    revoke,
    restore,
    restoring,
    revokeError,
    restoreError,
  }
}
