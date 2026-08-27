import type { DataTableColumn } from '@/components/DataTable'
import EmptyMark from '@/components/EmptyMark'
import SeverityBadge from '@/components/SeverityBadge'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']


export function findingColumns(
  hostColumn?: DataTableColumn<FindingRecord>,
): DataTableColumn<FindingRecord>[] {
  const wide = hostColumn === undefined

  return [
    {
      key: 'title',
      label: 'Finding',
      width: wide ? 'w-1/2' : 'w-2/5',
      render: (finding) => (
        <span className="block truncate" title={finding.title}>
          {finding.title}
        </span>
      ),
    },
    ...(hostColumn ? [hostColumn] : []),
    {
      key: 'port',
      label: 'Port',
      width: 'w-1/10',
      align: 'right',
      render: (finding) =>
        finding.port == null ? (
          <EmptyMark />
        ) : (
          <span className="block text-right tabular-nums">{finding.port}</span>
        ),
    },
    {
      key: 'cve',
      label: 'CVE',
      width: wide ? 'w-1/4' : 'w-3/20',
      render: (finding) =>
        finding.cve_id ? (
          <span className="block truncate" title={finding.cve_id}>
            {finding.cve_id}
          </span>
        ) : (
          <EmptyMark />
        ),
    },
    {
      key: 'severity',
      label: 'Severity',
      width: 'w-3/20',
      render: (finding) => <SeverityBadge severity={finding.severity} />,
    },
  ]
}
