import { type ReactNode, useState } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/api/queryKeys'
import { getScan } from '@/api/scans'
import ErrorRetry from '@/components/ErrorRetry'
import NotFoundNotice from '@/components/NotFoundNotice'
import PageHeader from '@/components/PageHeader'
import { readDetailState } from '@/lib/detailState'
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

  const detail = readDetailState(scanId, query)

  let header: ReactNode = <PageHeader title="Scan" />
  let body: ReactNode

  if (detail.state === 'notFound') {
    body = (
      <NotFoundNotice
        testId="scan-detail"
        message="That scan doesn't exist."
        backTo="/scans"
        backLabel="Back to scans"
      />
    )
  } else if (detail.state === 'error') {
    body = (
      <ErrorRetry
        testId="scan-detail-error"
        message="Couldn't load this scan."
        onRetry={detail.retry}
      />
    )
  } else if (detail.state === 'loading') {
    body = null
  } else if (detail.data.status === 'failed') {
    header = <ScanDetailHeader scan={detail.data} />
    body = <ScanFailedNotice errorCode={detail.data.error_code} />
  } else if (isUnfinished(detail.data.status)) {
    header = <ScanDetailHeader scan={detail.data} />
    body = (
      <ScanUnfinishedNotice
        onCheck={() => {
          void query.refetch()
        }}
        isChecking={query.isFetching}
      />
    )
  } else {
    const scan = detail.data
    header = <ScanDetailHeader scan={scan} />
    body = (
      <div className="flex flex-col gap-12">
        <section className="flex flex-col gap-4">
          <h2 className="font-title text-title-sm">Findings</h2>
          <FindingsTable
            findings={scan.findings}
            hosts={scan.hosts}
            testId="findings-table"
            caption="Findings for this scan"
            emptyTestId="scan-no-findings"
            emptyCopy="No findings. Every host in this scan came back clean."
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
