import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getScanAnalysis } from '@/api/scans'
import { queryKeys } from '@/api/queryKeys'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import type { HomeSnapshot } from '@/api/home'

function HomeAIOverview({
  latestScan,
}: {
  latestScan: HomeSnapshot['latest_successful_scan']
}) {
  const query = useQuery({
    queryKey: queryKeys.scans.analysis(latestScan?.scan_id ?? ''),
    queryFn: () => getScanAnalysis(latestScan!.scan_id),
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
          <h2 className="text-title-sm">Resumo da última varredura</h2>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <p className="text-body-md text-muted-foreground">
            Ainda não há uma explicação em linguagem simples para esta
            varredura.
          </p>
          <Link to={scanLink}>
            <Button type="button" variant="outline" size="sm">
              Ver e explicar esta varredura
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
          <h2 className="text-title-sm">Resumo da última varredura</h2>
        </CardHeader>
        <CardContent>
          <p className="text-body-md text-muted-foreground">
            A explicação está sendo preparada. Você pode acompanhar o
            progresso na página da varredura.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (analysis.status === 'failed') {
    return (
      <Card data-testid="home-ai-overview">
        <CardHeader>
          <h2 className="text-title-sm">Resumo da última varredura</h2>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <p className="text-body-md text-muted-foreground">
            Não foi possível preparar a explicação agora. Os resultados
            técnicos continuam disponíveis.
          </p>
          <Link to={scanLink}>
            <Button type="button" variant="outline" size="sm">
              Abrir resultados
            </Button>
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (analysis.status !== 'completed') return null

  return (
    <Card data-testid="home-ai-overview">
      <CardHeader>
        <h2 className="text-title-sm">Resumo da última varredura</h2>
        <p className="text-body-sm text-muted-foreground">
          Uma leitura simples baseada somente nas evidências registradas.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-title-xs">{analysis.analysis.executive_summary}</p>
        <p className="max-w-prose text-body-md">
          {analysis.analysis.plain_language_summary}
        </p>
        {analysis.analysis.priority_actions.length > 0 && (
          <section aria-labelledby="home-ai-actions-title">
            <h3 id="home-ai-actions-title" className="text-title-xs">
              Primeiro passo recomendado
            </h3>
            <p className="mt-2 max-w-prose text-body-md">
              {analysis.analysis.priority_actions[0].description}
            </p>
          </section>
        )}
        <Link to={scanLink}>
          <Button type="button" variant="outline" size="sm">
            Ver mais detalhes
          </Button>
        </Link>
      </CardContent>
    </Card>
  )
}

export default HomeAIOverview
