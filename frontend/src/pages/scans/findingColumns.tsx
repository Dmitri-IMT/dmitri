import CellLink from '@/components/CellLink'
import type { DataTableColumn } from '@/components/DataTable'
import EmptyMark from '@/components/EmptyMark'
import SeverityWord from '@/components/SeverityWord'
import Timestamp from '@/components/Timestamp'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']

type FindingColumnLabels = {
  vulnerability: string
  severity: string
  machine: string
  port: string
  cve: string
  firstSeen: string
  status: string
  confirmed: string
  unverified: string
}

const ENGLISH_LABELS: FindingColumnLabels = {
  vulnerability: 'Vulnerability',
  severity: 'Severity',
  machine: 'Machine',
  port: 'Port',
  cve: 'CVE',
  firstSeen: 'First seen',
  status: 'Status',
  confirmed: 'Confirmed',
  unverified: 'Unverified',
}

function machineLabel(finding: FindingRecord): string {
  return finding.host_hostname || finding.host_ip || ''
}

export function scanFindingColumns(
  sourceToolLabel?: string,
  labels: FindingColumnLabels = ENGLISH_LABELS,
): DataTableColumn<FindingRecord>[] {
  return [
    {
      key: 'title',
      label: labels.vulnerability,
      width: 'w-1/2',
      render: (finding) => (
        <span className="block min-w-0" title={finding.title}>
          <span className="block truncate">{finding.title}</span>
          {sourceToolLabel && finding.source_script && (
            <span className="block truncate text-caption-sm text-muted-foreground">
              {sourceToolLabel}: {finding.source_script}
            </span>
          )}
        </span>
      ),
    },
    {
      key: 'host',
      label: labels.machine,
      width: 'w-1/5',
      render: (finding) => {
        const label = machineLabel(finding)
        if (label === '') return <EmptyMark />
        const name = (
          <span className="block truncate" title={label}>
            {label}
          </span>
        )
        return finding.host_id ? (
          <CellLink to={`/network/${finding.host_id}`}>{name}</CellLink>
        ) : (
          name
        )
      },
    },
    {
      key: 'status',
      label: labels.status,
      width: 'w-3/20',
      render: (finding) =>
        finding.demonstrated ? (
          <span>{labels.confirmed}</span>
        ) : (
          <span className="text-muted-foreground">{labels.unverified}</span>
        ),
    },
    {
      key: 'severity',
      label: labels.severity,
      width: 'w-3/20',
      render: (finding) => <SeverityWord severity={finding.severity} />,
    },
  ]
}

export function hostFindingColumns(
  labels: FindingColumnLabels = ENGLISH_LABELS,
): DataTableColumn<FindingRecord>[] {
  return [
    {
      key: 'title',
      label: labels.vulnerability,
      width: 'w-2/5',
      render: (finding) => (
        <span className="block truncate" title={finding.title}>
          {finding.title}
        </span>
      ),
    },
    {
      key: 'port',
      label: labels.port,
      width: 'w-1/10',
      render: (finding) =>
        finding.port == null ? (
          <EmptyMark />
        ) : (
          <span className="block pr-3 tabular-nums">{finding.port}</span>
        ),
    },
    {
      key: 'cve',
      label: labels.cve,
      width: 'w-9/50',
      render: (finding) =>
        finding.cve_id ? (
          <span className="block truncate font-mono" title={finding.cve_id}>
            {finding.cve_id}
          </span>
        ) : (
          <EmptyMark />
        ),
    },
    {
      key: 'first_seen',
      label: labels.firstSeen,
      width: 'w-4/25',
      render: (finding) =>
        finding.first_seen_at ? (
          <Timestamp value={finding.first_seen_at} />
        ) : (
          <EmptyMark />
        ),
    },
    {
      key: 'severity',
      label: labels.severity,
      width: 'w-4/25',
      render: (finding) => <SeverityWord severity={finding.severity} />,
    },
  ]
}
