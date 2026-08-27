import DataTable from '@/components/DataTable'
import FindingPanel from '@/pages/scans/FindingPanel'
import { findingColumns } from '@/pages/scans/findingColumns'
import { bySeverityDesc } from '@/lib/severity'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']

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

  return (
    <DataTable
      columns={findingColumns()}
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
