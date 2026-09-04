import type { HostSortBy } from '@/api/hosts'
import type { DataTableColumn } from '@/components/DataTable'
import SeverityWord from '@/components/SeverityWord'
import Timestamp from '@/components/Timestamp'
import { isQuietHost, weeksSinceLastSeen } from '@/lib/hostLastSeen'
import type { components } from '@/types/openapi'

type HostSummary = components['schemas']['HostSummary']

function machineCell(host: HostSummary, now: Date) {
  const quiet = isQuietHost(host.last_seen_at, now)
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
          Not seen for {weeksSinceLastSeen(host.last_seen_at, now)} weeks
        </span>
      )}
    </>
  )
}

export function hostListColumns(
  now: Date,
): DataTableColumn<HostSummary, HostSortBy>[] {
  return [
    {
      key: 'hostname',
      label: 'Machine',
      width: 'w-13/50',
      sortable: true,
      render: (host) => machineCell(host, now),
    },
    {
      key: 'ip',
      label: 'Address',
      width: 'w-8/50',
      sortable: true,
      render: (host) => (
        <span className="block truncate" title={host.ip}>
          {host.ip}
        </span>
      ),
    },
    {
      key: 'vendor',
      label: 'Vendor',
      width: 'w-8/50',
      sortable: true,
      render: (host) => (
        <span className="block truncate" title={host.vendor}>
          {host.vendor}
        </span>
      ),
    },
    {
      key: 'open_ports_count',
      label: 'Services',
      width: 'w-5/50',
      align: 'right',
      render: (host) => (
        <span className="block text-right tabular-nums">
          {host.open_ports_count}
        </span>
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
