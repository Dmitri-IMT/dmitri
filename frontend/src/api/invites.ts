import { apiClient } from './client'
import type { components } from '../types/openapi'

type PendingInviteListResponse =
  components['schemas']['PendingInviteListResponse']
type CreateInviteRequest = components['schemas']['CreateInviteRequest']
type InviteCreatedResponse = components['schemas']['InviteCreatedResponse']

export async function listPendingInvites(): Promise<PendingInviteListResponse> {
  const response = await apiClient.get<PendingInviteListResponse>('/invites')
  return response.data
}

export async function createInvite(
  request: CreateInviteRequest,
): Promise<InviteCreatedResponse> {
  const response = await apiClient.post<InviteCreatedResponse>(
    '/invites',
    request,
  )
  return response.data
}

export async function revokeInvite(inviteId: string): Promise<void> {
  await apiClient.delete(`/invites/${inviteId}`)
}
