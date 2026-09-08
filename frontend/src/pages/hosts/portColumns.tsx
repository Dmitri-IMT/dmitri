import type { DataTableColumn } from '@/components/DataTable'
import EmptyMark from '@/components/EmptyMark'
import type { components } from '@/types/openapi'

type Port = components['schemas']['Port']

export const portColumns: DataTableColumn<Port>[] = [
  {
    key: 'service',
    label: 'Service',
    width: 'w-2/5',
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
    width: 'w-1/5',
    render: (port) => port.protocol,
  },
  {
    key: 'version',
    label: 'Version',
    width: 'w-2/5',
    render: (port) =>
      port.version ? (
        <span className="block truncate" title={port.version}>
          {port.version}
        </span>
      ) : (
        <EmptyMark />
      ),
  },
]
