import BackLink from '@/components/BackLink'
import EmptyMark from '@/components/EmptyMark'
import Timestamp from '@/components/Timestamp'
import useI18n from '@/i18n/useI18n'
import { weeksSinceLastSeen } from '@/lib/hostLastSeen'
import { MACHINE_TYPE_LABELS } from '@/lib/machineType'
import type { components } from '@/types/openapi'

type HostDetailResponse = components['schemas']['HostDetailResponse']

function HostIdentity({ host }: { host: HostDetailResponse }) {
  const { t } = useI18n()
  const now = new Date()
  const title = host.hostname !== '' ? host.hostname : host.ip
  const weeks = weeksSinceLastSeen(host.last_seen_at, now)
  const portsLabel = host.open_ports_count === 0
    ? t('common.noOpenPorts')
    : t('common.openPorts', { count: host.open_ports_count })
  const typeLabel = MACHINE_TYPE_LABELS[host.machine_type]

  return (
    <div data-testid="host-detail-header" className="flex flex-col gap-2">
      <BackLink fallback="/network" />
      <h1 data-testid="host-detail-identity" className="text-title-lg">{title}</h1>
      <p data-testid="host-detail-meta" className="text-body-md text-muted-foreground">
        <span className="font-mono">{host.ip}</span> ·{' '}
        {host.mac ? <span className="font-mono">{host.mac}</span> : <EmptyMark />}
        {` · ${[host.vendor, typeLabel, portsLabel].filter(Boolean).join(' · ')}`}
      </p>
      <p data-testid="host-detail-seen" className="text-body-md text-muted-foreground">
        {t('common.firstSeen')} <Timestamp value={host.first_seen_at} now={now} /> ·{' '}
        {weeks >= 1
          ? t('common.notSeenForInline', { count: weeks, unit: weeks === 1 ? t('common.week') : t('common.weeks') })
          : <>{t('common.lastSeenInline')} <Timestamp value={host.last_seen_at} now={now} /></>}
      </p>
    </div>
  )
}

export default HostIdentity
