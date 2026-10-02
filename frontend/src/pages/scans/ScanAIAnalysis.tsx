import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import {
  getScanAnalysis,
  requestScanAnalysis,
  type ScanAIAnalysisResponse,
} from '@/api/scans'
import { queryKeys } from '@/api/queryKeys'
import Disclosure from '@/components/Disclosure'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card'
import type { components } from '@/types/openapi'
import useI18n from '@/i18n/useI18n'
import { evidenceLimitKey } from '@/lib/evidenceCompleteness'

type FindingRecord = components['schemas']['FindingRecord']
type EvidenceCompleteness = components['schemas']['EvidenceCompleteness']

const ANALYSIS_POLL_INTERVAL_MS = 3_000
const ANALYSIS_POLL_MAX_MS = 5 * 60 * 1_000

function waitingForAnalysis(status: ScanAIAnalysisResponse['status']): boolean {
  return status === 'pending' || status === 'processing'
}

function ScanAIAnalysis({
  scanId,
  findings,
  completeness,
}: {
  scanId: string
  findings: FindingRecord[]
  completeness: EvidenceCompleteness
}) {
  const { language, t } = useI18n()
  const limitKey = evidenceLimitKey(completeness)
  const queryClient = useQueryClient()
  const pollingStartedAtRef = useRef<number | null>(null)
  const [isRequesting, setIsRequesting] = useState(false)
  const [requestFailed, setRequestFailed] = useState(false)

  const query = useQuery({
    queryKey: queryKeys.scans.analysis(scanId, language),
    queryFn: () => getScanAnalysis(scanId, language),
    enabled: scanId !== '',
    retry: false,
    refetchInterval: (currentQuery) => {
      const status = currentQuery.state.data?.status
      if (!status || !waitingForAnalysis(status)) {
        pollingStartedAtRef.current = null
        return false
      }
      if (pollingStartedAtRef.current === null) {
        pollingStartedAtRef.current = Date.now()
      }
      if (Date.now() - pollingStartedAtRef.current >= ANALYSIS_POLL_MAX_MS) {
        return false
      }
      return ANALYSIS_POLL_INTERVAL_MS
    },
  })

  async function handleRequest() {
    setIsRequesting(true)
    setRequestFailed(false)
    try {
      const data = await requestScanAnalysis(scanId, language)
      queryClient.setQueryData(queryKeys.scans.analysis(scanId, language), data)
    } catch (error) {
      if (isAxiosError(error) && error.response?.status === 409) {
        await query.refetch()
      } else {
        setRequestFailed(true)
      }
    } finally {
      setIsRequesting(false)
    }
  }

  if (query.isPending) return null

  if (query.isError || requestFailed) {
    return (
      <Card data-testid="scan-ai-error">
        <CardHeader>
          <h2 className="text-title-sm">{t('ai.overview')}</h2>
        </CardHeader>
        <CardContent>
          <p className="text-body-md text-muted-foreground">
            {t('ai.loadFailed')}
          </p>
        </CardContent>
        <CardFooter>
          <Button
            type="button"
            variant="outline"
            size="sm"
            data-testid="scan-ai-retry"
            onClick={() => {
              setRequestFailed(false)
              void query.refetch()
            }}
          >
            {t('ai.reloadOverview')}
          </Button>
        </CardFooter>
      </Card>
    )
  }

  if (!query.data) return null

  const requestFooter = (
    <CardFooter>
      <Button
        type="button"
        variant="outline"
        size="sm"
        data-testid="scan-ai-request"
        disabled={isRequesting}
        onClick={() => void handleRequest()}
      >
        {t('ai.explainScan')}
      </Button>
    </CardFooter>
  )

  const failedCard = (
    <Card data-testid="scan-ai-failed">
      <CardHeader>
        <h2 className="text-title-sm">{t('ai.overview')}</h2>
      </CardHeader>
      <CardContent>
        <p className="text-body-md text-muted-foreground">
          {t('ai.failedOverview')}
        </p>
      </CardContent>
      {requestFooter}
    </Card>
  )

  switch (query.data.status) {
    case 'unavailable':
      return (
        <Card data-testid="scan-ai-unavailable">
          <CardHeader>
            <h2 className="text-title-sm">{t('ai.overview')}</h2>
          </CardHeader>
          <CardContent>
            <p className="text-body-md text-muted-foreground">
              {t('ai.unavailableOverview')}
            </p>
          </CardContent>
        </Card>
      )
    case 'not_requested':
      return (
        <Card data-testid="scan-ai-not-requested">
          <CardHeader>
            <h2 className="text-title-sm">{t('ai.overview')}</h2>
          </CardHeader>
          <CardContent>
            <p className="text-body-md text-muted-foreground">
              {t('ai.notRequestedOverview')}
            </p>
          </CardContent>
          {requestFooter}
        </Card>
      )
    case 'pending':
    case 'processing':
      return (
        <Card data-testid="scan-ai-pending" aria-live="polite">
          <CardHeader>
            <h2 className="text-title-sm">{t('ai.overview')}</h2>
          </CardHeader>
          <CardContent>
            <p className="text-body-md text-muted-foreground">
              {t('ai.preparingOverview')}
            </p>
          </CardContent>
        </Card>
      )
    case 'failed':
      return failedCard
    case 'completed': {
      const analysis = query.data.analysis
      const findingTitles = new Map(
        findings.map((finding) => [finding.finding_id, finding.title]),
      )
      return (
        <Card data-testid="scan-ai-completed">
          <CardHeader>
            <h2 className="text-title-sm">{t('ai.overview')}</h2>
            <p className="text-body-sm text-muted-foreground">
              {t('ai.completedDescription')}
            </p>
          </CardHeader>
          <CardContent className="flex flex-col gap-6">
            <p
              data-testid="scan-ai-evidence-limit"
              className="text-body-sm text-muted-foreground"
            >
              {t('ai.evidenceLimit')}
              {limitKey != null && ` ${t(limitKey)}`}
            </p>
            <Disclosure
              label={t('ai.showOverview')}
              testId="scan-ai-overview-toggle"
              caretTestId="scan-ai-overview-caret"
              defaultOpen
            >
              <div className="flex flex-col gap-6 pt-3">
                <div className="flex max-w-prose flex-col gap-2 pt-3">
                  <p className="text-title-xs">{analysis.executive_summary}</p>
                  <p className="text-body-md">
                    {analysis.plain_language_summary}
                  </p>
                </div>

                {analysis.priority_actions.length > 0 && (
                  <Disclosure
                    label={t('ai.whatToDoFirst')}
                    testId="scan-ai-actions-toggle"
                    caretTestId="scan-ai-actions-caret"
                  >
                    <section className="flex flex-col gap-3 pt-3">
                      <ol className="flex max-w-prose list-decimal flex-col gap-4 pl-6">
                        {analysis.priority_actions.map((action, index) => (
                          <li
                            key={`${action.priority}-${index}`}
                            className="text-body-md"
                          >
                            <p className="font-semibold">{action.title}</p>
                            <p>{action.description}</p>
                            <p className="text-caption-md text-muted-foreground">
                              {t(
                                `ai.priority${action.priority[0].toUpperCase()}${action.priority.slice(1)}` as
                                  | 'ai.priorityImmediate'
                                  | 'ai.priorityHigh'
                                  | 'ai.priorityMedium'
                                  | 'ai.priorityLow',
                              )}
                            </p>
                          </li>
                        ))}
                      </ol>
                    </section>
                  </Disclosure>
                )}

                {analysis.important_findings.length > 0 && (
                  <section
                    className="flex flex-col gap-3"
                    aria-labelledby="scan-ai-findings-title"
                  >
                    <h3 id="scan-ai-findings-title" className="text-title-xs">
                      {t('ai.whyVulnerabilities')}
                    </h3>
                    <div className="flex max-w-prose flex-col gap-4">
                      {analysis.important_findings.map((finding) => (
                        <div
                          key={finding.finding_id}
                          className="flex flex-col gap-2 border-t border-rule pt-4 first:border-t-0 first:pt-0"
                        >
                          <p className="font-semibold">
                            {findingTitles.get(finding.finding_id) ??
                              t('ai.recordedVulnerability')}
                          </p>
                          <p className="text-body-md">
                            {finding.plain_language_explanation}
                          </p>
                          <p className="text-body-md">
                            {finding.why_it_matters}
                          </p>
                          <p className="text-body-md">
                            <span className="font-semibold">
                              {t('ai.recommendedAction')}{' '}
                            </span>
                            {finding.recommendation}
                          </p>
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                <Disclosure
                  label={t('ai.showDetails')}
                  testId="scan-ai-details-toggle"
                  caretTestId="scan-ai-details-caret"
                >
                  <div className="flex max-w-prose flex-col gap-4 pt-3 text-body-md">
                    <p>{analysis.overall_assessment}</p>
                    {analysis.uncertainties.length > 0 && (
                      <div className="flex flex-col gap-2">
                        <p className="font-semibold">{t('ai.cannotConfirm')}</p>
                        <ul className="list-disc pl-6">
                          {analysis.uncertainties.map((uncertainty, index) => (
                            <li key={index}>{uncertainty}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </Disclosure>
              </div>
            </Disclosure>
          </CardContent>
        </Card>
      )
    }
    default: {
      const _exhaustive: never = query.data
      return _exhaustive
    }
  }
}

export default ScanAIAnalysis
