import CellLink from '@/components/CellLink'
import DataTable, { type DataTableColumn } from '@/components/DataTable'
import EmptyMark from '@/components/EmptyMark'
import SeverityWord from '@/components/SeverityWord'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']

const columns: DataTableColumn<FindingRecord>[] = [
  {
    key: 'title',
    label: 'Vulnerability',
    width: 'w-23/50',
    render: (finding) => (
      <>
        <span className="block truncate" title={finding.title}>
          {finding.title}
        </span>
        {finding.cve_id && (
          <span
            className="block truncate font-mono text-body-sm text-muted-foreground"
            title={finding.cve_id}
          >
            {finding.cve_id}
          </span>
        )}
      </>
    ),
  },
  {
    key: 'machine',
    label: 'Machine',
    width: 'w-17/50',
    render: (finding) => {
      if (!finding.host_ip) return <EmptyMark />
      const address = (
        <span className="block truncate font-mono" title={finding.host_ip}>
          {finding.host_ip}
        </span>
      )
      return finding.host_id ? (
        <CellLink to={`/network/${finding.host_id}`}>{address}</CellLink>
      ) : (
        address
      )
    },
  },
  {
    key: 'severity',
    label: 'Severity',
    width: 'w-1/5',
    render: (finding) => <SeverityWord severity={finding.severity} />,
  },
]

function AttentionTable({ findings }: { findings: FindingRecord[] }) {
  if (findings.length === 0) {
    return null
  }

  return (
    <DataTable
      columns={columns}
      rows={findings}
      rowId={(finding) => finding.finding_id}
      testId="home-table"
      caption="Vulnerabilities needing your attention"
      rowAction={{
        kind: 'link',
        to: (finding) =>
          `/scans/${finding.scan_id}?finding=${finding.finding_id}`,
        label: (finding) =>
          `${finding.title} on ${finding.host_ip ?? 'unknown machine'}`,
      }}
    />
  )
}

export default AttentionTable
