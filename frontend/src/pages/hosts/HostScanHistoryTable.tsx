import DataTable, { type DataTableColumn } from '@/components/DataTable'
import SeverityWord from '@/components/SeverityWord'
import Timestamp from '@/components/Timestamp'
import { SCAN_MODE_LABEL } from '@/lib/scanModes'
import type { components } from '@/types/openapi'

type HostScanHistoryEntry = components['schemas']['HostScanHistoryEntry']

const columns: DataTableColumn<HostScanHistoryEntry>[] = [
  {
    key: 'timestamp',
    label: 'When',
    width: 'w-17/50',
    render: (entry) => (
      <span className="block truncate">
        <Timestamp value={entry.timestamp} />
      </span>
    ),
  },
  {
    key: 'scan_mode',
    label: 'Mode',
    width: 'w-11/50',
    render: (entry) => SCAN_MODE_LABEL[entry.scan_mode],
  },
  {
    key: 'open_ports_count',
    label: 'Services',
    width: 'w-9/50',
    align: 'right',
    render: (entry) => (
      <span className="block tabular-nums">{entry.open_ports_count}</span>
    ),
  },
  {
    key: 'highest_severity',
    label: 'Highest severity',
    width: 'w-13/50',
    render: (entry) => <SeverityWord severity={entry.highest_severity} />,
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
      caption="Scans this machine has appeared in"
      rowAction={{
        kind: 'link',
        to: (entry) => `/scans/${entry.scan_id}`,
        label: (entry) => `Open scan ${entry.scan_id}`,
      }}
    />
  )
}

export default HostScanHistoryTable
