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

function ScanPartialWarning({ scan }: { scan: ScanDetailResponse }) {
  const { t } = useI18n()
  if (scan.metadata?.partial_result !== true) return null

  const coverage = scan.targeted_coverage ?? []
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
                      {[
                        [t('scans.coverageCompletedLabel'), item.completed],
                        [t('scans.coverageFailed'), item.failed],
                        [t('scans.coverageTimedOut'), item.timed_out],
                        [t('scans.coverageSkipped'), item.skipped],
                      ].map(([label, value]) => (
                        <div key={label}>
                          <dt className="text-muted-foreground">{label}</dt>
                          <dd>{value}</dd>
                        </div>
                      ))}
                    </dl>
                    {item.gaps.length > 0 && (
                      <p className="text-body-sm text-muted-foreground">
                        {t('scans.coverageGaps')}:{' '}
                        {item.gaps
                          .map(({ reason, count }) => {
                            const messageKey = GAP_REASON_MESSAGES[reason]
                            const reasonLabel = messageKey
                              ? t(messageKey)
                              : reason.replaceAll('_', ' ')
                            return `${reasonLabel} (${count})`
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
