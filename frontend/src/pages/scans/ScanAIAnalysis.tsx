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

type FindingRecord = components['schemas']['FindingRecord']
type AIRecommendedAction = components['schemas']['AIRecommendedAction']

const ANALYSIS_POLL_INTERVAL_MS = 3_000
const ANALYSIS_POLL_MAX_MS = 5 * 60 * 1_000

const PRIORITY_LABEL: Record<AIRecommendedAction['priority'], string> = {
  immediate: 'Immediate',
  high: 'High priority',
  medium: 'Medium priority',
  low: 'Low priority',
}

function waitingForAnalysis(status: ScanAIAnalysisResponse['status']): boolean {
  return status === 'pending' || status === 'processing'
}

function ScanAIAnalysis({
  scanId,
  findings,
}: {
  scanId: string
  findings: FindingRecord[]
}) {
  const queryClient = useQueryClient()
  const pollingStartedAtRef = useRef<number | null>(null)
  const [isRequesting, setIsRequesting] = useState(false)
  const [requestFailed, setRequestFailed] = useState(false)

  const query = useQuery({
    queryKey: queryKeys.scans.analysis(scanId),
    queryFn: () => getScanAnalysis(scanId),
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
      const data = await requestScanAnalysis(scanId)
      queryClient.setQueryData(queryKeys.scans.analysis(scanId), data)
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
          <h2 className="text-title-sm">AI overview</h2>
        </CardHeader>
        <CardContent>
          <p className="text-body-md text-muted-foreground">
            Couldn&apos;t load the overview.
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
            Reload overview
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
        Explain this scan
      </Button>
    </CardFooter>
  )

  const failedCard = (
    <Card data-testid="scan-ai-failed">
      <CardHeader>
        <h2 className="text-title-sm">AI overview</h2>
      </CardHeader>
      <CardContent>
        <p className="text-body-md text-muted-foreground">
          Couldn&apos;t prepare the overview. The scan results are complete
          without it.
        </p>
      </CardContent>
      {requestFooter}
    </Card>
  )

  switch (query.data.status) {
    case 'unavailable':
      return null
    case 'not_requested':
      return (
        <Card data-testid="scan-ai-not-requested">
          <CardHeader>
            <h2 className="text-title-sm">AI overview</h2>
          </CardHeader>
          <CardContent>
            <p className="text-body-md text-muted-foreground">
              Get a plain-language overview of this scan.
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
            <h2 className="text-title-sm">AI overview</h2>
          </CardHeader>
          <CardContent>
            <p className="text-body-md text-muted-foreground">
              Preparing a plain-language overview of this scan.
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
            <h2 className="text-title-sm">AI overview</h2>
            <p className="text-body-sm text-muted-foreground">
              A plain-language interpretation of this scan&apos;s recorded
              evidence.
            </p>
          </CardHeader>
          <CardContent className="flex flex-col gap-6">
            <div className="flex max-w-prose flex-col gap-2">
              <p className="text-title-xs">{analysis.executive_summary}</p>
              <p className="text-body-md">{analysis.plain_language_summary}</p>
            </div>

            {analysis.priority_actions.length > 0 && (
              <section
                className="flex flex-col gap-3"
                aria-labelledby="scan-ai-actions-title"
              >
                <h3 id="scan-ai-actions-title" className="text-title-xs">
                  What to do first
                </h3>
                <ol className="flex max-w-prose list-decimal flex-col gap-4 pl-6">
                  {analysis.priority_actions.map((action, index) => (
                    <li
                      key={`${action.priority}-${index}`}
                      className="text-body-md"
                    >
                      <p className="font-semibold">{action.title}</p>
                      <p>{action.description}</p>
                      <p className="text-caption-md text-muted-foreground">
                        {PRIORITY_LABEL[action.priority]}
                      </p>
                    </li>
                  ))}
                </ol>
              </section>
            )}

            {analysis.important_findings.length > 0 && (
              <section
                className="flex flex-col gap-3"
                aria-labelledby="scan-ai-findings-title"
              >
                <h3 id="scan-ai-findings-title" className="text-title-xs">
                  Why these vulnerabilities matter
                </h3>
                <div className="flex max-w-prose flex-col gap-4">
                  {analysis.important_findings.map((finding) => (
                    <div
                      key={finding.finding_id}
                      className="flex flex-col gap-2 border-t border-rule pt-4 first:border-t-0 first:pt-0"
                    >
                      <p className="font-semibold">
                        {findingTitles.get(finding.finding_id) ??
                          'Recorded vulnerability'}
                      </p>
                      <p className="text-body-md">
                        {finding.plain_language_explanation}
                      </p>
                      <p className="text-body-md">{finding.why_it_matters}</p>
                      <p className="text-body-md">
                        <span className="font-semibold">
                          Recommended action:{' '}
                        </span>
                        {finding.recommendation}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <Disclosure
              label="Show assessment details and limitations"
              testId="scan-ai-details-toggle"
              caretTestId="scan-ai-details-caret"
            >
              <div className="flex max-w-prose flex-col gap-4 pt-3 text-body-md">
                <p>{analysis.overall_assessment}</p>
                {analysis.uncertainties.length > 0 && (
                  <div className="flex flex-col gap-2">
                    <p className="font-semibold">
                      What this scan cannot confirm
                    </p>
                    <ul className="list-disc pl-6">
                      {analysis.uncertainties.map((uncertainty, index) => (
                        <li key={index}>{uncertainty}</li>
                      ))}
                    </ul>
                  </div>
                )}
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
