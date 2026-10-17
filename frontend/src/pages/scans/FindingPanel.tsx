import ContextChat from '@/components/ContextChat'
import { Button } from '@/components/ui/button'
import useI18n from '@/i18n/useI18n'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']
type EvidenceSummary = components['schemas']['FindingEvidenceSummary']
type EvidenceObservation =
  components['schemas']['FindingEvidenceObservationPayload']

function hasText(value: string | null | undefined): boolean {
  return value != null && value !== ''
}

function seenOn(finding: FindingRecord): string | null {
  const place =
    finding.port != null && finding.protocol
      ? `${finding.port}/${finding.protocol}`
      : finding.port != null
        ? String(finding.port)
        : null
  if (hasText(finding.service) && place) return `${finding.service} · ${place}`
  if (hasText(finding.service)) return finding.service ?? null
  return place
}

function Label({ children }: { children: string }) {
  return (
    <dt className="w-1/4 shrink-0 text-caption-md uppercase tracking-widest text-muted-foreground">
      {children}
    </dt>
  )
}

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

function methodLabel(method: EvidenceObservation['method'], t: Translate) {
  switch (method) {
    case 'version_correlation':
      return t('evidence.method.version_correlation')
    case 'configuration_observation':
      return t('evidence.method.configuration_observation')
    case 'specific_check':
      return t('evidence.method.specific_check')
    case 'textual_reference':
      return t('evidence.method.textual_reference')
    case 'unknown':
      return t('evidence.method.unknown')
  }
}

function confidenceLabel(
  confidence: keyof EvidenceSummary['by_confidence'],
  t: Translate,
) {
  switch (confidence) {
    case 'tentative':
      return t('evidence.confidence.tentative')
    case 'probable':
      return t('evidence.confidence.probable')
    case 'confirmed':
      return t('evidence.confidence.confirmed')
    case 'unknown':
      return t('evidence.confidence.unknown')
  }
}

function statusLabel(
  status: FindingRecord['evidence_status'],
  method: FindingRecord['detection_method'],
  t: Translate,
) {
  switch (status) {
    case 'supported':
      if (method === 'version_correlation') {
        return t('evidence.status.supportedVersionCorrelation')
      }
      return t('evidence.status.supported')
    case 'inconclusive':
      return t('evidence.status.inconclusive')
    case 'conflicting':
      return t('evidence.status.conflicting')
    case 'unknown':
      return t('evidence.status.unknown')
  }
}

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

function evidenceExplanation(finding: FindingRecord, t: Translate): string {
  if (finding.evidence_status === 'conflicting')
    return t('evidence.explanation.conflicting')
  if (finding.evidence_status === 'inconclusive')
    return t('evidence.explanation.inconclusive')
  if (
    finding.evidence_status === 'unknown' &&
    (finding.evidence_observations ?? []).length === 0
  ) {
    return t('evidence.explanation.legacy')
  }
  if (finding.detection_method === 'version_correlation')
    return t('evidence.explanation.correlation')
  if (finding.detection_method === 'configuration_observation')
    return t('evidence.explanation.configuration')
  if (finding.detection_method === 'specific_check')
    return t('evidence.explanation.specificCheck')
  if (finding.detection_method === 'textual_reference')
    return t('evidence.explanation.textReference')
  return t('evidence.explanation.unknown')
}

