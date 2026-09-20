import { useParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { getHost } from '@/api/hosts'
import { queryKeys } from '@/api/queryKeys'
import ContextChat from '@/components/ContextChat'
import ReadDetailGate from '@/components/ReadDetailGate'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
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
            <ContextChat
              scope="host"
              contextId={host.host_id}
              title={t('ai.askAbout', { label: t('common.machine') })}
              presetQuestion={t('ai.defaultMachineQuestion')}
              askLabel={t('ai.explainMachine')}
              askingLabel={t('ai.explainMachineLoading')}
            />
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
                <h2 className="text-title-sm">{t('common.servicesRunning')}</h2>
              </CardHeader>
              <CardContent>
                <HostPortsTable ports={host.ports} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <h2 className="text-title-sm">
                  {t('common.industrialServices')}
                </h2>
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

export default HostDetail
