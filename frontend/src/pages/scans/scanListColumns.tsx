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
import type { MessageKey } from '@/i18n/messages'

type ScanSummary = components['schemas']['ScanSummary']

function statusCell(scan: ScanSummary): ReactNode {
  return (
    <span data-testid={`scans-status-${scan.scan_id}`}>
      {scanStatusLabel(scan.status, scan.terminated_by)}
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

export function scanListColumns(
  t: (key: MessageKey, variables?: Record<string, string | number>) => string,
): DataTableColumn<ScanSummary>[] {
  return [
    {
      key: 'timestamp',
      label: t('common.when'),
      width: 'w-9/50',
      render: scanWhenCell,
    },
    {
      key: 'box_name',
      label: t('common.box'),
      width: 'w-7/50',
      render: boxCell,
    },
    {
      key: 'scan_mode',
      label: t('common.mode'),
      width: 'w-1/10',
      render: scanModeCell,
    },
    {
      key: 'status',
      label: t('common.status'),
      width: 'w-1/10',
      render: statusCell,
    },
    {
      key: 'duration',
      label: t('common.duration'),
      width: 'w-1/12',
      render: (scan) =>
        scanDurationCell(scan, `scans-duration-${scan.scan_id}`),
    },
    {
      key: 'host_count',
      label: t('common.machines'),
      width: 'w-1/10',
      render: (scan) => countCell(scan, scan.host_count),
    },
    {
      key: 'finding_count',
      label: t('common.vulnerabilities'),
      width: 'w-3/25',
      render: (scan) =>
        countCell(
          scan,
          scan.finding_count === 0 ? t('common.none') : scan.finding_count,
        ),
    },
    {
      key: 'highest_severity',
      label: t('common.highestSeverity'),
      width: 'w-9/50',
      render: highestCell,
    },
  ]
}
