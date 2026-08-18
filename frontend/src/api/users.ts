import { apiClient } from './client'
import type { components } from '../types/openapi'

type UserProfileResponse = components['schemas']['UserProfileResponse']

export async function getCurrentUser(): Promise<UserProfileResponse> {
  const response = await apiClient.get<UserProfileResponse>('/users/me')
  return response.data
}

export async function deleteCurrentUser(): Promise<void> {
  await apiClient.delete('/users/me')
}
