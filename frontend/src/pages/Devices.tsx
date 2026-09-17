import { useQuery } from '@tanstack/react-query'
import { listAgents } from '@/api/agents'
import { queryKeys } from '@/api/queryKeys'
import ListSurface from '@/components/ListSurface'
import PageHeader from '@/components/PageHeader'
import { readAgentPresence } from '@/lib/agentPresence'
import { deviceListColumns } from '@/pages/agents/deviceListColumns'

function Devices() {
  const now = new Date()
  const query = useQuery({
    queryKey: queryKeys.agents.list(),
    queryFn: listAgents,
  })

  return (
    <div data-testid="devices-page" className="flex flex-col gap-12">
      <PageHeader
        title="Devices"
        subtitle="The Dmitri boxes reporting to this organisation."
      />
      <ListSurface
        testId="devices"
        query={query}
        columns={deviceListColumns(now)}
        rowId={(agent) => agent.agent_id}
        caption="Dmitri boxes"
        errorMessage="Couldn't load your devices."
        empty={{
          heading: 'No box connected yet',
          body: 'Your installer connects the box on site; it appears here once it comes online.',
          note: (
            <p
              data-testid="devices-blank-note"
              className="text-body-sm text-muted-foreground"
            >
              Contact whoever installed Dmitri if you were expecting one.
            </p>
          ),
        }}
        rowAction={{
          kind: 'link',
          to: (agent) => `/devices/${agent.agent_id}`,
          label: (agent) => `Open ${agent.display_name}`,
        }}
        rowTone={(agent) =>
          readAgentPresence(agent).kind === 'online' ? undefined : 'muted'
        }
      />
    </div>
  )
}

export default Devices
