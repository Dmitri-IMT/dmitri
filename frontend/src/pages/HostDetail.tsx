import { useParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { getHost } from '@/api/hosts'
import { queryKeys } from '@/api/queryKeys'
import ReadDetailGate from '@/components/ReadDetailGate'
import { readDetailState } from '@/lib/detailState'
import HostFindings from '@/pages/hosts/HostFindings'
import HostIdentity from '@/pages/hosts/HostIdentity'
import HostPortsTable from '@/pages/hosts/HostPortsTable'
import HostScanHistoryTable from '@/pages/hosts/HostScanHistoryTable'

function HostDetail() {
  const { hostId = '' } = useParams()

  const query = useQuery({
    queryKey: queryKeys.hosts.detail(hostId),
    queryFn: () => getHost(hostId),
    enabled: hostId !== '',
  })

  return (
    <ReadDetailGate
      testId="host-detail"
      title="Host"
      notFoundMessage="That host doesn't exist."
      errorMessage="Couldn't load this host."
      backTo="/hosts"
      backLabel="Back to hosts"
      detail={readDetailState(hostId, query)}
    >
      {(host) => (
        <>
          <HostIdentity host={host} />
          <div className="flex flex-col gap-12">
            <section className="flex flex-col gap-4">
              <h2 className="font-title text-title-sm">Findings</h2>
              <HostFindings hostId={host.host_id} />
            </section>
            <section className="flex flex-col gap-4">
              <h2 className="font-title text-title-sm">Open ports</h2>
              <HostPortsTable ports={host.ports} />
            </section>
            <section className="flex flex-col gap-4">
              <h2 className="font-title text-title-sm">Seen in these scans</h2>
              <HostScanHistoryTable history={host.scan_history} />
            </section>
          </div>
        </>
      )}
    </ReadDetailGate>
  )
}

export default HostDetail
