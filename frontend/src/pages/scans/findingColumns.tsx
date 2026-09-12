import CellLink from '@/components/CellLink'
import type { DataTableColumn } from '@/components/DataTable'
import EmptyMark from '@/components/EmptyMark'
import SeverityWord from '@/components/SeverityWord'
import Timestamp from '@/components/Timestamp'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']
type ScanHostView = components['schemas']['ScanHostView']

function machineLabel(
  finding: FindingRecord,
  hostsById: Map<string, ScanHostView>,
): string {
  if (finding.host_hostname) return finding.host_hostname
  const host = finding.host_id ? hostsById.get(finding.host_id) : undefined
  if (host && host.hostname !== '') return host.hostname
  if (host) return host.ip
  return finding.host_ip ?? ''
}

export function scanFindingColumns(
  hosts: ScanHostView[],
): DataTableColumn<FindingRecord>[] {
  const hostsById = new Map(hosts.map((host) => [host.host_id, host]))

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
        const label = machineLabel(finding, hostsById)
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
      align: 'right',
      render: (finding) =>
        finding.port == null ? (
          <EmptyMark />
        ) : (
          <span className="block tabular-nums">{finding.port}</span>
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
          <span className="block tabular-nums">{finding.port}</span>
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
