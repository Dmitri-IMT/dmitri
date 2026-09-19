import Timestamp from '@/components/Timestamp'
import AgentPresence from '@/pages/agents/AgentPresence'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']

function AgentIdentity({ agent }: { agent: AgentDetail }) {
  return (
    <div data-testid="agents-identity" className="flex min-w-0 flex-col gap-2">
      <h2 data-testid="agents-name" className="text-title-lg">
        {agent.display_name}
      </h2>
      <p
        data-testid="agents-presence"
        tabIndex={-1}
        className="text-body-md text-muted-foreground"
      >
        <AgentPresence agent={agent} /> ·{' '}
        {agent.last_seen_at ? (
          <>
            last report <Timestamp value={agent.last_seen_at} />
          </>
        ) : (
          'no report yet'
        )}
      </p>
    </div>
  )
}

export default AgentIdentity
