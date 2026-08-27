import type { DataTableColumn } from '@/components/DataTable'
import type { components } from '@/types/openapi'

type Port = components['schemas']['Port']

function dash() {
  return <span className="text-muted-foreground">—</span>
}

export const portColumns: DataTableColumn<Port>[] = [
  {
    key: 'port',
    label: 'Port',
    width: 'w-1/5',
    render: (port) => <span className="block tabular-nums">{port.port}</span>,
  },
  {
    key: 'protocol',
    label: 'Protocol',
    width: 'w-1/5',
    render: (port) => port.protocol,
  },
  {
    key: 'service',
    label: 'Service',
    width: 'w-1/5',
    render: (port) => (
      <span className="block truncate" title={port.service}>
        {port.service}
      </span>
    ),
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
        dash()
      ),
  },
]
