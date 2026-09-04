import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/api/queryKeys'
import { listScans, SCAN_LIST_SORT, SCANS_PER_PAGE } from '@/api/scans'
import { FirstScanCta, FirstScanNote } from '@/components/FirstScanCta'
import ListSurface from '@/components/ListSurface'
import PageHeader from '@/components/PageHeader'
import { scanListColumns } from '@/pages/scans/scanListColumns'

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

  return (
    <div data-testid="scans-page" className="flex flex-col gap-12">
      <PageHeader title="Scans" />
      <ListSurface
        testId="scans"
        query={query}
        columns={scanListColumns}
        rowId={(scan) => scan.scan_id}
        caption="Scan run log"
        errorMessage="Couldn't load the scans."
        empty={{
          heading: 'No scans yet',
          body: 'Your first scan finds the machines on your network and what needs fixing.',
          action: <FirstScanCta />,
          note: <FirstScanNote />,
        }}
        rowAction={{
          kind: 'link',
          to: (scan) => `/scans/${scan.scan_id}`,
          label: (scan) => `Open scan ${scan.scan_id}`,
        }}
        page={page}
        perPage={SCANS_PER_PAGE}
        onPageChange={setPage}
      />
    </div>
  )
}

export default Scans
