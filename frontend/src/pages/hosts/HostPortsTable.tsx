import DataTable, { type DataTableColumn } from '@/components/DataTable'
import type { components } from '@/types/openapi'

type Port = components['schemas']['Port']

function dash() {
  return <span className="text-muted-foreground">—</span>
}

const columns: DataTableColumn<Port>[] = [
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

function HostPortsTable({ ports }: { ports: Port[] }) {
  if (ports.length === 0) {
    return (
      <p data-testid="host-no-ports" className="text-body-md">
        No open ports. This host isn&apos;t exposing anything.
      </p>
    )
  }

  return (
    <DataTable
      columns={columns}
      rows={ports}
      rowId={(port) => `${port.port}/${port.protocol}`}
      testId="host-ports-table"
      caption="Open ports on this host"
      rowAction={undefined}
    />
  )
}

export default HostPortsTable
