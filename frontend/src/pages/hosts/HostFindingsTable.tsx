import DataTable, { type DataTableColumn } from '@/components/DataTable'
import SeverityBadge from '@/components/SeverityBadge'
import FindingPanel from '@/pages/scans/FindingPanel'
import { bySeverityDesc } from '@/lib/severity'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']

function dash() {
  return <span className="text-muted-foreground">—</span>
}

function HostFindingsTable({
  findings,
  openFindingId,
  onOpenFindingChange,
}: {
  findings: FindingRecord[]
  openFindingId: string | null
  onOpenFindingChange: (id: string | null) => void
}) {
  if (findings.length === 0) {
    return (
      <p data-testid="host-no-findings" className="text-body-md">
        No findings on this host.
      </p>
    )
  }

  const rows = [...findings].sort(bySeverityDesc)

  const columns: DataTableColumn<FindingRecord>[] = [
    {
      key: 'title',
      label: 'Finding',
      width: 'w-1/2',
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
      align: 'right',
      render: (finding) =>
        finding.port == null ? (
          dash()
        ) : (
          <span className="block text-right tabular-nums">{finding.port}</span>
        ),
    },
    {
      key: 'cve',
      label: 'CVE',
      width: 'w-1/4',
      render: (finding) =>
        finding.cve_id ? (
          <span className="block truncate" title={finding.cve_id}>
            {finding.cve_id}
          </span>
        ) : (
          dash()
        ),
    },
    {
      key: 'severity',
      label: 'Severity',
      width: 'w-3/20',
      render: (finding) => <SeverityBadge severity={finding.severity} />,
    },
  ]

  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowId={(finding) => finding.finding_id}
      testId="host-findings-table"
      caption="Findings on this host"
      rowAction={{
        kind: 'expand',
        panel: (finding) => <FindingPanel finding={finding} />,
        label: (finding) => `Show details for ${finding.title}`,
        openRowId: openFindingId,
        onOpenRowChange: onOpenFindingChange,
      }}
    />
  )
}

export default HostFindingsTable
