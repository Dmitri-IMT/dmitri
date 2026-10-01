import { apiClient } from './client'
import type { components } from '../types/openapi'

type CommandDetail = components['schemas']['CommandDetail']

export const COMMAND_POLL_INTERVAL_MS = 5_000

export async function getCommand(commandId: string): Promise<CommandDetail> {
  const response = await apiClient.get<CommandDetail>(`/commands/${commandId}`)
  return response.data
}

export async function cancelCommand(commandId: string): Promise<CommandDetail> {
  const response = await apiClient.post<CommandDetail>(
    `/commands/${commandId}/cancel`,
  )
  return response.data
}
