import { TriangleAlert } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import useI18n from '@/i18n/useI18n'
import type { MessageKey } from '@/i18n/messages/catalog.types'
import type { components } from '@/types/openapi'

type ScanDetailResponse = components['schemas']['ScanDetailResponse']
type TargetedCoverage = {
  tool: string
  completed: number
  failed: number
  timedOut: number
  skipped: number
  gaps: string[]
}

const GAP_REASON_MESSAGES: Record<string, MessageKey> = {
  tool_unavailable: 'scans.gapReasonToolUnavailable',
  dependency_unavailable: 'scans.gapReasonDependencyUnavailable',
  incompatible_tool: 'scans.gapReasonIncompatibleTool',
  wordlist_unavailable: 'scans.gapReasonWordlistUnavailable',
  policy_unavailable: 'scans.gapReasonPolicyUnavailable',
  plan_limit: 'scans.gapReasonPlanLimit',
  stage_budget: 'scans.gapReasonStageBudget',
  output_limit: 'scans.gapReasonOutputLimit',
  issue_limit: 'scans.gapReasonIssueLimit',
  validation_limit: 'scans.gapReasonValidationLimit',
  baseline_unavailable: 'scans.gapReasonBaselineUnavailable',
  malformed_report: 'scans.gapReasonMalformedReport',
  wrong_target: 'scans.gapReasonWrongTarget',
  spawn_error: 'scans.gapReasonSpawnError',
  execution_error: 'scans.gapReasonExecutionError',
  unit_timeout: 'scans.gapReasonUnitTimeout',
}

function targetedCoverage(value: unknown): TargetedCoverage[] {
  if (typeof value !== 'string') return []

  return value
    .split(';')
    .filter(Boolean)
    .map((entry) => {
      const separator = entry.indexOf(':')
      const tool = entry.slice(0, separator)
      const detail = entry.slice(separator + 1)
      const [counts = '', gaps] = detail.split(',gaps=', 2)
      const values: Record<string, number> = {
        c: 0,
        f: 0,
        t: 0,
        s: 0,
      }
      for (const item of counts.split(',')) {
        const [key, count] = item.split('=', 2)
        if (key in values && count !== undefined) {
          values[key] = Number(count) || 0
        }
      }
      return {
        tool,
        completed: values.c,
        failed: values.f,
        timedOut: values.t,
        skipped: values.s,
        gaps: gaps
          ? gaps.split('|').map((gap) => {
              const [reason, count] = gap.split(':', 2)
              return count === undefined ? reason : `${reason}:${count}`
            })
          : [],
      }
    })
}

function ScanPartialWarning({ scan }: { scan: ScanDetailResponse }) {
  const { t } = useI18n()
  if (scan.metadata?.partial_result !== true) return null

  const coverage = targetedCoverage(scan.metadata.targeted_coverage)
  const targetedCounts = [
    ['targeted_units_planned', t('scans.coveragePlanned')],
    ['targeted_units_completed', t('scans.coverageCompletedLabel')],
    ['targeted_units_failed', t('scans.coverageFailed')],
    ['targeted_units_timed_out', t('scans.coverageTimedOut')],
    ['targeted_units_skipped', t('scans.coverageSkipped')],
  ]
    .map(([key, label]) => {
      const value = scan.metadata?.[key]
      return typeof value === 'number' ? `${value} ${label}` : null
    })
    .filter((value): value is string => value !== null)

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          variant="link"
          data-testid="scan-partial-warning-trigger"
          className="h-auto shrink-0 gap-2 p-0 text-primary"
        >
          <TriangleAlert aria-hidden="true" className="size-4 text-amber-600" />
          {t('scans.partialWarningTitle')}
        </Button>
      </DialogTrigger>
      <DialogContent
        data-testid="scan-partial-notice"
        className="max-h-screen overflow-y-auto sm:max-w-2xl"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <TriangleAlert
              aria-hidden="true"
              className="size-4 text-amber-600"
            />
            {t('scans.partialWarningTitle')}
          </DialogTitle>
          <DialogDescription>{t('scans.partialResults')}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4 text-body-md">
          {targetedCounts.length > 0 && (
            <p>
              {t('scans.targetedChecks')}: {targetedCounts.join(', ')}.
            </p>
          )}
          {coverage.length > 0 && (
            <section className="flex flex-col gap-3">
              <h3 className="text-title-xs">
                {t('scans.targetedToolCoverage')}
              </h3>
              <ul className="grid gap-3 sm:grid-cols-2">
                {coverage.map((item) => (
                  <li
                    key={item.tool}
                    className="flex flex-col gap-3 rounded-md border border-border p-3"
                  >
                    <h4 className="font-medium">{item.tool}</h4>
                    <dl className="grid grid-cols-2 gap-3 text-body-sm">
                      <div>
                        <dt className="text-muted-foreground">
                          {t('scans.coverageCompletedLabel')}
                        </dt>
                        <dd>{item.completed}</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">
                          {t('scans.coverageFailed')}
                        </dt>
                        <dd>{item.failed}</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">
                          {t('scans.coverageTimedOut')}
                        </dt>
                        <dd>{item.timedOut}</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">
                          {t('scans.coverageSkipped')}
                        </dt>
                        <dd>{item.skipped}</dd>
                      </div>
                    </dl>
                    {item.gaps.length > 0 && (
                      <p className="text-body-sm text-muted-foreground">
                        {t('scans.coverageGaps')}:{' '}
                        {item.gaps
                          .map((gap) => {
                            const separator = gap.lastIndexOf(':')
                            const reason = gap.slice(0, separator)
                            const count = gap.slice(separator + 1)
                            const messageKey = GAP_REASON_MESSAGES[reason]
                            const reasonLabel = messageKey
                              ? t(messageKey)
                              : reason.replaceAll('_', ' ')
                            return separator === -1
                              ? gap.replaceAll('_', ' ')
                              : `${reasonLabel} (${count})`
                          })
                          .join(', ')}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default ScanPartialWarning
