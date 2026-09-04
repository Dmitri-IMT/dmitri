import type { DataTableColumn } from '@/components/DataTable'
import EmptyMark from '@/components/EmptyMark'
import SeverityWord from '@/components/SeverityWord'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']

export function findingColumns(
  machineColumn?: DataTableColumn<FindingRecord>,
): DataTableColumn<FindingRecord>[] {
  return [
    {
      key: 'title',
      label: 'Vulnerability',
      width: machineColumn ? 'w-2/5' : 'w-13/25',
      render: (finding) => (
        <span className="block truncate" title={finding.title}>
          {finding.title}
        </span>
      ),
    },
    ...(machineColumn ? [machineColumn] : []),
    {
      key: 'port',
      label: 'Port',
      width: 'w-3/25',
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
      width: machineColumn ? 'w-13/50' : 'w-1/5',
      render: (finding) =>
        finding.cve_id ? (
          <span className="block truncate font-mono" title={finding.cve_id}>
            {finding.cve_id}
          </span>
        ) : (
          <EmptyMark />
        ),
    },
    ...(machineColumn
      ? []
      : [
          {
            key: 'severity',
            label: 'Severity',
            width: 'w-4/25',
            render: (finding: FindingRecord) => (
              <SeverityWord severity={finding.severity} />
            ),
          },
        ]),
  ]
}
