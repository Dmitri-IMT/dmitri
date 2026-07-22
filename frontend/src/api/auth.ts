import { authClient } from './instances'
import { clearAccessToken, setAccessToken } from './tokenStore'
import type { components } from '../types/openapi'

type LoginRequest = components['schemas']['LoginRequest']
type LoginResponse = components['schemas']['LoginResponse']

export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  const response = await authClient.post<LoginResponse>(
    '/auth/login',
    credentials,
  )
  setAccessToken(response.data.access_token)
  return response.data
}

export async function refresh(): Promise<LoginResponse> {
  const response = await authClient.post<LoginResponse>('/auth/refresh')
  setAccessToken(response.data.access_token)
  return response.data
}

export async function logout(): Promise<void> {
  await authClient.post('/auth/logout')
  clearAccessToken()
}
