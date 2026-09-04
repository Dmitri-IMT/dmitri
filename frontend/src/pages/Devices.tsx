import { useQuery } from '@tanstack/react-query'
import { listAgents } from '@/api/agents'
import { queryKeys } from '@/api/queryKeys'
import DataTable from '@/components/DataTable'
import ErrorRetry from '@/components/ErrorRetry'
import PageHeader from '@/components/PageHeader'
import DevicesBlank from '@/pages/agents/DevicesBlank'
import { deviceListColumns } from '@/pages/agents/deviceListColumns'
import type { components } from '@/types/openapi'

type AgentSummary = components['schemas']['AgentSummary']

function Devices() {
  const now = new Date()
  const query = useQuery({
    queryKey: queryKeys.agents.list(),
    queryFn: listAgents,
  })
  const rows = query.data?.data ?? []
  const table = {
    columns: deviceListColumns(now),
    rowId: (agent: AgentSummary) => agent.agent_id,
    testId: 'devices-table',
    caption: 'Dmitri boxes',
  }

  return (
    <div data-testid="devices-page" className="flex flex-col gap-12">
      <PageHeader
        title="Devices"
        subtitle="The Dmitri boxes reporting to this organisation."
      />
      {query.isError ? (
        <ErrorRetry
          testId="devices-error"
          message="Couldn't load your devices."
          onRetry={() => {
            void query.refetch()
          }}
        />
      ) : query.isPending ? (
        <div data-testid="devices-loading">
          <DataTable {...table} rows={[]} isPending />
        </div>
      ) : rows.length === 0 ? (
        <DevicesBlank />
      ) : (
        <DataTable
          {...table}
          rows={rows}
          rowAction={{
            kind: 'link',
            to: (agent) => `/devices/${agent.agent_id}`,
            label: (agent) => `Open ${agent.display_name}`,
          }}
          rowTone={(agent) => (agent.online ? undefined : 'muted')}
        />
      )}
    </div>
  )
}

export default Devices
