import { type ReactNode, useState } from 'react'
import { useParams } from 'react-router'
import ErrorRetry from '@/components/ErrorRetry'
import NotFoundNotice from '@/components/NotFoundNotice'
import PageHeader from '@/components/PageHeader'
import { useHostDetail } from '@/hooks/useHostDetail'
import HostIdentity from '@/pages/hosts/HostIdentity'
import HostPortsTable from '@/pages/hosts/HostPortsTable'
import HostScanHistoryTable from '@/pages/hosts/HostScanHistoryTable'
import FindingsTable from '@/pages/scans/FindingsTable'

function HostDetail() {
  const { hostId = '' } = useParams()
  const [openFindingId, setOpenFindingId] = useState<string | null>(null)
  const detail = useHostDetail(hostId)

  let header: ReactNode = <PageHeader title="Host" />
  let body: ReactNode

  if (detail.state === 'notFound') {
    body = (
      <NotFoundNotice
        testId="host-detail"
        message="That host doesn't exist."
        backTo="/hosts"
        backLabel="Back to hosts"
      />
    )
  } else if (detail.state === 'error') {
    body = (
      <ErrorRetry
        testId="host-detail-error"
        message="Couldn't load this host."
        onRetry={detail.retry}
      />
    )
  } else if (detail.state === 'loading') {
    body = null
  } else {
    header = <HostIdentity host={detail.host} />
    body = (
      <div className="flex flex-col gap-12">
        <section className="flex flex-col gap-4">
          <h2 className="font-title text-title-sm">Findings</h2>
          <FindingsTable
            findings={detail.findings}
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
          <HostPortsTable ports={detail.host.ports} />
        </section>
        <section className="flex flex-col gap-4">
          <h2 className="font-title text-title-sm">Seen in these scans</h2>
          <HostScanHistoryTable history={detail.host.scan_history} />
        </section>
      </div>
    )
  }

  return (
    <div data-testid="host-detail" className="flex flex-col gap-12">
      {header}
      {body}
    </div>
  )
}

export default HostDetail
