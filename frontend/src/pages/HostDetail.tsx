import { useParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { getHost } from '@/api/hosts'
import { queryKeys } from '@/api/queryKeys'
import ReadDetailGate from '@/components/ReadDetailGate'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { readDetailState } from '@/lib/detailState'
import HostFindings from '@/pages/hosts/HostFindings'
import HostIdentity from '@/pages/hosts/HostIdentity'
import HostProfile from '@/pages/hosts/HostProfile'
import HostExposures from '@/pages/hosts/HostExposures'
import IndustrialServices from '@/pages/hosts/IndustrialServices'
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
      title="Machine"
      notFoundMessage="That machine doesn't exist."
      errorMessage="Couldn't load this machine."
      backTo="/network"
      backLabel="Back to the network"
      detail={readDetailState(hostId, query)}
    >
      {(host) => (
        <>
          <HostIdentity host={host} />
          <div className="flex flex-col gap-8">
            <Card data-testid="host-profile">
              <CardHeader>
                <h2 className="text-title-sm">Machine profile</h2>
              </CardHeader>
              <CardContent>
                <HostProfile host={host} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <h2 className="text-title-sm">Attack surface</h2>
              </CardHeader>
              <CardContent>
                <HostExposures host={host} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <h2 className="text-title-sm">Vulnerabilities</h2>
              </CardHeader>
              <CardContent>
                <HostFindings hostId={host.host_id} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <h2 className="text-title-sm">
                  Services running on this machine
                </h2>
              </CardHeader>
              <CardContent>
                <HostPortsTable ports={host.ports} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <h2 className="text-title-sm">Industrial services</h2>
              </CardHeader>
              <CardContent>
                <IndustrialServices services={host.industrial_services} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <h2 className="text-title-sm">Scan history</h2>
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
