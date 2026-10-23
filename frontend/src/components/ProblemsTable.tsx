import { useState } from 'react'
import { Link } from 'react-router'
import DataTable, { type DataTableColumn } from '@/components/DataTable'
import VulnerabilityView from '@/components/VulnerabilityView'
import RiskBreakdownHint from '@/components/RiskBreakdownHint'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import useScanAnalysis from '@/hooks/useScanAnalysis'
import useI18n from '@/i18n/useI18n'
import { machineName } from '@/lib/fixTask'
import type { components } from '@/types/openapi'

type Finding = components['schemas']['FindingRecord']

const MACHINE_NAME_LIMIT = 24

export default function ProblemsTable({
  findings,
  machine = false,
  openFindingId,
  onOpenFindingChange,
  testId = 'problems-table',
}: {
  findings: Finding[]
  machine?: boolean
  openFindingId: string | null
  onOpenFindingChange: (id: string | null) => void
  testId?: string
}) {
  const { t } = useI18n()
  const [filter, setFilter] = useState('all')
  const [showAll, setShowAll] = useState(false)
  const [sort, setSort] = useState<'asc' | 'desc'>('desc')
  const analysis = useScanAnalysis(findings[0]?.scan_id ?? '')
  const notes =
    analysis.data?.status === 'completed' ? analysis.data.analysis.findings : []
  const rows = findings
    .filter(
      (finding) =>
        finding.finding_id === openFindingId ||
        filter === 'all' ||
        finding.demonstrated,
    )
    .sort(
      (a, b) =>
        ((a.risk_score ?? -1) - (b.risk_score ?? -1)) *
        (sort === 'asc' ? 1 : -1),
    )
  const deepIndex = rows.findIndex(
    (finding) => finding.finding_id === openFindingId,
  )
  const visible = showAll ? rows : rows.slice(0, Math.max(5, deepIndex + 1))
  const columns: DataTableColumn<Finding, 'risk'>[] = [
    {
      key: 'problem',
      label: t('problems.problem'),
      width: '',
      render: (finding) => (
        <span
          className={
            finding.finding_id === openFindingId ? 'font-semibold' : ''
          }
        >
          {notes.find((note) => note.finding_id === finding.finding_id)
            ?.plain_title ?? finding.title}
        </span>
      ),
    },
    {
      key: 'level',
      label: t('problems.level'),
      width: 'w-25',
      render: (finding) => (
        <strong>{t('common.severity', { severity: finding.severity })}</strong>
      ),
    },
    {
      key: 'risk',
      label: t('finding.risk'),
      width: 'w-35',
      sortable: true,
      render: (finding) => (
        <span className="flex items-center gap-2">
          <strong data-testid={`problems-risk-${finding.finding_id}`}>
            {finding.risk_score == null ? '—' : Math.round(finding.risk_score)}
          </strong>
          <RiskBreakdownHint breakdown={finding.risk_breakdown} />
        </span>
      ),
    },
    ...(!machine
      ? [
          {
            key: 'machine',
            label: t('common.machine'),
            width: 'w-50',
            render: (finding: Finding) => {
              const name = machineName(finding) ?? '—'
              const label =
                name.length > MACHINE_NAME_LIMIT
                  ? `${name.slice(0, MACHINE_NAME_LIMIT - 3)}...`
                  : name
              return finding.host_id ? (
                <Button
                  asChild
                  variant="link"
                  className="h-auto min-w-0 max-w-full p-0 text-body-sm"
                >
                  <Link
                    to={`/network/${finding.host_id}`}
                    title={name}
                    aria-label={name}
                  >
                    <span className="min-w-0 truncate">{label}</span>
                  </Link>
                </Button>
              ) : (
                '—'
              )
            },
          },
        ]
      : []),
    {
      key: 'cve',
      label: 'CVE',
      width: 'w-42',
      render: (finding) => (
        <span className="font-mono text-caption-md text-ink-muted">
          {finding.cve_id ?? '—'}
        </span>
      ),
    },
    {
      key: 'details',
      label: t('finding.tech'),
      visuallyHiddenHeader: true,
      width: 'w-10',
      render: () => null,
    },
  ]
  return (
    <Card data-testid={machine ? 'machine-problems' : 'problems-card'}>
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <h2 className="text-title-sm">
          {t(machine ? 'problems.machine' : 'problems.all')} · {findings.length}
        </h2>
        <div className="flex items-center gap-3">
          <span className="text-body-sm text-ink-muted">
            {t('problems.filter')}
          </span>
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger
              aria-label={t('evidence.filter.label')}
              className="w-48"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('problems.all')}</SelectItem>
              <SelectItem value="confirmed">
                {t('problems.confirmed')}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <DataTable
          columns={columns}
          rows={visible}
          rowId={(finding) => finding.finding_id}
          testId={testId}
          caption={t(machine ? 'problems.machine' : 'problems.all')}
          sort={{
            by: 'risk',
            order: sort,
            onChange: () =>
              setSort((current) => (current === 'desc' ? 'asc' : 'desc')),
          }}
          empty={
            <p className="text-body-md">
              {findings.length === 0
                ? t('common.noVulnerabilitiesInScan')
                : t('evidence.filter.empty.confirmed')}
            </p>
          }
          rowAction={{
            kind: 'expand',
            togglePosition: 'last',
            openRowId: openFindingId,
            onOpenRowChange: onOpenFindingChange,
            label: (finding) =>
              t('common.showFindingDetails', { title: finding.title }),
            panel: (finding) => <VulnerabilityView finding={finding} />,
          }}
        />
        {visible.length < rows.length && (
          <Button
            variant="outline"
            className="self-start"
            data-testid="problems-show-more"
            onClick={() => setShowAll(true)}
          >
            {t('problems.more', { n: rows.length - visible.length })}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
