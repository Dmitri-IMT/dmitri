import { useQuery } from '@tanstack/react-query'
import { getAIUsage } from '@/api/ai'
import { queryKeys } from '@/api/queryKeys'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'

const USAGE_LIMIT = 50
const numberFormat = new Intl.NumberFormat()

function formatNumber(value: number) {
  return numberFormat.format(value)
}

function AIUsagePanel() {
  const query = useQuery({
    queryKey: queryKeys.ai.usage(USAGE_LIMIT),
    queryFn: () => getAIUsage(USAGE_LIMIT),
    retry: false,
  })

  return (
    <section data-testid="settings-ai-usage" className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <h2 className="text-title-sm">AI usage</h2>
        <p className="max-w-prose text-body-md text-muted-foreground">
          Organization-wide provider usage. Prompts and model responses are not
          stored here.
        </p>
      </div>
      {query.isPending && (
        <p className="text-body-md text-muted-foreground" aria-live="polite">
          Loading usage…
        </p>
      )}
      {query.isError && (
        <div className="flex flex-col items-start gap-2">
          <p role="alert" className="text-body-md text-muted-foreground">
            Usage data could not be loaded.
          </p>
          <Button
            type="button"
            variant="outline"
            onClick={() => void query.refetch()}
          >
            Try again
          </Button>
        </div>
      )}
      {query.data && (
        <Card>
          <CardHeader>
            <h3 className="text-title-xs">Summary</h3>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <dl className="grid grid-cols-2 gap-4 md:grid-cols-5">
              <div>
                <dt className="text-body-sm text-muted-foreground">Requests</dt>
                <dd className="text-title-xs">
                  {formatNumber(query.data.summary.requests)}
                </dd>
              </div>
              <div>
                <dt className="text-body-sm text-muted-foreground">
                  Input tokens
                </dt>
                <dd className="text-title-xs">
                  {formatNumber(query.data.summary.input_tokens)}
                </dd>
              </div>
              <div>
                <dt className="text-body-sm text-muted-foreground">
                  Output tokens
                </dt>
                <dd className="text-title-xs">
                  {formatNumber(query.data.summary.output_tokens)}
                </dd>
              </div>
              <div>
                <dt className="text-body-sm text-muted-foreground">
                  Total tokens
                </dt>
                <dd className="text-title-xs">
                  {formatNumber(query.data.summary.total_tokens)}
                </dd>
              </div>
              <div>
                <dt className="text-body-sm text-muted-foreground">Errors</dt>
                <dd className="text-title-xs">
                  {formatNumber(query.data.summary.errors)}
                </dd>
              </div>
            </dl>
            {query.data.data.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-form text-left text-body-sm">
                  <caption className="sr-only">
                    Recent AI provider requests
                  </caption>
                  <thead className="border-b border-border text-muted-foreground">
                    <tr>
                      <th className="px-2 py-2 font-normal">Operation</th>
                      <th className="px-2 py-2 font-normal">Model</th>
                      <th className="px-2 py-2 font-normal">Status</th>
                      <th className="px-2 py-2 font-normal">Tokens</th>
                      <th className="px-2 py-2 font-normal">Latency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.data.map((entry, index) => (
                      <tr
                        key={`${entry.created_at}-${index}`}
                        className="border-b border-border last:border-0"
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
            ) : (
              <p className="text-body-md text-muted-foreground">
                No AI requests recorded yet.
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </section>
  )
}

export default AIUsagePanel
