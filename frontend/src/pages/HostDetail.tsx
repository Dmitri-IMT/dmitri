import { useState } from 'react'
import { useParams } from 'react-router'
import ReadDetailGate from '@/components/ReadDetailGate'
import { useHostDetail } from '@/hooks/useHostDetail'
import HostIdentity from '@/pages/hosts/HostIdentity'
import HostPortsTable from '@/pages/hosts/HostPortsTable'
import HostScanHistoryTable from '@/pages/hosts/HostScanHistoryTable'
import FindingsTable from '@/pages/scans/FindingsTable'

function HostDetail() {
  const { hostId = '' } = useParams()
  const [openFindingId, setOpenFindingId] = useState<string | null>(null)
  const detail = useHostDetail(hostId)

  return (
    <ReadDetailGate
      testId="host-detail"
      title="Host"
      notFoundMessage="That host doesn't exist."
      errorMessage="Couldn't load this host."
      backTo="/hosts"
      backLabel="Back to hosts"
      detail={detail}
    >
      {({ host, findings }) => (
        <>
          <HostIdentity host={host} />
          <div className="flex flex-col gap-12">
            <section className="flex flex-col gap-4">
              <h2 className="font-title text-title-sm">Findings</h2>
              <FindingsTable
                findings={findings}
                testId="host-findings-table"
                caption="Findings on this host"
                emptyTestId="host-no-findings"
                emptyCopy="No findings on this host."
                openFindingId={openFindingId}
                onOpenFindingChange={setOpenFindingId}
              />
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
