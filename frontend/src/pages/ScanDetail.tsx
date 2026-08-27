import { useState } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/api/queryKeys'
import { getScan } from '@/api/scans'
import ReadDetailGate from '@/components/ReadDetailGate'
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

  return (
    <ReadDetailGate
      testId="scan-detail"
      title="Scan"
      notFoundMessage="That scan doesn't exist."
      errorMessage="Couldn't load this scan."
      backTo="/scans"
      backLabel="Back to scans"
      detail={readDetailState(scanId, query)}
    >
      {(scan) => (
        <>
          <ScanDetailHeader scan={scan} />
          {scan.status === 'failed' ? (
            <ScanFailedNotice errorCode={scan.error_code} />
          ) : isUnfinished(scan.status) ? (
            <ScanUnfinishedNotice
              onCheck={() => {
                void query.refetch()
              }}
              isChecking={query.isFetching}
            />
          ) : (
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
          )}
        </>
      )}
    </ReadDetailGate>
  )
}

export default ScanDetail
