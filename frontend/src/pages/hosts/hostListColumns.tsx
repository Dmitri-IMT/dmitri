import type { HostSortBy } from '@/api/hosts'
import type { DataTableColumn } from '@/components/DataTable'
import EmptyMark from '@/components/EmptyMark'
import SeverityBadge from '@/components/SeverityBadge'
import Timestamp from '@/components/Timestamp'
import type { components } from '@/types/openapi'

type HostSummary = components['schemas']['HostSummary']


export const hostListColumns: DataTableColumn<HostSummary, HostSortBy>[] = [
  {
    key: 'hostname',
    label: 'Host',
    width: 'w-1/5',
    sortable: true,
    render: (host) =>
      host.hostname ? (
        <span className="block truncate" title={host.hostname}>
          {host.hostname}
        </span>
      ) : (
        <span className="text-muted-foreground">(unnamed)</span>
      ),
  },
  {
    key: 'ip',
    label: 'IP',
    width: 'w-3/20',
    sortable: true,
    render: (host) => (
      <span className="block truncate" title={host.ip}>
        {host.ip}
      </span>
    ),
  },
  {
    key: 'mac',
    label: 'MAC',
    width: 'w-1/5',
    render: (host) =>
      host.mac ? (
        <span className="block truncate" title={host.mac}>
          {host.mac}
        </span>
      ) : (
        <EmptyMark />
      ),
  },
  {
    key: 'vendor',
    label: 'Vendor',
    width: 'w-3/20',
    sortable: true,
    render: (host) => (
      <span className="block truncate" title={host.vendor}>
        {host.vendor}
      </span>
    ),
  },
  {
    key: 'open_ports_count',
    label: 'Open ports',
    width: 'w-1/10',
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
    width: 'w-1/10',
    render: (host) =>
      host.highest_severity == null ? (
        <EmptyMark />
      ) : (
        <SeverityBadge severity={host.highest_severity} />
      ),
  },
  {
    key: 'last_seen_at',
    label: 'Last seen',
    width: 'w-1/10',
    sortable: true,
    render: (host) => <Timestamp value={host.last_seen_at} />,
  },
]
