import BackLink from '@/components/BackLink'
import EmptyMark from '@/components/EmptyMark'
import Timestamp from '@/components/Timestamp'
import { weeksSinceLastSeen } from '@/lib/hostLastSeen'
import { MACHINE_TYPE_LABELS } from '@/lib/machineType'
import type { components } from '@/types/openapi'

type HostDetailResponse = components['schemas']['HostDetailResponse']

function openPortsPhrase(count: number): string {
  if (count === 0) return 'no open ports'
  if (count === 1) return '1 open port'
  return `${count} open ports`
}

function HostIdentity({ host }: { host: HostDetailResponse }) {
  const now = new Date()
  const title = host.hostname !== '' ? host.hostname : host.ip
  const weeks = weeksSinceLastSeen(host.last_seen_at, now)
  const quiet = weeks >= 1
  const typeLabel = MACHINE_TYPE_LABELS[host.machine_type]

  return (
    <div data-testid="host-detail-header" className="flex flex-col gap-2">
      <BackLink fallback="/network" />
      <h1 data-testid="host-detail-identity" className="text-title-lg">
        {title}
      </h1>
      <p
        data-testid="host-detail-meta"
        className="text-body-md text-muted-foreground"
      >
        <span className="font-mono">{host.ip}</span> ·{' '}
        {host.mac ? (
          <span className="font-mono">{host.mac}</span>
        ) : (
          <EmptyMark />
        )}
        {` · ${[host.vendor, typeLabel, openPortsPhrase(host.open_ports_count)]
          .filter(Boolean)
          .join(' · ')}`}
      </p>
      <p
        data-testid="host-detail-seen"
        className="text-body-md text-muted-foreground"
      >
        First seen <Timestamp value={host.first_seen_at} now={now} /> ·{' '}
        {quiet ? (
          <>
            not seen for {weeks} {weeks === 1 ? 'week' : 'weeks'}
          </>
        ) : (
          <>
            last seen <Timestamp value={host.last_seen_at} now={now} />
          </>
        )}
      </p>
    </div>
  )
}

export default HostIdentity
