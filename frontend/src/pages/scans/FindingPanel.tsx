import ContextChat from '@/components/ContextChat'
import { Button } from '@/components/ui/button'
import useI18n from '@/i18n/useI18n'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']

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

function FindingPanel({ finding }: { finding: FindingRecord }) {
  const { t } = useI18n()
  const id = finding.finding_id
  const seen = seenOn(finding)
  const showCve = hasText(finding.cve_id)
  const showCvss = finding.cvss_score != null
  const showMargin = showCve || showCvss || seen != null

  return (
    <div
      data-testid={`finding-panel-${finding.finding_id}`}
      className="flex flex-col gap-6 p-4"
    >
      <ContextChat
        scope="finding"
        contextId={finding.finding_id}
        title={t('ai.findingExplanation')}
        presetQuestion={t('ai.defaultFindingQuestion')}
        askLabel={t('ai.explainFinding')}
        askingLabel={t('ai.explainFindingLoading')}
      />
      <div className="flex gap-8">
        <dl className="flex min-w-0 flex-1 flex-col gap-6">
          <div className="flex gap-4">
            <Label>{t('common.riskScore')}</Label>
            <dd className="min-w-0 max-w-prose text-body-md">
              {finding.risk_score == null
                ? t('common.riskScoreNotCalculated')
                : t('common.riskScoreValue', {
                    score: Math.round(finding.risk_score),
                  })}
              {finding.confidence && (
                <p>
                  {t('common.confidence')}: {finding.confidence}
                </p>
              )}
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
    </div>
  )
}

export default FindingPanel
