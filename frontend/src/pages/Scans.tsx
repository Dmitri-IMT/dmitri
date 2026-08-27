import { type ReactNode, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/api/queryKeys'
import { listScans, SCAN_LIST_SORT, SCANS_PER_PAGE } from '@/api/scans'
import DataTable from '@/components/DataTable'
import EmptyState from '@/components/EmptyState'
import ErrorRetry from '@/components/ErrorRetry'
import PageHeader from '@/components/PageHeader'
import Pagination from '@/components/Pagination'
import { scanListColumns } from '@/pages/scans/ScanRow'

function Scans() {
  const [page, setPage] = useState(1)
  const params = {
    page,
    per_page: SCANS_PER_PAGE,
    ...SCAN_LIST_SORT,
  }
  const query = useQuery({
    queryKey: queryKeys.scans.list(params),
    queryFn: () => listScans(params),
  })

  let body: ReactNode

  if (query.isError) {
    body = (
      <ErrorRetry
        testId="scans-error"
        message="Couldn't load the scans."
        onRetry={() => {
          void query.refetch()
        }}
      />
    )
  } else if (query.isPending) {
    body = (
      <DataTable
        columns={scanListColumns}
        rows={[]}
        rowId={(scan) => scan.scan_id}
        testId="scans-table"
        caption="Scan run log"
        isPending
      />
    )
  } else if (query.data.total === 0) {
    body = (
      <EmptyState
        testId="scans-blank"
        heading="No scans yet."
        body="Dmitri scans your network for devices and known vulnerabilities. Every scan you run shows up here. Scanning is set up on the Pi itself."
      />
    )
  } else {
    body = (
      <div className="flex flex-col gap-4">
        <DataTable
          columns={scanListColumns}
          rows={query.data.data}
          rowId={(scan) => scan.scan_id}
          testId="scans-table"
          caption="Scan run log"
          rowAction={{
            kind: 'link',
            to: (scan) => `/scans/${scan.scan_id}`,
            label: (scan) => `Open scan ${scan.scan_id}`,
          }}
        />
        <Pagination
          page={page}
          perPage={SCANS_PER_PAGE}
          total={query.data.total}
          onPageChange={setPage}
          testId="scans"
        />
      </div>
    )
  }

  return (
    <div data-testid="scans-page" className="flex flex-col gap-12">
      <PageHeader title="Scans" />
      {body}
    </div>
  )
}

export default Scans
