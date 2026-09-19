import DataTable, { type DataTableColumn } from '@/components/DataTable'
import SeverityWord from '@/components/SeverityWord'
import Timestamp from '@/components/Timestamp'
import { SCAN_MODE_LABEL } from '@/lib/scanModes'
import type { components } from '@/types/openapi'
import useI18n from '@/i18n/useI18n'

type HostScanHistoryEntry = components['schemas']['HostScanHistoryEntry']

function buildColumns(t: ReturnType<typeof useI18n>['t']): DataTableColumn<HostScanHistoryEntry>[] {
  return [
  {
    key: 'timestamp',
    label: t('common.when'),
    width: 'w-17/50',
    render: (entry) => (
      <span className="block truncate">
        <Timestamp value={entry.timestamp} />
      </span>
    ),
  },
  {
    key: 'scan_mode',
    label: t('common.mode'),
    width: 'w-11/50',
    render: (entry) => SCAN_MODE_LABEL[entry.scan_mode],
  },
  {
    key: 'open_ports_count',
    label: t('common.services'),
    width: 'w-9/50',
    render: (entry) => (
      <span className="block tabular-nums">{entry.open_ports_count}</span>
    ),
  },
  {
    key: 'highest_severity',
    label: t('common.highestSeverity'),
    width: 'w-13/50',
    render: (entry) => <SeverityWord severity={entry.highest_severity} />,
  },
  ]
}

function HostScanHistoryTable({
  history,
}: {
  history: HostScanHistoryEntry[]
}) {
  const { t } = useI18n()
  return (
    <DataTable
      columns={buildColumns(t)}
      rows={history}
      rowId={(entry) => entry.scan_id}
      testId="host-history-table"
      caption={t('common.scanHistoryCaption')}
      rowAction={{
        kind: 'link',
        to: (entry) => `/scans/${entry.scan_id}`,
        label: (entry) => t('common.openScan', { id: entry.scan_id }),
      }}
    />
  )
}

export default HostScanHistoryTable
