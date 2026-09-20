import Timestamp from '@/components/Timestamp'
import { readAgentPresence, type PresenceAgent } from '@/lib/agentPresence'

function AgentPresence({
  agent,
  now,
  truncate = false,
  testId,
}: {
  agent: PresenceAgent
  now?: Date
  truncate?: boolean
  testId?: string
}) {
  const presence = readAgentPresence(agent)

  return (
    <span
      data-testid={testId}
      className={truncate ? 'block truncate' : undefined}
      title={
        presence.kind !== 'revoked'
          ? undefined
          : `Revoked ${new Date(presence.revokedAt).toLocaleString()}`
      }
    >
      {presence.kind === 'revoked' ? (
        <>
          Revoked <Timestamp value={presence.revokedAt} now={now} />
        </>
      ) : presence.kind === 'online' ? (
        'Online'
      ) : (
        'Offline'
      )}
    </span>
  )
}

export default AgentPresence
