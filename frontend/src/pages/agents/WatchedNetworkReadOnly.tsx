import { useSession } from '@/auth/useSession'
import {
  resolveWatchedNetwork,
  watchedNetworkLabel,
} from '@/pages/agents/watchedNetworkLabel'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']

function WatchedNetworkReadOnly({ agent }: { agent: AgentDetail }) {
  const { user } = useSession()
  const target = resolveWatchedNetwork(agent)

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-title-sm">Watched network</h3>
      <p
        data-testid="agents-network"
        className="min-w-0 text-body-md text-muted-foreground"
      >
        {agent.target_subnet
          ? watchedNetworkLabel(agent.target_subnet, target)
          : user?.role === 'viewer'
            ? 'No network chosen yet. Ask your admin to choose one.'
            : 'No network chosen yet.'}
      </p>
    </div>
  )
}

export default WatchedNetworkReadOnly
