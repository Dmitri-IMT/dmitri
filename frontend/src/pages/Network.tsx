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
import Pagination from '@/components/Pagination'
import Timestamp from '@/components/Timestamp'
import { Button } from '@/components/ui/button'
import { hostListColumns } from '@/pages/hosts/hostListColumns'
import type { components } from '@/types/openapi'

type HostSummary = components['schemas']['HostSummary']

function Network() {
  const now = new Date()
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
  const quietParams: HostListParams = {
    ...params,
    page: quietPage,
    group: 'quiet',
  }
  const query = useQuery({
    queryKey: queryKeys.hosts.list(params),
    queryFn: () => listHosts(params),
  })
  const quietQuery = useQuery({
    queryKey: queryKeys.hosts.list(quietParams),
    queryFn: () => listHosts(quietParams),
    enabled: isQuietOpen,
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
        title="Network"
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
        columns={hostListColumns(now, false)}
        rowId={(host) => host.host_id}
        caption="Machines on your network"
        errorMessage="Couldn't load your network."
        empty={{
          heading: 'No machines yet',
          body: 'Your first scan finds the machines on your network and what needs fixing.',
          action: <FirstScanCta />,
          note: <FirstScanNote />,
        }}
        sort={{ by: sortBy, order: sortOrder, onChange: handleSort }}
        emptyRow={
          <span
            data-testid="network-no-active"
            className="text-muted-foreground"
          >
            No machines seen in the last 7 days.
          </span>
        }
        collapsedGroup={{
          rows: quietQuery.data?.data ?? [],
          count: quietTotal,
          label: (count) => `Not seen recently (${count})`,
          testId: 'network-quiet',
          tone: 'muted',
          isOpen: isQuietOpen,
          columns: hostListColumns(now, true),
          isPending: quietQuery.isPending,
          error: quietQuery.isError ? (
            <span className="flex items-center gap-4">
              <span
                data-testid="network-quiet-error"
                className="text-muted-foreground"
              >
                Couldn&apos;t load the machines you haven&apos;t seen recently.
              </span>
              <Button
                type="button"
                variant="link"
                data-testid="network-quiet-error-retry"
                className="h-auto rounded-none px-0 py-0 text-caption-md font-normal"
                onClick={() => {
                  void quietQuery.refetch()
                }}
              >
                Retry
              </Button>
            </span>
          ) : undefined,
          footer: (
            <Pagination
              page={quietPage}
              perPage={HOSTS_PER_PAGE}
              total={quietQuery.data?.total ?? 0}
              onPageChange={setQuietPage}
              testId="network-quiet"
              label="Quiet machine pages"
            />
          ),
          onOpenChange: (isOpen) => {
            setIsQuietOpen(isOpen)
            if (!isOpen) setQuietPage(1)
          },
        }}
        rowAction={{
          kind: 'link',
          to: (host) => `/network/${host.host_id}`,
          label: (host) => `Open ${host.hostname || host.ip}`,
        }}
        pagination={{
          page,
          perPage: HOSTS_PER_PAGE,
          total: query.data?.total ?? 0,
          onPageChange: setPage,
          label: 'Machine pages',
        }}
      />
    </div>
  )
}

export default Network
