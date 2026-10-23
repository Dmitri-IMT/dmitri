import useI18n from '@/i18n/useI18n'
import { methodLabel } from '@/lib/evidencePresentation'
import type { components } from '@/types/openapi'

type EvidenceObservation =
  components['schemas']['FindingEvidenceObservationPayload']

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
