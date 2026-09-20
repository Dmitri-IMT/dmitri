import CellLink from '@/components/CellLink'
import DataTable, { type DataTableColumn } from '@/components/DataTable'
import EmptyMark from '@/components/EmptyMark'
import Pagination from '@/components/Pagination'
import SeverityWord from '@/components/SeverityWord'
import { HOME_ATTENTION_PER_PAGE } from '@/api/home'
import type { components } from '@/types/openapi'
import useI18n from '@/i18n/useI18n'

type FindingRecord = components['schemas']['FindingRecord']

function attentionMachineText(finding: FindingRecord): string | null {
  if (finding.host_hostname) return finding.host_hostname
  if (finding.host_ip) return finding.host_ip
  return null
}

function attentionColumns(t: ReturnType<typeof useI18n>['t']) {
  const columns: DataTableColumn<FindingRecord>[] = [
    {
      key: 'title',
      label: t('home.vulnerability'),
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
      label: t('home.machine'),
      width: 'w-17/50',
      render: (finding) => {
        const label = attentionMachineText(finding)
        if (label === null) return <EmptyMark />
        const machine = finding.host_hostname ? (
          <span className="block truncate" title={label}>
            {label}
          </span>
        ) : (
          <span className="block truncate font-mono" title={label}>
            {label}
          </span>
        )
        return finding.host_id ? (
          <CellLink to={`/network/${finding.host_id}`}>{machine}</CellLink>
        ) : (
          machine
        )
      },
    },
    {
      key: 'severity',
      label: t('home.severity'),
      width: 'w-1/5',
      render: (finding) => <SeverityWord severity={finding.severity} />,
    },
  ]
  return columns
}

type AttentionTableProps = {
  findings: FindingRecord[]
  total: number
  page: number
  onPageChange: (page: number) => void
}

function AttentionTable({
  findings,
  total,
  page,
  onPageChange,
}: AttentionTableProps) {
  const { t } = useI18n()
  const columns = attentionColumns(t)
  return (
    <>
      {findings.length > 0 && (
        <DataTable
          columns={columns}
          rows={findings}
          rowId={(finding) => finding.finding_id}
          testId="home-table"
          caption={t('home.attentionCaption')}
          rowAction={{
            kind: 'link',
            to: (finding) =>
              `/scans/${finding.scan_id}?finding=${finding.finding_id}`,
            label: (finding) =>
              `${finding.title} on ${attentionMachineText(finding) ?? 'unknown machine'}`,
          }}
        />
      )}
      <Pagination
        page={page}
        perPage={HOME_ATTENTION_PER_PAGE}
        total={total}
        onPageChange={onPageChange}
        testId="home-attention"
        label={t('home.attentionPages')}
      />
    </>
  )
}

export default AttentionTable
