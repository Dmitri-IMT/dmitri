import CellLink from '@/components/CellLink'
import type { DataTableColumn } from '@/components/DataTable'
import EmptyMark from '@/components/EmptyMark'
import SeverityWord from '@/components/SeverityWord'
import Timestamp from '@/components/Timestamp'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']

function machineLabel(finding: FindingRecord): string {
  return finding.host_hostname || finding.host_ip || ''
}

export function scanFindingColumns(): DataTableColumn<FindingRecord>[] {
  return [
    {
      key: 'title',
      label: 'Vulnerability',
      width: 'w-2/5',
      render: (finding) => (
        <span className="block truncate" title={finding.title}>
          {finding.title}
        </span>
      ),
    },
    {
      key: 'host',
      label: 'Machine',
      width: 'w-9/50',
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
      key: 'port',
      label: 'Port',
      width: 'w-3/25',
      render: (finding) =>
        finding.port == null ? (
          <EmptyMark />
        ) : (
          <span className="block pr-3 tabular-nums">{finding.port}</span>
        ),
    },
    {
      key: 'cve',
      label: 'CVE',
      width: 'w-7/50',
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
      label: 'First seen',
      width: 'w-4/25',
      render: (finding) =>
        finding.first_seen_at ? (
          <Timestamp value={finding.first_seen_at} />
        ) : (
          <EmptyMark />
        ),
    },
  ]
}

export function hostFindingColumns(): DataTableColumn<FindingRecord>[] {
  return [
    {
      key: 'title',
      label: 'Vulnerability',
      width: 'w-2/5',
      render: (finding) => (
        <span className="block truncate" title={finding.title}>
          {finding.title}
        </span>
      ),
    },
    {
      key: 'port',
      label: 'Port',
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
      label: 'CVE',
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
      label: 'First seen',
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
      label: 'Severity',
      width: 'w-4/25',
      render: (finding) => <SeverityWord severity={finding.severity} />,
    },
  ]
}
