import type { ReactNode } from 'react'
import EmptyMark from '@/components/EmptyMark'
import type { DataTableColumn } from '@/components/DataTable'
import SeverityWord from '@/components/SeverityWord'
import {
  scanDurationCell,
  scanModeCell,
  scanWhenCell,
} from '@/pages/scans/scanCells'
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
  return <span className="block tabular-nums">{value}</span>
}

function highestCell(scan: ScanSummary): ReactNode {
  if (hidesCounts(scan.status)) return <EmptyMark />
  return <SeverityWord severity={scan.highest_severity} />
}

function boxCell(scan: ScanSummary): ReactNode {
  return (
    <span data-testid={`scans-box-${scan.scan_id}`}>
      {scan.box_name ?? <EmptyMark />}
    </span>
  )
}

export const scanListColumns: DataTableColumn<ScanSummary>[] = [
  {
    key: 'timestamp',
    label: 'When',
    width: 'w-9/50',
    render: scanWhenCell,
  },
  {
    key: 'box_name',
    label: 'Box',
    width: 'w-7/50',
    render: boxCell,
  },
  {
    key: 'scan_mode',
    label: 'Mode',
    width: 'w-1/10',
    render: scanModeCell,
  },
  {
    key: 'status',
    label: 'Status',
    width: 'w-1/10',
    render: statusCell,
  },
  {
    key: 'duration',
    label: 'Duration',
    width: 'w-1/12',
    align: 'right',
    render: (scan) => scanDurationCell(scan, `scans-duration-${scan.scan_id}`),
  },
  {
    key: 'host_count',
    label: 'Machines',
    width: 'w-1/10',
    align: 'right',
    render: (scan) => countCell(scan, scan.host_count),
  },
  {
    key: 'finding_count',
    label: 'Vulnerabilities',
    width: 'w-3/25',
    align: 'right',
    render: (scan) =>
      countCell(scan, scan.finding_count === 0 ? 'None' : scan.finding_count),
  },
  {
    key: 'highest_severity',
    label: 'Highest severity',
    width: 'w-9/50',
    render: highestCell,
  },
]
