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
import { isQuietHost, partitionQuietHosts } from '@/lib/hostLastSeen'
import { hostListColumns } from '@/pages/hosts/hostListColumns'
import type { components } from '@/types/openapi'

type HostSummary = components['schemas']['HostSummary']
type HostListResponse = components['schemas']['HostListResponse']

function Network() {
  const now = new Date()
  const [page, setPage] = useState(1)
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

  const params = {
    page,
    per_page: HOSTS_PER_PAGE,
    sort_by: sortBy,
    sort_order: sortOrder,
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
      <ListSurface<HostSummary, HostListResponse, HostSortBy>
        testId="network"
        query={query}
        selectRows={(data) => data.data}
        isEmpty={(data) => data.total === 0}
        columns={hostListColumns(now)}
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
        partitionRows={(hosts) => {
          const { recent, quiet } = partitionQuietHosts(hosts, now)
          return {
            rows: recent,
            collapsedGroup: quiet.length
              ? {
                  rows: quiet,
                  label: (count) => `Not seen recently (${count})`,
                  testId: 'network-quiet',
                }
              : undefined,
          }
        }}
        rowAction={{
          kind: 'link',
          to: (host) => `/network/${host.host_id}`,
          label: (host) => `Open ${host.hostname || host.ip}`,
        }}
        rowTone={(host) =>
          isQuietHost(host.last_seen_at, now) ? 'muted' : undefined
        }
        pagination={{
          page,
          perPage: HOSTS_PER_PAGE,
          onPageChange: setPage,
          total: (data) => data.total,
        }}
      />
    </div>
  )
}

export default Network
