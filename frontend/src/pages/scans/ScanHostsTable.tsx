import DataTable, { type DataTableColumn } from '@/components/DataTable'
import EmptyMark from '@/components/EmptyMark'
import type { components } from '@/types/openapi'

type ScanHostView = components['schemas']['ScanHostView']

function machineName(host: ScanHostView): string {
  return host.hostname !== '' ? host.hostname : host.ip
}

const columns: DataTableColumn<ScanHostView>[] = [
  {
    key: 'hostname',
    label: 'Machine',
    width: 'w-6/25',
    render: (host) => {
      const name = machineName(host)
      return (
        <span className="block truncate" title={name}>
          {name}
        </span>
      )
    },
  },
  {
    key: 'ip',
    label: 'Address',
    width: 'w-9/50',
    render: (host) => (
      <span className="block truncate font-mono" title={host.ip}>
        {host.ip}
      </span>
    ),
  },
  {
    key: 'mac',
    label: 'MAC',
    width: 'w-11/50',
    render: (host) =>
      host.mac ? (
        <span className="block truncate font-mono" title={host.mac}>
          {host.mac}
        </span>
      ) : (
        <EmptyMark />
      ),
  },
  {
    key: 'vendor',
    label: 'Vendor',
    width: 'w-11/50',
    render: (host) => (
      <span className="block truncate" title={host.vendor}>
        {host.vendor}
      </span>
    ),
  },
  {
    key: 'ports',
    label: 'Services',
    width: 'w-7/50',
    align: 'right',
    render: (host) => (
      <span className="block text-right tabular-nums">{host.ports.length}</span>
    ),
  },
]

function ScanHostsTable({ hosts }: { hosts: ScanHostView[] }) {
  return (
    <DataTable
      columns={columns}
      rows={hosts}
      rowId={(host) => host.host_id}
      testId="scan-hosts-table"
      caption="Machines seen in this scan"
      rowAction={{
        kind: 'link',
        to: (host) => `/network/${host.host_id}`,
        label: (host) => `Open ${machineName(host)}`,
      }}
    />
  )
}

export default ScanHostsTable
