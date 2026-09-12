import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getScanAnalysis } from '@/api/scans'
import { queryKeys } from '@/api/queryKeys'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import type { components } from '@/types/openapi'

type ScanAIAnalysisResponse = components['schemas']['ScanAIAnalysisResponse']
type AIRecommendedAction = components['schemas']['AIRecommendedAction']

const ANALYSIS_POLL_INTERVAL_MS = 3_000

const PRIORITY_LABEL: Record<AIRecommendedAction['priority'], string> = {
  immediate: 'Immediate',
  high: 'High priority',
  medium: 'Medium priority',
  low: 'Low priority',
}

function waitingForAnalysis(status: ScanAIAnalysisResponse['status']): boolean {
  return status === 'pending' || status === 'processing'
}

/**
 * A compact, read-only entry point to the persisted interpretation of the
 * organisation's newest completed scan. Opening Home never calls the model.
 */
function HomeAIOverview({ scanId }: { scanId: string }) {
  const query = useQuery({
    queryKey: queryKeys.scans.analysis(scanId),
    queryFn: () => getScanAnalysis(scanId),
    enabled: scanId !== '',
    retry: false,
    refetchInterval: (currentQuery) => {
      const status = currentQuery.state.data?.status
      return status && waitingForAnalysis(status)
        ? ANALYSIS_POLL_INTERVAL_MS
        : false
    },
  })

  if (query.data?.status === 'unavailable') return null

  if (query.isError) {
    return (
      <Card data-testid="home-ai-error">
        <CardHeader>
          <h2 className="text-title-sm">AI overview unavailable</h2>
        </CardHeader>
        <CardContent>
          <p className="text-body-md text-muted-foreground">
            We couldn&apos;t load the plain-language overview. Your scan results
            are still available.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (query.isPending) return null

  if (query.data && waitingForAnalysis(query.data.status)) {
    return (
      <Card data-testid="home-ai-pending" aria-live="polite">
        <CardHeader>
          <h2 className="text-title-sm">AI overview</h2>
        </CardHeader>
        <CardContent>
          <p className="text-body-md text-muted-foreground">
            We&apos;re preparing a simpler explanation of your latest scan. The
            technical results are ready now.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (query.data?.status === 'failed') {
    return (
      <Card data-testid="home-ai-failed">
        <CardHeader>
          <h2 className="text-title-sm">AI overview unavailable</h2>
        </CardHeader>
        <CardContent>
          <p className="text-body-md text-muted-foreground">
            We couldn&apos;t prepare the plain-language overview. This does not
            affect your scan results.
          </p>
        </CardContent>
      </Card>
    )
  }

  const analysis = query.data?.analysis
  if (!analysis) return null

  return (
    <Card data-testid="home-ai-completed">
      <CardHeader>
        <h2 className="text-title-sm">Your latest scan, explained</h2>
        <p className="text-body-sm text-muted-foreground">
          A plain-language interpretation based on the recorded scan evidence.
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
            aria-labelledby="home-ai-actions-title"
          >
            <h3 id="home-ai-actions-title" className="text-title-xs">
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

        <div>
          <Button asChild variant="outline">
            <Link to={`/scans/${scanId}`}>View full scan results</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export default HomeAIOverview
