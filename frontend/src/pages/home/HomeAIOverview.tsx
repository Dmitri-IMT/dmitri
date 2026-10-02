import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getScanAnalysis } from '@/api/scans'
import { queryKeys } from '@/api/queryKeys'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import type { HomeSnapshot } from '@/api/home'
import useI18n from '@/i18n/useI18n'
import { evidenceLimitKey } from '@/lib/evidenceCompleteness'

function HomeAIOverview({
  latestScan,
}: {
  latestScan: HomeSnapshot['latest_successful_scan']
}) {
  const { language, t } = useI18n()
  const query = useQuery({
    queryKey: queryKeys.scans.analysis(latestScan?.scan_id ?? '', language),
    queryFn: () => getScanAnalysis(latestScan!.scan_id, language),
    enabled: latestScan !== null,
    retry: false,
  })

  if (!latestScan || query.isPending || query.isError) return null

  const scanLink = `/scans/${latestScan.scan_id}`
  const analysis = query.data

  if (analysis.status === 'unavailable') return null

  if (analysis.status === 'not_requested') {
    return (
      <Card data-testid="home-ai-overview">
        <CardHeader>
          <h2 className="text-title-sm">{t('home.latestScanOverview')}</h2>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <p className="text-body-md text-muted-foreground">
            {t('home.noOverviewYet')}
          </p>
          <Link to={scanLink}>
            <Button type="button" variant="outline" size="sm">
              {t('home.viewAndExplainScan')}
            </Button>
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (analysis.status === 'pending' || analysis.status === 'processing') {
    return (
      <Card data-testid="home-ai-overview" aria-live="polite">
        <CardHeader>
          <h2 className="text-title-sm">{t('home.latestScanOverview')}</h2>
        </CardHeader>
        <CardContent>
          <p className="text-body-md text-muted-foreground">
            {t('home.preparingOverview')}
          </p>
        </CardContent>
      </Card>
    )
  }

  if (analysis.status === 'failed') {
    return (
      <Card data-testid="home-ai-overview">
        <CardHeader>
          <h2 className="text-title-sm">{t('home.latestScanOverview')}</h2>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <p className="text-body-md text-muted-foreground">
            {t('ai.failedOverview')}
          </p>
          <Link to={scanLink}>
            <Button type="button" variant="outline" size="sm">
              {t('home.openResults')}
            </Button>
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (analysis.status !== 'completed') return null

  const limitKey = evidenceLimitKey(latestScan.evidence_completeness)
  return (
    <Card data-testid="home-ai-overview">
      <CardHeader>
        <h2 className="text-title-sm">{t('home.latestScanOverview')}</h2>
        <p className="text-body-sm text-muted-foreground">
          {t('ai.completedDescription')}
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p
          data-testid="home-ai-evidence-limit"
          className="text-body-sm text-muted-foreground"
        >
          {t('ai.evidenceLimit')}
          {limitKey != null && ` ${t(limitKey)}`}
        </p>
        <p className="text-title-xs">{analysis.analysis.executive_summary}</p>
        <p className="max-w-prose text-body-md">
          {analysis.analysis.plain_language_summary}
        </p>
        {analysis.analysis.priority_actions.length > 0 && (
          <section aria-labelledby="home-ai-actions-title">
            <h3 id="home-ai-actions-title" className="text-title-xs">
              {t('ai.whatToDoFirst')}
            </h3>
            <p className="mt-2 max-w-prose text-body-md">
              {analysis.analysis.priority_actions[0].description}
            </p>
          </section>
        )}
        <Link to={scanLink}>
          <Button type="button" variant="outline" size="sm">
            {t('home.viewMoreDetails')}
          </Button>
        </Link>
      </CardContent>
    </Card>
  )
}

export default HomeAIOverview
