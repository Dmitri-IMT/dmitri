import DataTable, { type DataTableColumn } from '@/components/DataTable'
import EmptyMark from '@/components/EmptyMark'
import SeverityBadge from '@/components/SeverityBadge'
import Timestamp from '@/components/Timestamp'
import type { components } from '@/types/openapi'

type HostScanHistoryEntry = components['schemas']['HostScanHistoryEntry']

const columns: DataTableColumn<HostScanHistoryEntry>[] = [
  {
    key: 'timestamp',
    label: 'When',
    width: 'w-2/5',
    render: (entry) => <Timestamp value={entry.timestamp} />,
  },
  {
    key: 'scan_mode',
    label: 'Mode',
    width: 'w-1/5',
    render: (entry) => entry.scan_mode,
  },
  {
    key: 'open_ports_count',
    label: 'Open ports',
    width: 'w-1/5',
    align: 'right',
    render: (entry) => (
      <span className="block text-right tabular-nums">
        {entry.open_ports_count}
      </span>
    ),
  },
  {
    key: 'highest_severity',
    label: 'Highest severity',
    width: 'w-1/5',
    render: (entry) =>
      entry.highest_severity == null ? (
        <EmptyMark />
      ) : (
        <SeverityBadge severity={entry.highest_severity} />
      ),
  },
]

function HostScanHistoryTable({
  history,
}: {
  history: HostScanHistoryEntry[]
}) {
  return (
    <DataTable
      columns={columns}
      rows={history}
      rowId={(entry) => entry.scan_id}
      testId="host-history-table"
      caption="Scans this host has appeared in"
      rowAction={{
        kind: 'link',
        to: (entry) => `/scans/${entry.scan_id}`,
        label: (entry) => `Open scan ${entry.scan_id}`,
      }}
    />
  )
}

export default HostScanHistoryTable
