import { useQuery } from '@tanstack/react-query'
import { listAgents } from '@/api/agents'
import { queryKeys } from '@/api/queryKeys'
import ListSurface from '@/components/ListSurface'
import PageHeader from '@/components/PageHeader'
import DevicesBlank from '@/pages/agents/DevicesBlank'
import { deviceListColumns } from '@/pages/agents/deviceListColumns'
import type { components } from '@/types/openapi'

type AgentSummary = components['schemas']['AgentSummary']
type AgentListResponse = components['schemas']['AgentListResponse']

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
      <ListSurface<AgentSummary, AgentListResponse>
        testId="devices"
        query={query}
        selectRows={(data) => data.data}
        isEmpty={(data) => data.data.length === 0}
        columns={deviceListColumns(now)}
        rowId={(agent) => agent.agent_id}
        caption="Dmitri boxes"
        errorMessage="Couldn't load your devices."
        empty={{
          heading: 'No box connected yet',
          body: 'Your installer connects the box on site; it appears here once it comes online.',
        }}
        blank={<DevicesBlank />}
        rowAction={{
          kind: 'link',
          to: (agent) => `/devices/${agent.agent_id}`,
          label: (agent) => `Open ${agent.display_name}`,
        }}
        rowTone={(agent) => (agent.online ? undefined : 'muted')}
      />
    </div>
  )
}

export default Devices
