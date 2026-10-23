import { apiClient } from './client'
import type { components } from '@/types/openapi'

type McpInfo = components['schemas']['McpInfo']
type McpAuthorizationView = components['schemas']['McpAuthorizationView']
type McpConsentRequest = components['schemas']['McpConsentRequest']
type McpConsentResponse = components['schemas']['McpConsentResponse']
type McpConnectionList = components['schemas']['McpConnectionList']

export async function getMcpInfo(): Promise<McpInfo> {
  return (await apiClient.get<McpInfo>('/mcp/info')).data
}

export async function getMcpAuthorization(requestToken: string) {
  return (
    await apiClient.get<McpAuthorizationView>('/mcp/authorization', {
      params: { request_token: requestToken },
    })
  ).data
}

export async function decideMcpAuthorization(body: McpConsentRequest) {
  return (await apiClient.post<McpConsentResponse>('/mcp/authorization', body))
    .data
}

export async function getMcpConnections() {
  return (await apiClient.get<McpConnectionList>('/mcp/connections')).data
}

export async function disconnectMcp(connectionId: string) {
  await apiClient.delete(`/mcp/connections/${connectionId}`)
}
