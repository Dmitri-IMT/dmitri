import DataTable, { type DataTableColumn } from '@/components/DataTable'
import FindingPanel from '@/pages/scans/FindingPanel'
import { findingColumns } from '@/pages/scans/findingColumns'
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

  const hostColumn: DataTableColumn<FindingRecord> = {
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
  }

  return (
    <DataTable
      columns={findingColumns(hostColumn)}
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
