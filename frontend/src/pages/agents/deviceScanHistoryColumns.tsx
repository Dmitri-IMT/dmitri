import type { DataTableColumn } from '@/components/DataTable'
import { scanStatusLabel } from '@/lib/scanStatus'
import {
  scanDurationCell,
  scanModeCell,
  scanWhenCell,
} from '@/pages/scans/scanCells'
import type { components } from '@/types/openapi'

type ScanSummary = components['schemas']['ScanSummary']

export const deviceScanHistoryColumns: DataTableColumn<ScanSummary>[] = [
  {
    key: 'timestamp',
    label: 'When',
    width: 'w-17/50',
    render: scanWhenCell,
  },
  {
    key: 'scan_mode',
    label: 'Mode',
    width: 'w-11/50',
    render: scanModeCell,
  },
  {
    key: 'status',
    label: 'Status',
    width: 'w-11/50',
    render: (scan) => scanStatusLabel(scan.status),
  },
  {
    key: 'duration',
    label: 'Duration',
    width: 'w-11/50',
    align: 'right',
    render: (scan) => scanDurationCell(scan),
  },
]
