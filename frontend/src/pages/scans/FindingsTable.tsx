import CellLink from '@/components/CellLink'
import DataTable, { type DataTableColumn } from '@/components/DataTable'
import EmptyMark from '@/components/EmptyMark'
import FindingPanel from '@/pages/scans/FindingPanel'
import { findingColumns } from '@/pages/scans/findingColumns'
import { bySeverityDesc } from '@/lib/severity'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']
type ScanHostView = components['schemas']['ScanHostView']

function machineLabel(
  finding: FindingRecord,
  hostsById: Map<string, ScanHostView>,
): string {
  const host = finding.host_id ? hostsById.get(finding.host_id) : undefined
  if (host && host.hostname !== '') return host.hostname
  if (host) return host.ip
  return finding.host_ip ?? ''
}

function machineColumnFor(
  hosts: ScanHostView[],
): DataTableColumn<FindingRecord> {
  const hostsById = new Map(hosts.map((host) => [host.host_id, host]))

  return {
    key: 'host',
    label: 'Machine',
    width: 'w-11/50',
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
  }
}

function FindingsTable({
  findings,
  hosts,
  isPending = false,
  testId,
  caption,
  openFindingId,
  onOpenFindingChange,
}: {
  findings: FindingRecord[]
  hosts?: ScanHostView[]
  isPending?: boolean
  testId: string
  caption: string
  openFindingId: string | null
  onOpenFindingChange: (id: string | null) => void
}) {
  const table = {
    columns: findingColumns(hosts && machineColumnFor(hosts)),
    rowId: (finding: FindingRecord) => finding.finding_id,
    testId,
    caption,
  }

  if (isPending) return <DataTable {...table} rows={[]} isPending />

  return (
    <DataTable
      {...table}
      rows={[...findings].sort(bySeverityDesc)}
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
