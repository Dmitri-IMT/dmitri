import { apiClient } from './client'
import type { components } from '../types/openapi'

type UserProfileResponse = components['schemas']['UserProfileResponse']
type OrgMember = components['schemas']['OrgMember']
type OrgMemberListResponse = components['schemas']['OrgMemberListResponse']
type UpdateUserRoleRequest = components['schemas']['UpdateUserRoleRequest']

export async function getCurrentUser(): Promise<UserProfileResponse> {
  const response = await apiClient.get<UserProfileResponse>('/users/me')
  return response.data
}

export async function deleteCurrentUser(): Promise<void> {
  await apiClient.delete('/users/me')
}

export async function listOrgMembers(): Promise<OrgMemberListResponse> {
  const response = await apiClient.get<OrgMemberListResponse>('/users')
  return response.data
}

export async function updateUserRole(
  userId: string,
  request: UpdateUserRoleRequest,
): Promise<OrgMember> {
  const response = await apiClient.patch<OrgMember>(`/users/${userId}`, request)
  return response.data
}

export async function deleteUser(userId: string): Promise<void> {
  await apiClient.delete(`/users/${userId}`)
}
