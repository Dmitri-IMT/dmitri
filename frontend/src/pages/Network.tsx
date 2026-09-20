import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  HOST_LIST_DEFAULT_SORT_BY,
  HOST_SORT_DEFAULT_ORDER,
  HOSTS_PER_PAGE,
  listHosts,
  type HostListParams,
  type HostSortBy,
} from '@/api/hosts'
import { queryKeys } from '@/api/queryKeys'
import { getLatestSuccessfulScan } from '@/api/scans'
import { FirstScanCta, FirstScanNote } from '@/components/FirstScanCta'
import ListSurface from '@/components/ListSurface'
import PageHeader from '@/components/PageHeader'
import Timestamp from '@/components/Timestamp'
import { hostListColumns } from '@/pages/hosts/hostListColumns'
import QuietMachineGroup from '@/pages/hosts/QuietMachineGroup'
import type { components } from '@/types/openapi'
import useI18n from '@/i18n/useI18n'

type HostSummary = components['schemas']['HostSummary']

function Network() {
  const now = new Date()
  const { t } = useI18n()
  const [page, setPage] = useState(1)
  const [quietPage, setQuietPage] = useState(1)
  const [isQuietOpen, setIsQuietOpen] = useState(false)
  const [sortBy, setSortBy] = useState<HostSortBy>(HOST_LIST_DEFAULT_SORT_BY)
  const [sortOrder, setSortOrder] = useState<HostListParams['sort_order']>(
    HOST_SORT_DEFAULT_ORDER[HOST_LIST_DEFAULT_SORT_BY],
  )

  function handleSort(key: HostSortBy) {
    setSortOrder(
      key === sortBy
        ? sortOrder === 'desc'
          ? 'asc'
          : 'desc'
        : HOST_SORT_DEFAULT_ORDER[key],
    )
    setSortBy(key)
    setPage(1)
  }

  const params: HostListParams = {
    page,
    per_page: HOSTS_PER_PAGE,
    sort_by: sortBy,
    sort_order: sortOrder,
    group: 'active',
  }
  const query = useQuery({
    queryKey: queryKeys.hosts.list(params),
    queryFn: () => listHosts(params),
  })
  const latestScanQuery = useQuery({
    queryKey: queryKeys.scans.latest('completed'),
    queryFn: getLatestSuccessfulScan,
  })

  const total = query.data?.total
  const quietTotal = query.data?.quiet_total ?? 0
  const latestScan = latestScanQuery.data

  return (
    <div data-testid="network-page" className="flex flex-col gap-12">
      <PageHeader
        title={t('network.title')}
        subtitle={
          total === undefined ? undefined : (
            <>
              {total === 1 ? '1 machine' : `${total} machines`}
              {latestScan && (
                <>
                  {' · last scan '}
                  <Timestamp value={latestScan.timestamp} now={now} />
                </>
              )}
            </>
          )
        }
      />
      <ListSurface<HostSummary, HostSortBy>
        testId="network"
        query={query}
        columns={hostListColumns(now, false, t)}
        rowId={(host) => host.host_id}
        caption={t('network.caption')}
        errorMessage={t('network.error')}
        empty={{
          heading: t('network.emptyHeading'),
          body: t('network.emptyBody'),
          action: <FirstScanCta />,
          note: <FirstScanNote />,
        }}
        sort={{ by: sortBy, order: sortOrder, onChange: handleSort }}
        emptyRow={
          <span
            data-testid="network-no-active"
            className="text-muted-foreground"
          >
            {t('network.emptyActive')}
          </span>
        }
        collapsedGroup={{
          count: quietTotal,
          label: (count) => t('network.quiet', { count }),
          testId: 'network-quiet',
          isOpen: isQuietOpen,
          onOpenChange: (isOpen) => {
            setIsQuietOpen(isOpen)
            if (!isOpen) setQuietPage(1)
          },
          content: (body) => (
            <QuietMachineGroup
              body={body}
              now={now}
              sortBy={sortBy}
              sortOrder={sortOrder}
              page={quietPage}
              onPageChange={setQuietPage}
            />
          ),
        }}
        rowAction={{
          kind: 'link',
          to: (host) => `/network/${host.host_id}`,
          label: (host) =>
            t('network.open', { host: host.hostname || host.ip }),
        }}
        pagination={{
          page,
          perPage: HOSTS_PER_PAGE,
          total: query.data?.total ?? 0,
          onPageChange: setPage,
          label: t('network.pages'),
        }}
      />
    </div>
  )
}

export default Network
