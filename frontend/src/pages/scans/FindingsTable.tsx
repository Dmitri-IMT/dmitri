import DataTable, { type DataTableColumn } from '@/components/DataTable'
import SeverityBadge from '@/components/SeverityBadge'
import FindingPanel from '@/pages/scans/FindingPanel'
import { bySeverityDesc } from '@/lib/severity'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']
type ScanHostView = components['schemas']['ScanHostView']

function dash() {
  return <span className="text-muted-foreground">—</span>
}

function hostLabel(
  finding: FindingRecord,
  hostsById: Map<string, ScanHostView>,
): string {
  const host = finding.host_id ? hostsById.get(finding.host_id) : undefined
  if (host && host.hostname !== '') return host.hostname
  if (host) return host.ip
  return finding.host_ip ?? ''
}

function FindingsTable({
  findings,
  hosts,
  openFindingId,
  onOpenFindingChange,
}: {
  findings: FindingRecord[]
  hosts: ScanHostView[]
  openFindingId: string | null
  onOpenFindingChange: (id: string | null) => void
}) {
  if (findings.length === 0) {
    return (
      <p data-testid="scan-no-findings" className="text-body-md">
        No findings. Every host in this scan came back clean.
      </p>
    )
  }

  const hostsById = new Map(hosts.map((host) => [host.host_id, host]))
  const rows = [...findings].sort(bySeverityDesc)

  const columns: DataTableColumn<FindingRecord>[] = [
    {
      key: 'title',
      label: 'Finding',
      width: 'w-2/5',
      render: (finding) => (
        <span className="block truncate" title={finding.title}>
          {finding.title}
        </span>
      ),
    },
    {
      key: 'host',
      label: 'Host',
      width: 'w-1/5',
      render: (finding) => {
        const label = hostLabel(finding, hostsById)
        if (label === '') return dash()
        return (
          <span className="block truncate" title={label}>
            {label}
          </span>
        )
      },
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
      width: 'w-3/20',
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
      testId="findings-table"
      caption="Findings for this scan"
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

export default FindingsTable
