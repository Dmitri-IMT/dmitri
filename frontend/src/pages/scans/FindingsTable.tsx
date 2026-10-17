import DataTable from '@/components/DataTable'
import FindingPanel from '@/pages/scans/FindingPanel'
import useI18n from '@/i18n/useI18n'
import {
  hostFindingColumns,
  scanFindingColumns,
} from '@/pages/scans/findingColumns'
import { bySeverityDesc } from '@/lib/severity'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']

type FindingsTableProps = {
  findings: FindingRecord[]
  isPending?: boolean
  testId: string
  caption: string
  sourceToolLabel?: string
  openFindingId: string | null
  onOpenFindingChange: (id: string | null) => void
  variant: 'scan' | 'host'
}

function FindingsTable({
  findings,
  isPending = false,
  testId,
  caption,
  sourceToolLabel,
  openFindingId,
  onOpenFindingChange,
  variant,
}: FindingsTableProps) {
  const { t } = useI18n()
  const labels = {
    vulnerability: t('common.vulnerability'),
    severity: t('common.severityLabel'),
    machine: t('common.machine'),
    port: t('common.port'),
    cve: t('common.cve'),
    firstSeen: t('common.firstSeen'),
  }
  const columns =
    variant === 'scan'
      ? scanFindingColumns(sourceToolLabel, labels)
      : hostFindingColumns(labels)

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
        label: (finding) =>
          t('common.showFindingDetails', { title: finding.title }),
        openRowId: openFindingId,
        onOpenRowChange: onOpenFindingChange,
      }}
    />
  )
}

export default FindingsTable
