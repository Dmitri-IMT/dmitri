import type { components } from '@/types/openapi'

type AgentSummary = components['schemas']['AgentSummary']
export type PresenceAgent = Pick<AgentSummary, 'online' | 'revoked_at'>

export type AgentPresence =
  | { kind: 'revoked'; revokedAt: string }
  | { kind: 'online' }
  | { kind: 'offline' }

export function readAgentPresence(agent: PresenceAgent): AgentPresence {
  if (agent.revoked_at != null) {
    return { kind: 'revoked', revokedAt: agent.revoked_at }
  }
  return { kind: agent.online ? 'online' : 'offline' }
}
