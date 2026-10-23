import useI18n from '@/i18n/useI18n'
import { methodLabel, confidenceLabel } from '@/lib/evidencePresentation'
import type { components } from '@/types/openapi'

type EvidenceSummary = components['schemas']['FindingEvidenceSummary']
type EvidenceObservation =
  components['schemas']['FindingEvidenceObservationPayload']

function CountRow({ label, count }: { label: string; count: number }) {
  return (
    <div className="flex gap-4">
      <dt className="w-1/4 shrink-0 text-caption-md text-muted-foreground">
        {label}
      </dt>
      <dd className="text-body-md tabular-nums">{count}</dd>
    </div>
  )
}

function ValueRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-4">
      <dt className="w-1/4 shrink-0 text-caption-md text-muted-foreground">
        {label}
      </dt>
      <dd className="text-body-md">{value}</dd>
    </div>
  )
}

export function EvidenceSummary({
  summary,
  scope,
}: {
  summary: EvidenceSummary | null | undefined
  scope: EvidenceSummary['scope']
}) {
  const { t } = useI18n()
  if (!summary || summary.scope !== scope) return null
  const methods = [
    ['version_correlation', summary.by_method.version_correlation],
    ['configuration_observation', summary.by_method.configuration_observation],
    ['specific_check', summary.by_method.specific_check],
    ['textual_reference', summary.by_method.textual_reference],
    ['unknown', summary.by_method.unknown],
  ] as const
  const confidences = [
    ['tentative', summary.by_confidence.tentative],
    ['probable', summary.by_confidence.probable],
    ['confirmed', summary.by_confidence.confirmed],
    ['unknown', summary.by_confidence.unknown],
  ] as const

  return (
    <section
      data-testid={
        scope === 'scan' ? 'evidence-summary-scan' : 'evidence-summary-filtered'
      }
      className="flex flex-col gap-4"
      aria-labelledby={`evidence-summary-title-${scope}`}
    >
      <h3 id={`evidence-summary-title-${scope}`} className="text-title-xs">
        {t('evidence.summaryTitle')}
      </h3>
      <dl className="flex flex-col gap-2">
        <CountRow label={t('evidence.records')} count={summary.total_records} />
        <CountRow
          label={t('evidence.demonstrated')}
          count={summary.demonstrated_records}
        />
        <CountRow
          label={t('evidence.conflictingRecords')}
          count={summary.conflicting_records}
        />
        <ValueRow
          label={t('evidence.scope')}
          value={
            summary.scope === 'scan'
              ? t('evidence.scope.scan')
              : t('evidence.scope.filtered_findings')
          }
        />
        {methods.map(([method, count]) => (
          <CountRow key={method} label={methodLabel(method, t)} count={count} />
        ))}
        {confidences.map(([confidence, count]) => (
          <CountRow
            key={confidence}
            label={`${t('evidence.confidenceLabel')}: ${confidenceLabel(confidence, t)}`}
            count={count}
          />
        ))}
      </dl>
      <p className="text-body-sm text-muted-foreground">
        {t('evidence.countNote')}
      </p>
    </section>
  )
}

function endpointOf(observation: EvidenceObservation): string | null {
  if (observation.ip && observation.port != null && observation.protocol) {
    return `${observation.ip}:${observation.port}/${observation.protocol}`
  }
  if (observation.port != null && observation.protocol) {
    return `${observation.port}/${observation.protocol}`
  }
  if (observation.ip) return observation.ip
  if (observation.port != null) return String(observation.port)
  return null
}

type Translate = ReturnType<typeof useI18n>['t']

function resultLabel(result: EvidenceObservation['result'], t: Translate) {
  switch (result) {
    case 'positive':
      return t('evidence.result.positive')
    case 'negative':
      return t('evidence.result.negative')
    case 'inconclusive':
      return t('evidence.result.inconclusive')
  }
}

export function ObservationList({
  observations,
  truncated,
  testId,
  title,
}: {
  observations: EvidenceObservation[]
  truncated: boolean
  testId: string
  title: string
}) {
  const { t } = useI18n()
  if (observations.length === 0 && !truncated) return null

  return (
    <section
      data-testid={testId}
      className="flex flex-col gap-4"
      aria-labelledby={`${testId}-title`}
    >
      <h3 id={`${testId}-title`} className="text-title-xs">
        {title}
      </h3>
      {observations.map((observation, index) => {
        const endpoint = endpointOf(observation)
        const unitId = observation.unit_id
        return (
          <dl
            key={`${observation.condition_key}-${observation.source}-${index}`}
            className="flex flex-col gap-2 border-b border-border pb-4 last:border-b-0 last:pb-0"
          >
            <div className="flex gap-4">
              <dt className="w-1/4 shrink-0 text-caption-md text-muted-foreground">
                {t('evidence.condition')}
              </dt>
              <dd className="min-w-0 break-words font-mono text-caption-md">
                {observation.condition_key}
              </dd>
            </div>
            <div className="flex gap-4">
              <dt className="w-1/4 shrink-0 text-caption-md text-muted-foreground">
                {t('common.result')}
              </dt>
              <dd className="text-body-md">
                {resultLabel(observation.result, t)}
              </dd>
            </div>
            <div className="flex gap-4">
              <dt className="w-1/4 shrink-0 text-caption-md text-muted-foreground">
                {t('evidence.methodLabel')}
              </dt>
              <dd className="text-body-md">
                {methodLabel(observation.method, t)}
              </dd>
            </div>
            {endpoint && (
              <div className="flex gap-4">
                <dt className="w-1/4 shrink-0 text-caption-md text-muted-foreground">
                  {t('evidence.endpoint')}
                </dt>
                <dd className="font-mono text-caption-md">{endpoint}</dd>
              </div>
            )}
            {unitId != null && (
              <div className="flex gap-4">
                <dt className="w-1/4 shrink-0 text-caption-md text-muted-foreground">
                  {t('evidence.modbusUnit')}
                </dt>
                <dd className="font-mono text-caption-md">{unitId}</dd>
              </div>
            )}
            <div className="flex gap-4">
              <dt className="w-1/4 shrink-0 text-caption-md text-muted-foreground">
                {t('evidence.provenance')}
              </dt>
              <dd className="min-w-0 break-words text-body-md">
                {[
                  observation.source,
                  observation.source_script,
                  observation.rule_id,
                  observation.rule_version,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </dd>
            </div>
            <div className="flex gap-4">
              <dt className="w-1/4 shrink-0 text-caption-md text-muted-foreground">
                {t('common.evidence')}
              </dt>
              <dd className="min-w-0 flex-1 whitespace-pre-wrap break-words text-body-md">
                {observation.evidence}
              </dd>
            </div>
          </dl>
        )
      })}
      {truncated && (
        <p
          data-testid={`${testId}-truncated`}
          className="text-body-sm text-muted-foreground"
        >
          {t('evidence.truncated')}
        </p>
      )}
    </section>
  )
}
