import EmptyMark from '@/components/EmptyMark'
import Timestamp from '@/components/Timestamp'
import type { components } from '@/types/openapi'

type HostDetailResponse = components['schemas']['HostDetailResponse']

function HostIdentity({ host }: { host: HostDetailResponse }) {
  const title = host.hostname !== '' ? host.hostname : host.ip

  return (
    <div data-testid="host-detail-header" className="flex flex-col gap-4">
      <div className="flex flex-col gap-3">
        <h1
          data-testid="host-detail-identity"
          className="font-title text-title-md"
        >
          {title}
        </h1>
        <p className="text-body-md text-muted-foreground">
          {host.ip} · {host.mac ?? <EmptyMark />} · {host.vendor}
        </p>
        <p
          data-testid="host-detail-seen"
          className="text-body-md text-muted-foreground"
        >
          First seen <Timestamp value={host.first_seen_at} /> · last seen{' '}
          <Timestamp value={host.last_seen_at} />
        </p>
      </div>
      <hr className="border-border" />
    </div>
  )
}

export default HostIdentity
