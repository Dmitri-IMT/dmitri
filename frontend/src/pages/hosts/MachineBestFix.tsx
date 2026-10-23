import { Link } from 'react-router'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import FixTaskSteps from '@/components/FixTaskSteps'
import WaitingState from '@/components/WaitingState'
import useScanAnalysis from '@/hooks/useScanAnalysis'
import useI18n from '@/i18n/useI18n'
import type { components } from '@/types/openapi'

export default function MachineBestFix({
  scanId,
  findings,
}: {
  scanId: string
  findings: components['schemas']['FindingRecord'][]
}) {
  const { t } = useI18n()
  const query = useScanAnalysis(scanId)
  const ids = new Set(findings.map((finding) => finding.finding_id))
  const overlap = (task: components['schemas']['AIFixTask']) =>
    task.finding_ids.filter((id) => ids.has(id)).length
  const task =
    query.data?.status === 'completed'
      ? [...query.data.analysis.tasks]
          .filter((task) => overlap(task) > 0)
          .sort((a, b) => overlap(b) - overlap(a) || a.rank - b.rank)[0]
      : undefined
  const waiting =
    query.data?.status === 'pending' || query.data?.status === 'processing'
      ? query.data
      : null
  const scanner = [...findings].sort(
    (a, b) => (b.risk_score ?? -1) - (a.risk_score ?? -1),
  )[0]
  return (
    <Card data-testid="machine-best-fix">
      <CardHeader>
        <h2 className="text-title-sm">{t('machine.best')}</h2>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {findings.length === 0 ? (
          <>
            <p className="text-body-md">{t('machine.none')}</p>
            <p className="text-body-sm text-ink-muted">{t('todo.notProof')}</p>
          </>
        ) : task ? (
          <>
            <p className="text-body-sm text-ink-muted">
              {t('machine.fixes', { k: overlap(task), n: findings.length })}
            </p>
            <FixTaskSteps task={task} />
            <Button
              asChild
              variant="link"
              className="h-auto self-start p-0 text-body-sm"
            >
              <Link to={`/scans/${scanId}#todo-task-${task.rank}`}>
                {t('machine.task', { k: task.rank })}
              </Link>
            </Button>
          </>
        ) : waiting ? (
          <>
            <WaitingState
              size="small"
              stage={t('finding.waiting')}
              detail={t('ai.waiting.scanDetail')}
              startedAt={Date.parse(
                'created_at' in waiting
                  ? waiting.created_at
                  : new Date().toISOString(),
              )}
            />
            <p className="text-body-sm text-ink-muted">
              {t('finding.meanwhile', { text: scanner.recommendation })}
            </p>
          </>
        ) : (
          <>
            <p className="text-body-md">{scanner.recommendation}</p>
            <p className="text-caption-md text-ink-muted">
              {t('finding.scanner')}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}
