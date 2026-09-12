import type { DataTableColumn } from '@/components/DataTable'
import EmptyMark from '@/components/EmptyMark'
import Timestamp from '@/components/Timestamp'
import type { components } from '@/types/openapi'

type HostPort = components['schemas']['HostPort']

export const portColumns: DataTableColumn<HostPort>[] = [
  {
    key: 'service',
    label: 'Service',
    width: 'w-17/50',
    render: (port) => (
      <>
        <span className="block truncate" title={port.service}>
          {port.service}
        </span>
        <span className="block truncate font-mono text-muted-foreground">
          {port.port}
        </span>
      </>
    ),
  },
  {
    key: 'protocol',
    label: 'Protocol',
    width: 'w-7/50',
    render: (port) => port.protocol,
  },
  {
    key: 'version',
    label: 'Version',
    width: 'w-3/10',
    render: (port) =>
      port.version ? (
        <span className="block truncate" title={port.version}>
          {port.version}
        </span>
      ) : (
        <EmptyMark />
      ),
  },
  {
    key: 'last_seen_at',
    label: 'Last seen',
    width: 'w-11/50',
    render: (port) => <Timestamp value={port.last_seen_at} />,
  },
]
