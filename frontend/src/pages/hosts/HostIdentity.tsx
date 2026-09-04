import BackLink from '@/components/BackLink'
import EmptyMark from '@/components/EmptyMark'
import Timestamp from '@/components/Timestamp'
import { isSilent, weeksSince } from '@/lib/silentDevice'
import type { components } from '@/types/openapi'

type HostDetailResponse = components['schemas']['HostDetailResponse']

function HostIdentity({ host }: { host: HostDetailResponse }) {
  const now = new Date()
  const title = host.hostname !== '' ? host.hostname : host.ip
  const quiet = isSilent(host.last_seen_at, now)

  return (
    <div data-testid="host-detail-header" className="flex flex-col gap-2">
      <BackLink fallback="/network" />
      <h1 data-testid="host-detail-identity" className="text-title-lg">
        {title}
      </h1>
      <p className="text-body-md text-muted-foreground">
        <span className="font-mono">{host.ip}</span> ·{' '}
        {host.mac ? (
          <span className="font-mono">{host.mac}</span>
        ) : (
          <EmptyMark />
        )}{' '}
        · {host.vendor}
      </p>
      <p
        data-testid="host-detail-seen"
        className="text-body-md text-muted-foreground"
      >
        First seen <Timestamp value={host.first_seen_at} now={now} /> ·{' '}
        {quiet ? (
          <>not seen for {weeksSince(host.last_seen_at, now)} weeks</>
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
