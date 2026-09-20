import EmptyMark from '@/components/EmptyMark'
import type { DataTableColumn } from '@/components/DataTable'
import Timestamp from '@/components/Timestamp'
import AgentPresence from '@/pages/agents/AgentPresence'
import type { components } from '@/types/openapi'

type AgentSummary = components['schemas']['AgentSummary']

export function deviceListColumns(now: Date): DataTableColumn<AgentSummary>[] {
  return [
    {
      key: 'display_name',
      label: 'Box',
      width: 'w-3/10',
      render: (agent) => (
        <span className="block truncate" title={agent.display_name}>
          {agent.display_name}
        </span>
      ),
    },
    {
      key: 'target_subnet',
      label: 'Network',
      width: 'w-1/4',
      render: (agent) =>
        agent.target_subnet ? (
          <span
            className="block truncate font-mono"
            title={agent.target_subnet}
          >
            {agent.target_subnet}
          </span>
        ) : (
          <span className="block truncate text-muted-foreground">
            No network chosen yet
          </span>
        ),
    },
    {
      key: 'online',
      label: 'Status',
      width: 'w-1/5',
      render: (agent) => (
        <AgentPresence
          agent={agent}
          now={now}
          truncate
          testId={`devices-status-${agent.agent_id}`}
        />
      ),
    },
    {
      key: 'last_seen_at',
      label: 'Last report',
      width: 'w-1/4',
      render: (agent) =>
        agent.last_seen_at ? (
          <Timestamp value={agent.last_seen_at} now={now} />
        ) : (
          <EmptyMark />
        ),
    },
  ]
}
