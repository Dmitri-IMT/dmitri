import DataTable from '@/components/DataTable'
import FindingPanel from '@/pages/scans/FindingPanel'
import {
  hostFindingColumns,
  scanFindingColumns,
} from '@/pages/scans/findingColumns'
import { bySeverityDesc } from '@/lib/severity'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']
type ScanHostView = components['schemas']['ScanHostView']

type FindingsTableProps = {
  findings: FindingRecord[]
  variant: 'scan' | 'host'
  hosts?: ScanHostView[]
  isPending?: boolean
  testId: string
  caption: string
  openFindingId: string | null
  onOpenFindingChange: (id: string | null) => void
}

function FindingsTable({
  findings,
  variant,
  hosts,
  isPending = false,
  testId,
  caption,
  openFindingId,
  onOpenFindingChange,
}: FindingsTableProps) {
  const columns =
    variant === 'scan' ? scanFindingColumns(hosts ?? []) : hostFindingColumns()

  const table = {
    columns,
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
