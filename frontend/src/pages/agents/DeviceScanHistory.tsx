import { useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listScans, SCAN_LIST_SORT, SCANS_PER_PAGE } from '@/api/scans'
import { queryKeys } from '@/api/queryKeys'
import DataTable from '@/components/DataTable'
import ErrorRetry from '@/components/ErrorRetry'
import Pagination from '@/components/Pagination'
import { deviceScanHistoryColumns } from '@/pages/agents/deviceScanHistoryColumns'
import type { components } from '@/types/openapi'

type ScanSummary = components['schemas']['ScanSummary']

const historyTable = {
  columns: deviceScanHistoryColumns,
  rowId: (scan: ScanSummary) => scan.scan_id,
  testId: 'device-scan-history-table',
  caption: 'Scans from this box',
}

function DeviceScanHistory({ agentId }: { agentId: string }) {
  const [page, setPage] = useState(1)
  const params = {
    agent_id: agentId,
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
        testId="device-scan-history-error"
        message="Couldn't load this box's scan history."
        actionLabel="Try again"
        onRetry={() => {
          void query.refetch()
        }}
      />
    )
  } else if (query.isPending) {
    body = (
      <div data-testid="device-scan-history-loading">
        <DataTable {...historyTable} rows={[]} isPending skeletonRows={3} />
      </div>
    )
  } else if ((query.data.total ?? query.data.data.length) === 0) {
    body = (
      <p data-testid="device-scan-history-blank" className="text-body-md">
        No scans from this box yet.
      </p>
    )
  } else {
    body = (
      <>
        <DataTable
          {...historyTable}
          rows={query.data.data}
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
          testId="device-scan-history"
        />
      </>
    )
  }

  return (
    <section
      data-testid="device-scan-history"
      className="flex flex-col gap-4"
    >
      <h2 className="text-title-sm">Scan history</h2>
      {body}
    </section>
  )
}

export default DeviceScanHistory
