import { apiClient } from './client'
import type { components } from '@/types/openapi'

export type AgentUpdateAvailability =
  components['schemas']['AgentUpdateAvailability']
export type AgentUpdateHistoryPage =
  components['schemas']['AgentUpdateHistoryPage']
export type UpdateOperationView = components['schemas']['UpdateOperationView']
export type AgentUpdateRequest = components['schemas']['AgentUpdateRequest']

export async function getAgentUpdateAvailability(
  agentId: string,
): Promise<AgentUpdateAvailability> {
  const response = await apiClient.get<AgentUpdateAvailability>(
    `/agents/${agentId}/updates/availability`,
  )
  return response.data
}

export async function listAgentUpdates(
  agentId: string,
): Promise<AgentUpdateHistoryPage> {
  const response = await apiClient.get<AgentUpdateHistoryPage>(
    `/agents/${agentId}/updates`,
  )
  return response.data
}

export async function getAgentUpdate(
  updateId: string,
): Promise<UpdateOperationView> {
  const response = await apiClient.get<UpdateOperationView>(
    `/agent-updates/${updateId}`,
  )
  return response.data
}

export async function requestAgentUpdate(
  agentId: string,
  body: AgentUpdateRequest,
  idempotencyKey: string,
): Promise<UpdateOperationView> {
  const response = await apiClient.post<UpdateOperationView>(
    `/agents/${agentId}/updates`,
    body,
    { headers: { 'Idempotency-Key': idempotencyKey } },
  )
  return response.data
}
