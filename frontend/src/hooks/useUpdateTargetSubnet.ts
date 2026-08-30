import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { readApiError } from '@/api/apiError'
import { updateAgentTargetSubnet } from '@/api/agents'
import { queryKeys } from '@/api/queryKeys'
import { useToast } from '@/hooks/useToast'
import { findAvailableSubnet } from '@/lib/subnetLabel'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']

function initialSelection(agent: AgentDetail): string {
  return agent.target_subnet
    ? (findAvailableSubnet(agent.available_subnets, agent.target_subnet)
        ?.cidr ?? '')
    : ''
}

export function useUpdateTargetSubnet(agent: AgentDetail, onSaved: () => void) {
  const queryClient = useQueryClient()
  const { show } = useToast()
  const [selected, setSelected] = useState(() => initialSelection(agent))
  const [saving, setSaving] = useState(false)
  const [refusal, setRefusal] = useState<string | null>(null)

  async function save() {
    if (!findAvailableSubnet(agent.available_subnets, selected)) return
    setRefusal(null)
    setSaving(true)
    try {
      const updated = await updateAgentTargetSubnet(agent.agent_id, {
        target_subnet: selected,
      })
      queryClient.setQueryData(queryKeys.agents.detail(agent.agent_id), updated)
      onSaved()
    } catch (error) {
      const { status, code } = readApiError(error)
      let message: string
      if (status === 409 && code === 'device_offline') {
        message = "Couldn't reach the Pi; nothing changed."
      } else if (status === 422 && code === 'subnet_not_reported') {
        message =
          "The Pi doesn't report that network any more; nothing changed."
      } else {
        message = "Couldn't save that network; nothing changed."
      }
      setRefusal(message)
      show(message)
      if (status === 422 && code === 'subnet_not_reported') {
        await queryClient.invalidateQueries({
          queryKey: queryKeys.agents.detail(agent.agent_id),
        })
      }
    } finally {
      setSaving(false)
    }
  }

  return {
    selected,
    saving,
    refusal,
    selectSubnet: (cidr: string) => {
      setRefusal(null)
      setSelected(cidr)
    },
    save,
  }
}
