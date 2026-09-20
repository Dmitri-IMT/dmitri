import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/api/queryKeys'
import { listScans, SCAN_LIST_SORT, SCANS_PER_PAGE } from '@/api/scans'
import { FirstScanCta, FirstScanNote } from '@/components/FirstScanCta'
import ListSurface from '@/components/ListSurface'
import PageHeader from '@/components/PageHeader'
import { scanListColumns } from '@/pages/scans/scanListColumns'
import useI18n from '@/i18n/useI18n'

function Scans() {
  const [page, setPage] = useState(1)
  const { t } = useI18n()
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
      <PageHeader title={t('scans.title')} />
      <ListSurface
        testId="scans"
        query={query}
        columns={scanListColumns(t)}
        rowId={(scan) => scan.scan_id}
        caption={t('scans.caption')}
        errorMessage={t('scans.error')}
        empty={{
          heading: t('scans.emptyHeading'),
          body: t('scans.emptyBody'),
          action: <FirstScanCta />,
          note: <FirstScanNote />,
        }}
        rowAction={{
          kind: 'link',
          to: (scan) => `/scans/${scan.scan_id}`,
          label: (scan) => t('scans.open', { id: scan.scan_id }),
        }}
        pagination={{
          page,
          perPage: SCANS_PER_PAGE,
          total: query.data?.total ?? 0,
          onPageChange: setPage,
          label: t('scans.pages'),
        }}
      />
    </div>
  )
}

export default Scans
