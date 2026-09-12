import { useEffect, useRef, useState } from 'react'
import { skipToken, useQuery, useQueryClient } from '@tanstack/react-query'
import { createScanCommand, getAgent } from '@/api/agents'
import { readApiError } from '@/api/apiError'
import { COMMAND_POLL_INTERVAL_MS, getCommand } from '@/api/commands'
import { queryKeys } from '@/api/queryKeys'
import { useToast } from '@/hooks/useToast'
import { isTerminalCommandStatus } from '@/lib/commandStatus'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']
type CommandDetail = components['schemas']['CommandDetail']
type ScanMode = components['schemas']['ScanMode']
type NspiSubmode = components['schemas']['NspiSubmode']

export type ScanSelection = {
  scanMode: ScanMode
  nspiSubmode?: NspiSubmode
}

export type TriggerOutcome = 'followed' | 'subnet-stale' | 'refused'

export type ScanCommand = {
  command: CommandDetail | null
  following: boolean
  triggering: boolean
  trigger: (selection: ScanSelection) => Promise<TriggerOutcome>
}

export function useScanCommand(agent: AgentDetail): ScanCommand {
  const queryClient = useQueryClient()
  const { show } = useToast()
  const [triggering, setTriggering] = useState(false)
  const [followedCommandId, setFollowedCommandId] = useState<string | null>(
    agent.active_command_id ?? null,
  )
  const [lastObservedActiveCommandId, setLastObservedActiveCommandId] =
    useState<string | null>(agent.active_command_id ?? null)
  const triggeringRef = useRef(false)
  const sweptCommandId = useRef<string | null>(null)

  const observedActiveCommandId = agent.active_command_id ?? null
  if (observedActiveCommandId !== lastObservedActiveCommandId) {
    setLastObservedActiveCommandId(observedActiveCommandId)
    if (observedActiveCommandId !== null) {
      setFollowedCommandId(observedActiveCommandId)
    }
  }

  const commandQuery = useQuery({
    queryKey: queryKeys.commands.detail(followedCommandId ?? ''),
    queryFn: followedCommandId
      ? () => getCommand(followedCommandId)
      : skipToken,
    refetchInterval: (query) =>
      isTerminalCommandStatus(query.state.data?.status)
        ? false
        : COMMAND_POLL_INTERVAL_MS,
  })

  useEffect(() => {
    const command = commandQuery.data
    if (command?.status !== 'done') return
    if (sweptCommandId.current === command.command_id) return
    sweptCommandId.current = command.command_id

    void queryClient.invalidateQueries({ queryKey: queryKeys.scans.all })
    void queryClient.invalidateQueries({ queryKey: queryKeys.hosts.all })
    void queryClient.invalidateQueries({ queryKey: queryKeys.findings.all })
    void queryClient.invalidateQueries({
      queryKey: queryKeys.agents.detail(agent.agent_id),
    })
  }, [agent.agent_id, commandQuery.data, queryClient])

  async function trigger(selection: ScanSelection): Promise<TriggerOutcome> {
    if (!agent.target_subnet || triggeringRef.current) return 'refused'
    triggeringRef.current = true
    setTriggering(true)
    try {
      const scanMode = selection.scanMode
      const command = await createScanCommand(
        agent.agent_id,
        scanMode === 'nspi'
          ? {
              scan_mode: scanMode,
              subnet: agent.target_subnet,
              nspi_options: {
                version: 1,
                submode: selection.nspiSubmode ?? 'inventory',
                active_risk_acknowledged: false,
              },
            }
          : {
              scan_mode: scanMode,
              subnet: agent.target_subnet,
            },
      )
      setFollowedCommandId(command.command_id)
      return 'followed'
    } catch (error) {
      const { status, code } = readApiError(error)
      if (status === 409 && code === 'device_busy') {
        const detail = await queryClient.fetchQuery({
          queryKey: queryKeys.agents.detail(agent.agent_id),
          queryFn: () => getAgent(agent.agent_id),
        })
        if (detail.active_command_id) {
          setFollowedCommandId(detail.active_command_id)
          setLastObservedActiveCommandId(detail.active_command_id)
          show('That Pi is already scanning. Showing the scan in progress.')
          return 'followed'
        }
        show("Couldn't start the scan.")
      } else if (status === 503 && code === 'device_offline') {
        show('Pi seems to be offline.')
        void queryClient.invalidateQueries({
          queryKey: queryKeys.agents.detail(agent.agent_id),
        })
      } else if (status === 422 && code === 'subnet_not_reported') {
        show(
          "The Pi doesn't report that network any more. Pick the network to scan again.",
        )
        void queryClient.invalidateQueries({
          queryKey: queryKeys.agents.detail(agent.agent_id),
        })
        return 'subnet-stale'
      } else {
        show("Couldn't start the scan.")
      }
      return 'refused'
    } finally {
      triggeringRef.current = false
      setTriggering(false)
    }
  }

  return {
    command: commandQuery.data ?? null,
    following: followedCommandId !== null,
    triggering,
    trigger,
  }
}
