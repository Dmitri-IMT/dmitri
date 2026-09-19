import { useParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { explainHost, getHost } from '@/api/hosts'
import type { AIChatResponse } from '@/api/hosts'
import { useState } from 'react'
import { queryKeys } from '@/api/queryKeys'
import ReadDetailGate from '@/components/ReadDetailGate'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { readDetailState } from '@/lib/detailState'
import HostFindings from '@/pages/hosts/HostFindings'
import HostIdentity from '@/pages/hosts/HostIdentity'
import IndustrialServices from '@/pages/hosts/IndustrialServices'
import HostPortsTable from '@/pages/hosts/HostPortsTable'
import HostScanHistoryTable from '@/pages/hosts/HostScanHistoryTable'
import useI18n from '@/i18n/useI18n'

function HostDetail() {
  const { t } = useI18n()
  const { hostId = '' } = useParams()

  const query = useQuery({
    queryKey: queryKeys.hosts.detail(hostId),
    queryFn: () => getHost(hostId),
    enabled: hostId !== '',
  })

  return (
    <ReadDetailGate
      testId="host-detail"
      title={t('common.machine')}
      notFoundMessage={t('common.machineNotFound')}
      errorMessage={t('common.machineLoadError')}
      backTo="/network"
      backLabel="Back to the network"
      detail={readDetailState(hostId, query)}
    >
      {(host) => (
        <>
          <HostIdentity host={host} />
          <div className="flex flex-col gap-8">
            <HostAIExplanation hostId={host.host_id} />
            <Card>
              <CardHeader>
                <h2 className="text-title-sm">{t('common.vulnerabilities')}</h2>
              </CardHeader>
              <CardContent>
                <HostFindings hostId={host.host_id} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <h2 className="text-title-sm">
                  {t('common.servicesRunning')}
                </h2>
              </CardHeader>
              <CardContent>
                <HostPortsTable ports={host.ports} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <h2 className="text-title-sm">{t('common.industrialServices')}</h2>
              </CardHeader>
              <CardContent>
                <IndustrialServices services={host.industrial_services} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <h2 className="text-title-sm">{t('common.scanHistory')}</h2>
              </CardHeader>
              <CardContent>
                <HostScanHistoryTable history={host.scan_history} />
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </ReadDetailGate>
  )
}

function HostAIExplanation({ hostId }: { hostId: string }) {
  const { t } = useI18n()
  const [answer, setAnswer] = useState<AIChatResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function explain() {
    setLoading(true)
    setError(null)
    try {
      setAnswer(await explainHost(hostId))
    } catch (caughtError) {
      const message = (
        caughtError as {
          response?: { data?: { error?: { code?: string; message?: string } } }
        }
      ).response?.data?.error
      setError(
        message?.code === 'ai_rate_limited' && message.message
          ? message.message
          : t('ai.explanationUnavailable'),
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <h2 className="text-title-sm">{t('ai.askAbout', { label: t('common.machine') })}</h2>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Button
          type="button"
          size="sm"
          onClick={() => void explain()}
          disabled={loading}
        >
          {loading ? t('ai.explainMachineLoading') : t('ai.explainMachine')}
        </Button>
        {answer && (
          <div aria-live="polite">
            <p className="text-body-md">{answer.answer}</p>
            {answer.referenced_finding_ids.length > 0 && (
              <p className="mt-2 text-body-sm text-muted-foreground">
                {t('ai.answerConsidered', { count: answer.referenced_finding_ids.length })}
              </p>
            )}
            {answer.uncertainties.length > 0 && (
              <ul className="mt-2 list-disc pl-4 text-body-sm text-muted-foreground">
                {answer.uncertainties.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </div>
        )}
        {error && (
          <p className="text-body-sm text-destructive" role="alert">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export default HostDetail
