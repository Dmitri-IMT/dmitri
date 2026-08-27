import { Link } from 'react-router'
import DataTable, { type DataTableColumn } from '@/components/DataTable'
import { Button } from '@/components/ui/button'
import type { components } from '@/types/openapi'

type ScanHostView = components['schemas']['ScanHostView']
type Port = components['schemas']['Port']

function dash() {
  return <span className="text-muted-foreground">—</span>
}

function hostName(host: ScanHostView): string {
  return host.hostname !== '' ? host.hostname : host.ip
}

const portColumns: DataTableColumn<Port>[] = [
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

function HostPortsPanel({ host }: { host: ScanHostView }) {
  const name = hostName(host)
  return (
    <div
      data-testid={`host-ports-panel-${host.host_id}`}
      className="flex flex-col gap-4 p-4"
    >
      {host.ports.length > 0 && (
        <DataTable
          columns={portColumns}
          rows={host.ports}
          rowId={(port) => `${port.port}/${port.protocol}`}
          testId={`scan-hosts-ports-${host.host_id}`}
          caption={`Open ports on ${name}`}
        />
      )}
      <Button asChild variant="outline">
        <Link
          to={`/hosts/${host.host_id}`}
          data-testid={`scan-hosts-open-${host.host_id}`}
        >
          Open {name}
        </Link>
      </Button>
    </div>
  )
}

function ScanHostsTable({
  hosts,
  openHostId,
  onOpenHostChange,
}: {
  hosts: ScanHostView[]
  openHostId: string | null
  onOpenHostChange: (id: string | null) => void
}) {
  const columns: DataTableColumn<ScanHostView>[] = [
    {
      key: 'hostname',
      label: 'Host',
      width: 'w-1/4',
      render: (host) => {
        const name = hostName(host)
        return (
          <span className="block truncate" title={name}>
            {name}
          </span>
        )
      },
    },
    {
      key: 'ip',
      label: 'IP',
      width: 'w-1/5',
      render: (host) => (
        <span className="block truncate" title={host.ip}>
          {host.ip}
        </span>
      ),
    },
    {
      key: 'mac',
      label: 'MAC',
      width: 'w-1/4',
      render: (host) =>
        host.mac ? (
          <span className="block truncate" title={host.mac}>
            {host.mac}
          </span>
        ) : (
          dash()
        ),
    },
    {
      key: 'vendor',
      label: 'Vendor',
      width: 'w-1/5',
      render: (host) => (
        <span className="block truncate" title={host.vendor}>
          {host.vendor}
        </span>
      ),
    },
    {
      key: 'ports',
      label: 'Open ports',
      width: 'w-1/10',
      align: 'right',
      render: (host) => (
        <span className="block text-right tabular-nums">
          {host.ports.length}
        </span>
      ),
    },
  ]

  return (
    <DataTable
      columns={columns}
      rows={hosts}
      rowId={(host) => host.host_id}
      testId="scan-hosts-table"
      caption="Hosts in this scan"
      rowAction={{
        kind: 'expand',
        panel: (host) => <HostPortsPanel host={host} />,
        label: (host) => `Show ports for ${hostName(host)}`,
        openRowId: openHostId,
        onOpenRowChange: onOpenHostChange,
      }}
    />
  )
}

export default ScanHostsTable
