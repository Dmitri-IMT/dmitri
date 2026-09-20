import { useState } from 'react'
import { askContextAI } from '@/api/ai'
import type { AIChatResponse } from '@/api/ai'
import { Button } from '@/components/ui/button'
import useI18n from '@/i18n/useI18n'
import { readAiAskError } from '@/api/readAiAskError'
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
  const { language, t } = useI18n()
  const [explanation, setExplanation] = useState<AIChatResponse | null>(null)
  const [explanationError, setExplanationError] = useState<string | null>(null)
  const [isExplaining, setIsExplaining] = useState(false)
  const id = finding.finding_id
  const seen = seenOn(finding)
  const showCve = hasText(finding.cve_id)
  const showCvss = finding.cvss_score != null
  const showMargin = showCve || showCvss || seen != null

  async function handleExplain() {
    setIsExplaining(true)
    setExplanationError(null)
    try {
      const response = await askContextAI(
        'finding',
        finding.finding_id,
        t('ai.defaultFindingQuestion'),
        language,
      )
      setExplanation(response)
    } catch (caughtError) {
      setExplanationError(
        readAiAskError(caughtError, t('ai.explanationUnavailable')),
      )
    } finally {
      setIsExplaining(false)
    }
  }

  return (
    <div
      data-testid={`finding-panel-${finding.finding_id}`}
      className="flex gap-8 p-4"
    >
      <dl className="flex min-w-0 flex-1 flex-col gap-6">
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            size="sm"
            onClick={() => void handleExplain()}
            disabled={isExplaining}
          >
            {isExplaining
              ? t('ai.explainFindingLoading')
              : t('ai.explainFinding')}
          </Button>
          {explanationError && (
            <p className="text-body-sm text-destructive" role="alert">
              {explanationError}
            </p>
          )}
        </div>
        {explanation && (
          <div
            className="rounded-md border border-border p-4"
            aria-live="polite"
          >
            <p className="text-body-sm font-medium">
              {t('ai.findingExplanation')}
            </p>
            <p className="text-body-md">{explanation.answer}</p>
            {explanation.referenced_finding_ids.length > 0 && (
              <a
                className="mt-2 inline-block text-body-sm text-primary underline"
                href={`/scans/${finding.scan_id}?finding=${explanation.referenced_finding_ids[0]}`}
              >
                {t('ai.viewRelatedFinding')}
              </a>
            )}
            {explanation.uncertainties.length > 0 && (
              <ul className="mt-2 list-disc pl-4 text-body-sm text-muted-foreground">
                {explanation.uncertainties.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </div>
        )}
        <div className="flex gap-4">
          <Label>Risk score</Label>
          <dd className="min-w-0 max-w-prose text-body-md">
            {finding.risk_score == null
              ? 'Not calculated'
              : `${Math.round(finding.risk_score)} of 100`}
            {finding.confidence && <p>Confidence: {finding.confidence}</p>}
            {finding.exploitability != null && (
              <p>
                Exploitability index: {finding.exploitability.toFixed(2)} / 1
              </p>
            )}
            {finding.risk_rationale && <p>{finding.risk_rationale}</p>}
          </dd>
        </div>
        {hasText(finding.description) && (
          <div className="flex gap-4">
            <Label>What it is</Label>
            <dd className="min-w-0 max-w-prose text-body-md">
              {finding.description}
            </dd>
          </div>
        )}
        {hasText(finding.recommendation) && (
          <div className="flex gap-4">
            <Label>What to do</Label>
            <dd className="min-w-0 max-w-prose text-body-md">
              {finding.recommendation}
            </dd>
          </div>
        )}
        {hasText(finding.evidence) && (
          <div className="flex gap-4">
            <Label>Evidence</Label>
            <dd className="min-w-0 flex-1">
              <pre className="overflow-x-auto border border-border bg-card p-4 font-mono text-caption-md whitespace-pre">
                {finding.evidence}
              </pre>
            </dd>
          </div>
        )}
        {finding.references.length > 0 && (
          <div className="flex gap-4">
            <Label>References</Label>
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
                CVSS
              </p>
              <p className="text-body-md">{finding.cvss_score}</p>
            </div>
          )}
          {seen != null && (
            <div className="flex flex-col gap-2">
              <p className="text-caption-md uppercase tracking-widest text-muted-foreground">
                Seen on
              </p>
              <p className="text-body-md">{seen}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default FindingPanel
