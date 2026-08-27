import { type ReactNode, useState } from 'react'
import { Link, useParams } from 'react-router'
import ErrorRetry from '@/components/ErrorRetry'
import PageHeader from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { useHostDetail } from '@/hooks/useHostDetail'
import HostFindingsTable from '@/pages/hosts/HostFindingsTable'
import HostIdentity from '@/pages/hosts/HostIdentity'
import HostPortsTable from '@/pages/hosts/HostPortsTable'
import HostScanHistoryTable from '@/pages/hosts/HostScanHistoryTable'

function HostDetail() {
  const { hostId = '' } = useParams()
  const [openFindingId, setOpenFindingId] = useState<string | null>(null)
  const detail = useHostDetail(hostId)

  let header: ReactNode = <PageHeader title="Host" />
  let body: ReactNode

  if (detail.state === 'notFound') {
    body = (
      <div className="flex flex-col items-center gap-6 py-16 text-center">
        <p
          data-testid="host-detail-not-found"
          className="font-title text-title-sm"
        >
          That host doesn&apos;t exist.
        </p>
        <Button asChild variant="outline">
          <Link to="/hosts" data-testid="host-detail-back">
            Back to hosts
          </Link>
        </Button>
      </div>
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
          <HostFindingsTable
            findings={detail.findings}
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