function FindingPanel({ finding }: { finding: FindingRecord }) {
  const { t } = useI18n()
  const id = finding.finding_id
  const seen = seenOn(finding)
  const showCve = hasText(finding.cve_id)
  const showCvss = finding.cvss_score != null
  const showMargin = showCve || showCvss || seen != null
  const observations = finding.evidence_observations ?? []
  const method = finding.detection_method ?? 'unknown'
  const status = finding.evidence_status ?? 'unknown'
  const confidence = finding.confidence

  return (
    <div
      data-testid={`finding-panel-${finding.finding_id}`}
      className="flex flex-col gap-6 p-4"
    >
      <div className="flex gap-8">
        <dl className="flex min-w-0 flex-1 flex-col gap-6">
          <div
            data-testid={`finding-evidence-${id}`}
            className="flex flex-col gap-4"
          >
            <dl className="flex flex-col gap-2">
              <div
                data-testid={`finding-severity-${id}`}
                className="flex gap-4"
              >
                <Label>{t('common.severityLabel')}</Label>
                <dd className="text-body-md font-semibold">
                  {t('common.severity', { severity: finding.severity })}
                </dd>
              </div>
              <div data-testid={`finding-method-${id}`} className="flex gap-4">
                <Label>{t('evidence.methodLabel')}</Label>
                <dd className="text-body-md">{methodLabel(method, t)}</dd>
              </div>
              <div data-testid={`finding-status-${id}`} className="flex gap-4">
                <Label>{t('evidence.statusLabel')}</Label>
                <dd className="text-body-md">
                  {statusLabel(status, method, t)}
                </dd>
              </div>
              <div
                data-testid={`finding-confidence-${id}`}
                className="flex gap-4"
              >
                <Label>{t('evidence.confidenceLabel')}</Label>
                <dd className="text-body-md">
                  {confidence
                    ? confidenceLabel(confidence, t)
                    : t('evidence.confidence.notReported')}
                </dd>
              </div>
            </dl>
            <p className="max-w-prose text-body-md">
              {evidenceExplanation(finding, t)}
            </p>
            <ObservationList
              observations={observations}
              truncated={finding.evidence_truncated}
              testId={`finding-observations-${id}`}
              title={t('evidence.recordedTitle')}
            />
          </div>
          <div className="flex gap-4">
            <Label>{t('common.riskScore')}</Label>
            <dd className="min-w-0 max-w-prose text-body-md">
              {finding.risk_score == null
                ? t('common.riskScoreNotCalculated')
                : t('common.riskScoreValue', {
                    score: Math.round(finding.risk_score),
                  })}
              {finding.exploitability != null && (
                <p>
                  {t('common.exploitabilityIndex')}:{' '}
                  {finding.exploitability.toFixed(2)} / 1
                </p>
              )}
              {finding.risk_rationale && <p>{finding.risk_rationale}</p>}
            </dd>
          </div>
          {hasText(finding.description) && (
            <div className="flex gap-4">
              <Label>{t('common.whatItIs')}</Label>
              <dd className="min-w-0 max-w-prose text-body-md">
                {finding.description}
              </dd>
            </div>
          )}
          {hasText(finding.recommendation) && (
            <div className="flex gap-4">
              <Label>{t('common.whatToDo')}</Label>
              <dd className="min-w-0 max-w-prose text-body-md">
                {finding.recommendation}
              </dd>
            </div>
          )}
          {hasText(finding.evidence) && (
            <div className="flex gap-4">
              <Label>{t('common.evidence')}</Label>
              <dd className="min-w-0 flex-1">
                <pre className="overflow-x-auto border border-border bg-card p-4 font-mono text-caption-md whitespace-pre">
                  {finding.evidence}
                </pre>
              </dd>
            </div>
          )}
          {finding.references.length > 0 && (
            <div className="flex gap-4">
              <Label>{t('common.references')}</Label>
              <dd
                data-testid={`findings-panel-refs-${id}`}
                className="flex min-w-0 flex-1 flex-col gap-2"
              >
                {finding.references.map((url) => (
                  <Button
                    key={url}
                    asChild
                    variant="link"
                    className="h-auto max-w-full justify-start p-0 text-caption-md"
                  >
                    <a
                      href={url}
                      target="_blank"
                      rel="noreferrer noopener"
                      title={url}
                      className="truncate"
                    >
                      {url}
                    </a>
                  </Button>
                ))}
              </dd>
            </div>
          )}
        </dl>
        {showMargin && (
          <div className="flex w-1/4 shrink-0 flex-col gap-6 border-l border-border pl-8">
            {showCve && (
              <div className="flex flex-col gap-2">
                <p className="text-caption-md uppercase tracking-widest text-muted-foreground">
                  CVE
                </p>
                <p className="text-body-md" title={finding.cve_id ?? undefined}>
                  {finding.cve_id}
                </p>
              </div>
            )}
            {showCvss && (
              <div
                data-testid={`findings-panel-cvss-${id}`}
                className="flex flex-col gap-2"
              >
                <p className="text-caption-md uppercase tracking-widest text-muted-foreground">
                  {t('common.cvss')}
                </p>
                <p className="text-body-md">{finding.cvss_score}</p>
              </div>
            )}
            {seen != null && (
              <div className="flex flex-col gap-2">
                <p className="text-caption-md uppercase tracking-widest text-muted-foreground">
                  {t('common.seenOn')}
                </p>
                <p className="text-body-md">{seen}</p>
              </div>
            )}
          </div>
        )}
      </div>
      <ContextChat
        scope="finding"
        contextId={finding.finding_id}
        title={t('ai.findingExplanation')}
        presetQuestion={t('ai.defaultFindingQuestion')}
        askLabel={t('ai.explainFinding')}
        askingLabel={t('ai.explainFindingLoading')}
      />
    </div>
  )
}

export default FindingPanel
