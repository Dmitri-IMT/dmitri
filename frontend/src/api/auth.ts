// Imports the bare instance, not `./client`, on purpose: client.ts imports `refresh`
// from this module to drive its 401 retry, so importing it back would be a cycle.
// authClient carries no interceptors by design — refreshing must never recurse.
import { authClient } from './instances'
import { clearAccessToken, setAccessToken } from './tokenStore'
import type { components } from '../types/openapi'

type LoginRequest = components['schemas']['LoginRequest']
type LoginResponse = components['schemas']['LoginResponse']
type ForgotPasswordRequest = components['schemas']['ForgotPasswordRequest']
type ResetPasswordRequest = components['schemas']['ResetPasswordRequest']
type AcceptInviteRequest = components['schemas']['AcceptInviteRequest']
type InviteLookupRequest = components['schemas']['InviteLookupRequest']
type InviteLookupResponse = components['schemas']['InviteLookupResponse']

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

export async function forgotPassword(
  request: ForgotPasswordRequest,
): Promise<void> {
  await authClient.post('/auth/forgot-password', request)
}

export async function resetPassword(
  request: ResetPasswordRequest,
): Promise<void> {
  await authClient.post('/auth/reset-password', request)
}

export async function lookupInvite(
  request: InviteLookupRequest,
): Promise<InviteLookupResponse> {
  const response = await authClient.post<InviteLookupResponse>(
    '/invites/lookup',
    request,
  )
  return response.data
}

export async function acceptInvite(
  request: AcceptInviteRequest,
): Promise<LoginResponse> {
  const response = await authClient.post<LoginResponse>(
    '/invites/accept',
    request,
  )
  setAccessToken(response.data.access_token)
  return response.data
}
