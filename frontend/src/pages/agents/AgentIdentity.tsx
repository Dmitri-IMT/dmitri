import EmptyMark from '@/components/EmptyMark'
import Timestamp from '@/components/Timestamp'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']

function AgentIdentity({ agent }: { agent: AgentDetail }) {
  return (
    <div data-testid="agents-identity" className="flex min-w-0 flex-col gap-2">
      <h2 data-testid="agents-name" className="font-title text-title-sm">
        {agent.display_name}
      </h2>
      <p
        data-testid="agents-presence"
        className="text-body-md text-muted-foreground"
      >
        {agent.online ? 'Online' : 'Offline'} · last seen{' '}
        {agent.last_seen_at ? (
          <Timestamp value={agent.last_seen_at} />
        ) : (
          <EmptyMark />
        )}
      </p>
    </div>
  )
}

export default AgentIdentity
