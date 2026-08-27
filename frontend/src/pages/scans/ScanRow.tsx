import type { ReactNode } from 'react'
import type { DataTableColumn } from '@/components/DataTable'
import SeverityBadge from '@/components/SeverityBadge'
import StatusPill from '@/components/StatusPill'
import Timestamp from '@/components/Timestamp'
import { hidesCounts, scanStatusPill } from '@/lib/scanStatus'
import type { components } from '@/types/openapi'

type ScanSummary = components['schemas']['ScanSummary']

function dash() {
  return <span className="text-muted-foreground">—</span>
}

function statusCell(scan: ScanSummary): ReactNode {
  const pill = scanStatusPill(scan.status)
  return (
    <span data-testid={`scans-status-${scan.scan_id}`}>
      <StatusPill tone={pill.tone} label={pill.label} />
    </span>
  )
}

function hostsCell(scan: ScanSummary): ReactNode {
  if (hidesCounts(scan.status)) return dash()
  return scan.host_count
}

function findingsCell(scan: ScanSummary): ReactNode {
  if (hidesCounts(scan.status)) return dash()
  if (scan.finding_count === 0) return 'None'
  return scan.finding_count
}

function highestCell(scan: ScanSummary): ReactNode {
  if (hidesCounts(scan.status) || scan.highest_severity == null) {
    return dash()
  }
  return <SeverityBadge severity={scan.highest_severity} />
}

export const scanListColumns: DataTableColumn<ScanSummary>[] = [
  {
    key: 'timestamp',
    label: 'When',
    width: 'w-1/4',
    render: (scan) => <Timestamp value={scan.timestamp} />,
  },
  {
    key: 'scan_mode',
    label: 'Mode',
    width: 'w-1/8',
    render: (scan) => scan.scan_mode,
  },
  {
    key: 'status',
    label: 'Status',
    width: 'w-1/8',
    render: statusCell,
  },
  {
    key: 'host_count',
    label: 'Hosts',
    width: 'w-1/8',
    render: hostsCell,
  },
  {
    key: 'finding_count',
    label: 'Findings',
    width: 'w-1/8',
    render: findingsCell,
  },
  {
    key: 'highest_severity',
    label: 'Highest severity',
    width: 'w-1/4',
    render: highestCell,
  },
]
