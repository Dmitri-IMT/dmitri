import { type ReactNode, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { readApiError } from '@/api/apiError'
import { queryKeys } from '@/api/queryKeys'
import { getScan } from '@/api/scans'
import ErrorRetry from '@/components/ErrorRetry'
import PageHeader from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { isUnfinished } from '@/lib/scanStatus'
import FindingsTable from '@/pages/scans/FindingsTable'
import ScanDetailHeader from '@/pages/scans/ScanDetailHeader'
import ScanFailedNotice from '@/pages/scans/ScanFailedNotice'
import ScanHostsTable from '@/pages/scans/ScanHostsTable'
import ScanUnfinishedNotice from '@/pages/scans/ScanUnfinishedNotice'

function ScanDetail() {
  const { scanId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const [openFindingId, setOpenFindingId] = useState<string | null>(() =>
    searchParams.get('finding'),
  )
  const [openHostId, setOpenHostId] = useState<string | null>(null)

  const query = useQuery({
    queryKey: queryKeys.scans.detail(scanId),
    queryFn: () => getScan(scanId),
    enabled: scanId !== '',
  })

  let header: ReactNode = <PageHeader title="Scan" />
  let body: ReactNode

  if (
    scanId === '' ||
    (query.isError && readApiError(query.error).status === 404)
  ) {
    body = (
      <div className="flex flex-col items-center gap-6 py-16 text-center">
        <p
          data-testid="scan-detail-not-found"
          className="font-title text-title-sm"
        >
          That scan doesn&apos;t exist.
        </p>
        <Button asChild variant="outline">
          <Link to="/scans" data-testid="scan-detail-back">
            Back to scans
          </Link>
        </Button>
      </div>
    )
  } else if (query.isError) {
    body = (
      <ErrorRetry
        testId="scan-detail-error"
        message="Couldn't load this scan."
        onRetry={() => {
          void query.refetch()
        }}
      />
    )
  } else if (query.isPending) {
    body = null
  } else if (query.data.status === 'failed') {
    header = <ScanDetailHeader scan={query.data} />
    body = <ScanFailedNotice errorCode={query.data.error_code} />
  } else if (isUnfinished(query.data.status)) {
    header = <ScanDetailHeader scan={query.data} />
    body = (
      <ScanUnfinishedNotice
        onCheck={() => {
          void query.refetch()
        }}
        isChecking={query.isFetching}
      />
    )
  } else {
    const scan = query.data
    header = <ScanDetailHeader scan={scan} />
    body = (
      <div className="flex flex-col gap-12">
        <section className="flex flex-col gap-4">
          <h2 className="font-title text-title-sm">Findings</h2>
          <FindingsTable
            findings={scan.findings}
            hosts={scan.hosts}
            openFindingId={openFindingId}
            onOpenFindingChange={setOpenFindingId}
          />
        </section>
        <section className="flex flex-col gap-4">
          <h2 className="font-title text-title-sm">Hosts</h2>
          <ScanHostsTable
            hosts={scan.hosts}
            openHostId={openHostId}
            onOpenHostChange={setOpenHostId}
          />
        </section>
      </div>
    )
  }

  return (
    <div data-testid="scan-detail" className="flex flex-col gap-12">
      {header}
      {body}
    </div>
  )
}

export default ScanDetail
