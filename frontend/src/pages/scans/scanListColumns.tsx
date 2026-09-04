import type { ReactNode } from 'react'
import EmptyMark from '@/components/EmptyMark'
import type { DataTableColumn } from '@/components/DataTable'
import SeverityWord from '@/components/SeverityWord'
import Timestamp from '@/components/Timestamp'
import { SCAN_MODE_LABEL } from '@/lib/scanModes'
import { hidesCounts, scanStatusLabel } from '@/lib/scanStatus'
import type { components } from '@/types/openapi'

type ScanSummary = components['schemas']['ScanSummary']

function statusCell(scan: ScanSummary): ReactNode {
  return (
    <span data-testid={`scans-status-${scan.scan_id}`}>
      {scanStatusLabel(scan.status)}
    </span>
  )
}

function countCell(scan: ScanSummary, value: ReactNode): ReactNode {
  if (hidesCounts(scan.status)) return <EmptyMark />
  return <span className="block text-right tabular-nums">{value}</span>
}

function highestCell(scan: ScanSummary): ReactNode {
  if (hidesCounts(scan.status)) return <EmptyMark />
  return <SeverityWord severity={scan.highest_severity} />
}

export const scanListColumns: DataTableColumn<ScanSummary>[] = [
  {
    key: 'timestamp',
    label: 'When',
    width: 'w-6/25',
    render: (scan) => (
      <span className="block truncate">
        <Timestamp value={scan.timestamp} />
      </span>
    ),
  },
  {
    key: 'scan_mode',
    label: 'Mode',
    width: 'w-7/50',
    render: (scan) => SCAN_MODE_LABEL[scan.scan_mode],
  },
  {
    key: 'status',
    label: 'Status',
    width: 'w-7/50',
    render: statusCell,
  },
  {
    key: 'host_count',
    label: 'Machines',
    width: 'w-3/25',
    align: 'right',
    render: (scan) => countCell(scan, scan.host_count),
  },
  {
    key: 'finding_count',
    label: 'Vulnerabilities',
    width: 'w-4/25',
    align: 'right',
    render: (scan) =>
      countCell(scan, scan.finding_count === 0 ? 'None' : scan.finding_count),
  },
  {
    key: 'highest_severity',
    label: 'Highest severity',
    width: 'w-1/5',
    render: highestCell,
  },
]
