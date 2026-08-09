import { apiClient } from './client'
import type { components } from '../types/openapi'

type ChangePasswordRequest = components['schemas']['ChangePasswordRequest']

export async function changePassword(
  request: ChangePasswordRequest,
): Promise<void> {
  await apiClient.post('/auth/change-password', request)
}
