import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { getHost } from '@/api/hosts'
import { listFindings } from '@/api/findings'
import { queryKeys } from '@/api/queryKeys'
import BackLink from '@/components/BackLink'
import ReadDetailGate from '@/components/ReadDetailGate'
import ExplainPanel from '@/components/ExplainPanel'
import ItSections from '@/components/ItSections'
import ProblemsTable from '@/components/ProblemsTable'
import Timestamp from '@/components/Timestamp'
import { Button } from '@/components/ui/button'
import { readDetailState } from '@/lib/detailState'
import { useToast } from '@/hooks/useToast'
import useI18n from '@/i18n/useI18n'
import HostDelete from '@/pages/hosts/HostDelete'
import HostProfile from '@/pages/hosts/HostProfile'
import HostExposures from '@/pages/hosts/HostExposures'
import IndustrialServices from '@/pages/hosts/IndustrialServices'
import HostPortsTable from '@/pages/hosts/HostPortsTable'
import HostScanHistoryTable from '@/pages/hosts/HostScanHistoryTable'
import MachineAbout from '@/pages/hosts/MachineAbout'
import MachineBestFix from '@/pages/hosts/MachineBestFix'
import ScanDetailSection from '@/pages/scans/ScanDetailSection'
import type { components } from '@/types/openapi'

function MachineBody({
  host,
}: {
  host: components['schemas']['HostDetailResponse']
}) {
  const { t } = useI18n()
  const { show } = useToast()
  const [search] = useSearchParams()
  const [openId, setOpenId] = useState<string | null>(() =>
    search.get('finding'),
  )
  const scanId = host.scan_history[0]?.scan_id ?? ''
  const params = { host_id: host.host_id, scan_id: scanId, per_page: 100 }
  const findingsQuery = useQuery({
    queryKey: queryKeys.findings.list(params),
    queryFn: async () => {
      const first = await listFindings(params)
      const pages = Math.ceil(first.total / 100)
      const remaining = await Promise.all(
        Array.from({ length: Math.max(0, pages - 1) }, (_, i) =>
          listFindings({ ...params, page: i + 2 }),
        ),
      )
      return {
        ...first,
        data: [...first.data, ...remaining.flatMap((page) => page.data)],
      }
    },
    enabled: scanId !== '',
  })
  useEffect(() => {
    if (findingsQuery.isError) show(t('common.findingsLoadError'))
  }, [findingsQuery.isError, show, t])
  const findings = findingsQuery.data?.data ?? []
  return (
    <>
      <header className="flex flex-col gap-3">
        <BackLink fallback="/network" />
        <div className="flex items-end justify-between gap-6">
          <div className="flex flex-col gap-2">
            <p className="text-caption-md text-ink-muted">
              {t(`machine.type.${host.machine_type}`)} ·{' '}
              <Timestamp value={host.last_seen_at} />
            </p>
            <h1 data-testid="host-detail-identity" className="text-title-lg">
              {host.hostname || host.ip}
            </h1>
            <p className="font-mono text-body-md text-ink-muted">{host.ip}</p>
          </div>
          {scanId && (
            <ExplainPanel
              scope="host"
              contextId={host.host_id}
              scanId={scanId}
            />
          )}
        </div>
      </header>
      {findingsQuery.isError ? (
        <Button
          variant="outline"
          className="self-start"
          onClick={() => void findingsQuery.refetch()}
        >
          {t('explain.retry')}
        </Button>
      ) : findingsQuery.isPending && scanId ? (
        <p role="status" className="text-body-md text-ink-muted">
          {t('ai.loadingHistory')}
        </p>
      ) : (
        <>
          <MachineAbout host={host} findings={findings} />
          <MachineBestFix scanId={scanId} findings={findings} />
          <ProblemsTable
            findings={findings}
            machine
            openFindingId={openId}
            onOpenFindingChange={setOpenId}
          />
        </>
      )}
      <ItSections>
        <ScanDetailSection
          testId="it-section-ports"
          title={t('machine.ports', { n: host.open_ports_count })}
        >
          <div className="flex flex-col gap-6">
            <HostExposures host={host} />
            <HostPortsTable ports={host.ports} />
            {host.industrial_services.length > 0 && (
              <IndustrialServices services={host.industrial_services} />
            )}
          </div>
        </ScanDetailSection>
        <ScanDetailSection
          testId="it-section-profile"
          title={t('machine.profile')}
        >
          <div className="flex flex-col gap-6">
            <dl
              data-testid="host-profile-identity"
              className="grid grid-cols-3 gap-4 text-body-sm"
            >
              <div>
                <dt className="text-ink-muted">{t('common.address')}</dt>
                <dd className="font-mono">{host.ip}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">{t('common.mac')}</dt>
                <dd className="font-mono">{host.mac ?? '—'}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">{t('common.vendor')}</dt>
                <dd>{host.vendor || '—'}</dd>
              </div>
            </dl>
            <HostProfile host={host} />
          </div>
        </ScanDetailSection>
        <ScanDetailSection
          testId="it-section-history"
          title={t('machine.scanHistory', { n: host.scan_history.length })}
        >
          <HostScanHistoryTable history={host.scan_history} />
        </ScanDetailSection>
      </ItSections>
      <HostDelete host={host} />
    </>
  )
}
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
      {(host) => <MachineBody key={host.host_id} host={host} />}
    </ReadDetailGate>
  )
}
export default HostDetail
