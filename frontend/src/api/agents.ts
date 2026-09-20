import { apiClient } from './client'
import type { components } from '../types/openapi'

type AgentDetail = components['schemas']['AgentDetail']
type AgentListResponse = components['schemas']['AgentListResponse']
type UpdateAgentTargetSubnetRequest =
  components['schemas']['UpdateAgentTargetSubnetRequest']
type CreateCommandRequest = components['schemas']['CreateCommandRequest']
type CommandSummary = components['schemas']['CommandSummary']
export async function listAgents(): Promise<AgentListResponse> {
  const response = await apiClient.get<AgentListResponse>('/agents')
  return response.data
}

export async function getAgent(agentId: string): Promise<AgentDetail> {
  const response = await apiClient.get<AgentDetail>(`/agents/${agentId}`)
  return response.data
}

export async function revokeAgent(agentId: string): Promise<AgentDetail> {
  const response = await apiClient.post<AgentDetail>(
    `/agents/${agentId}/revoke`,
  )
  return response.data
}

export async function restoreAgent(agentId: string): Promise<AgentDetail> {
  const response = await apiClient.post<AgentDetail>(
    `/agents/${agentId}/restore`,
  )
  return response.data
}

export async function updateAgentTargetSubnet(
  agentId: string,
  body: UpdateAgentTargetSubnetRequest,
): Promise<AgentDetail> {
  const response = await apiClient.patch<AgentDetail>(
    `/agents/${agentId}`,
    body,
  )
  return response.data
}

export async function createScanCommand(
  agentId: string,
  body: CreateCommandRequest,
): Promise<CommandSummary> {
  const response = await apiClient.post<CommandSummary>(
    `/agents/${agentId}/commands`,
    body,
  )
  return response.data
}
