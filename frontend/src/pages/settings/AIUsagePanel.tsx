import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getAIUsage } from '@/api/ai'
import { queryKeys } from '@/api/queryKeys'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import Pagination from '@/components/Pagination'
import useI18n from '@/i18n/useI18n'

const USAGE_LIMIT = 50
const USAGE_PER_PAGE = 10
const numberFormat = new Intl.NumberFormat()

function formatNumber(value: number) {
  return numberFormat.format(value)
}

function AIUsagePanel() {
  const { t } = useI18n()
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: queryKeys.ai.usage(USAGE_LIMIT),
    queryFn: () => getAIUsage(USAGE_LIMIT),
    retry: false,
  })
  const entries = query.data?.data ?? []
  // A refetch can return fewer pages than the one the user is on.
  const currentPage = Math.min(
    page,
    Math.max(1, Math.ceil(entries.length / USAGE_PER_PAGE)),
  )
  const pageData = entries.slice(
    (currentPage - 1) * USAGE_PER_PAGE,
    currentPage * USAGE_PER_PAGE,
  )

  return (
    <section data-testid="settings-ai-usage" className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <h2 className="text-title-sm">{t('settings.aiUsage')}</h2>
        <p className="max-w-prose text-body-md text-muted-foreground">
          {t('settings.aiUsageDescription')}
        </p>
      </div>
      {query.isPending && (
        <p className="text-body-md text-muted-foreground" aria-live="polite">
          {t('settings.loadingUsage')}
        </p>
      )}
      {query.isError && (
        <div className="flex flex-col items-start gap-2">
          <p role="alert" className="text-body-md text-muted-foreground">
            {t('settings.usageError')}
          </p>
          <Button
            type="button"
            variant="outline"
            onClick={() => void query.refetch()}
          >
            {t('settings.tryAgain')}
          </Button>
        </div>
      )}
      {query.data && (
        <Card>
          <CardHeader>
            <h3 className="text-title-xs">{t('settings.summary')}</h3>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <dl className="grid grid-cols-2 gap-4 md:grid-cols-5">
              <div>
                <dt className="text-body-sm text-muted-foreground">
                  {t('settings.requests')}
                </dt>
                <dd className="text-title-xs">
                  {formatNumber(query.data.summary.requests)}
                </dd>
              </div>
              <div>
                <dt className="text-body-sm text-muted-foreground">
                  {t('settings.inputTokens')}
                </dt>
                <dd className="text-title-xs">
                  {formatNumber(query.data.summary.input_tokens)}
                </dd>
              </div>
              <div>
                <dt className="text-body-sm text-muted-foreground">
                  {t('settings.outputTokens')}
                </dt>
                <dd className="text-title-xs">
                  {formatNumber(query.data.summary.output_tokens)}
                </dd>
              </div>
              <div>
                <dt className="text-body-sm text-muted-foreground">
                  {t('settings.totalTokens')}
                </dt>
                <dd className="text-title-xs">
                  {formatNumber(query.data.summary.total_tokens)}
                </dd>
              </div>
              <div>
                <dt className="text-body-sm text-muted-foreground">
                  {t('settings.errors')}
                </dt>
                <dd className="text-title-xs">
                  {formatNumber(query.data.summary.errors)}
                </dd>
              </div>
            </dl>
            {query.data.data.length > 0 ? (
              <div className="overflow-x-auto">
                <div
                  className={
                    entries.length > USAGE_PER_PAGE ? 'min-h-usage-table' : ''
                  }
                >
                  <table className="w-full min-w-form text-left text-body-sm">
                    <caption className="sr-only">
                      {t('settings.recentRequests')}
                    </caption>
                    <thead className="border-b border-border text-muted-foreground">
                      <tr className="h-10">
                        <th className="px-2 py-2 font-normal">
                          {t('settings.operation')}
                        </th>
                        <th className="px-2 py-2 font-normal">
                          {t('settings.model')}
                        </th>
                        <th className="px-2 py-2 font-normal">
                          {t('settings.status')}
                        </th>
                        <th className="px-2 py-2 font-normal">
                          {t('settings.tokens')}
                        </th>
                        <th className="px-2 py-2 font-normal">
                          {t('settings.latency')}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {pageData.map((entry, index) => (
                        <tr
                          key={`${entry.created_at}-${index}`}
                          className="h-10 border-b border-border last:border-0"
                        >
                          <td className="px-2 py-2">{entry.operation}</td>
                          <td className="max-w-form truncate px-2 py-2">
                            {entry.model}
                          </td>
                          <td className="px-2 py-2">{entry.status}</td>
                          <td className="px-2 py-2">
                            {formatNumber(entry.total_tokens ?? 0)}
                          </td>
                          <td className="px-2 py-2">
                            {entry.latency_ms === null
                              ? '—'
                              : `${entry.latency_ms} ms`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  page={currentPage}
                  perPage={USAGE_PER_PAGE}
                  total={query.data.data.length}
                  onPageChange={setPage}
                  testId="settings-ai-usage"
                  label={t('settings.usagePages')}
                />
              </div>
            ) : (
              <p className="text-body-md text-muted-foreground">
                {t('settings.noRequests')}
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </section>
  )
}

export default AIUsagePanel
