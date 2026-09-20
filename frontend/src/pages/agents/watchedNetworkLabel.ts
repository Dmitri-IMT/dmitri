import { findAvailableSubnet } from '@/lib/subnetLabel'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']
type AvailableSubnet = components['schemas']['AvailableSubnet']

export function watchedNetworkLabel(
  cidr: string,
  subnet: AvailableSubnet | null,
): string {
  if (subnet) return `${subnet.cidr} (${subnet.interface})`
  return cidr
}

export function resolveWatchedNetwork(agent: AgentDetail) {
  return agent.target_subnet
    ? findAvailableSubnet(agent.available_subnets, agent.target_subnet)
    : null
}
