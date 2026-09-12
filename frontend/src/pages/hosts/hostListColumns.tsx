import type { HostSortBy } from '@/api/hosts'
import type { DataTableColumn } from '@/components/DataTable'
import EmptyMark from '@/components/EmptyMark'
import SeverityWord from '@/components/SeverityWord'
import Timestamp from '@/components/Timestamp'
import { weeksSinceLastSeen } from '@/lib/hostLastSeen'
import { MACHINE_TYPE_LABELS } from '@/lib/machineType'
import type { components } from '@/types/openapi'

type HostSummary = components['schemas']['HostSummary']

function machineCell(host: HostSummary, now: Date, quiet: boolean) {
  const weeks = quiet ? weeksSinceLastSeen(host.last_seen_at, now) : 0
  return (
    <>
      {host.hostname ? (
        <span className="block truncate" title={host.hostname}>
          {host.hostname}
        </span>
      ) : (
        <span className="block truncate font-mono" title={host.ip}>
          {host.ip}
        </span>
      )}
      {!host.hostname && (
        <span className="block truncate text-muted-foreground">
          No name yet
        </span>
      )}
      {quiet && (
        <span className="block truncate text-muted-foreground">
          Not seen for {weeks} {weeks === 1 ? 'week' : 'weeks'}
        </span>
      )}
    </>
  )
}

export function hostListColumns(
  now: Date,
  quiet: boolean,
): DataTableColumn<HostSummary, HostSortBy>[] {
  return [
    {
      key: 'hostname',
      label: 'Machine',
      width: 'w-13/50',
      sortable: true,
      render: (host) => machineCell(host, now, quiet),
    },
    {
      key: 'ip',
      label: 'Address',
      width: 'w-8/50',
      sortable: true,
      render: (host) => (
        <span className="block truncate font-mono" title={host.ip}>
          {host.ip}
        </span>
      ),
    },
    {
      key: 'machine_type',
      label: 'Type',
      width: 'w-8/50',
      render: (host) => {
        const label = MACHINE_TYPE_LABELS[host.machine_type]
        return label ? (
          <span className="block truncate">{label}</span>
        ) : (
          <EmptyMark />
        )
      },
    },
    {
      key: 'vulnerability_count',
      label: 'Vulnerabilities',
      width: 'w-5/50',
      sortable: true,
      render: (host) => (
        <span className="block tabular-nums">{host.vulnerability_count}</span>
      ),
    },
    {
      key: 'highest_severity',
      label: 'Highest severity',
      width: 'w-8/50',
      render: (host) => <SeverityWord severity={host.highest_severity} />,
    },
    {
      key: 'last_seen_at',
      label: 'Last seen',
      width: 'w-8/50',
      sortable: true,
      render: (host) => <Timestamp value={host.last_seen_at} now={now} />,
    },
  ]
}
