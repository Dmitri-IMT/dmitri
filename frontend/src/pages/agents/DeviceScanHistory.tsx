import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listScans, SCAN_LIST_SORT, SCANS_PER_PAGE } from '@/api/scans'
import { queryKeys } from '@/api/queryKeys'
import ListSurface from '@/components/ListSurface'
import { deviceScanHistoryColumns } from '@/pages/agents/deviceScanHistoryColumns'

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

  return (
    <section data-testid="device-scan-history" className="flex flex-col gap-4">
      <h2 className="text-title-sm">Scan history</h2>
      <ListSurface
        testId="device-scan-history"
        query={query}
        columns={deviceScanHistoryColumns}
        rowId={(scan) => scan.scan_id}
        caption="Scans from this box"
        errorMessage="Couldn't load this box's scan history."
        empty={{ kind: 'section', body: 'No scans from this box yet.' }}
        rowAction={{
          kind: 'link',
          to: (scan) => `/scans/${scan.scan_id}`,
          label: (scan) => `Open scan ${scan.scan_id}`,
        }}
        pagination={{
          page,
          perPage: SCANS_PER_PAGE,
          total: query.data?.total ?? 0,
          onPageChange: setPage,
        }}
      />
    </section>
  )
}

export default DeviceScanHistory
