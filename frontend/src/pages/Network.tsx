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
import DataTable from '@/components/DataTable'
import EmptyState from '@/components/EmptyState'
import ErrorRetry from '@/components/ErrorRetry'
import { FirstScanCta, FirstScanNote } from '@/components/FirstScanCta'
import PageHeader from '@/components/PageHeader'
import Pagination from '@/components/Pagination'
import Timestamp from '@/components/Timestamp'
import { isSilent } from '@/lib/silentDevice'
import { hostListColumns } from '@/pages/hosts/hostListColumns'
import type { components } from '@/types/openapi'

type HostSummary = components['schemas']['HostSummary']

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
  const rows = query.data?.data ?? []
  const quietRows = rows.filter((host) => isSilent(host.last_seen_at, now))
  const recentRows = rows.filter((host) => !isSilent(host.last_seen_at, now))
  const table = {
    columns: hostListColumns(now),
    rowId: (host: HostSummary) => host.host_id,
    testId: 'network-table',
    caption: 'Machines on your network',
    sort: { by: sortBy, order: sortOrder, onChange: handleSort },
  }

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
      {query.isError ? (
        <ErrorRetry
          testId="network-error"
          message="Couldn't load your network."
          onRetry={() => {
            void query.refetch()
          }}
        />
      ) : query.isPending ? (
        <DataTable {...table} rows={[]} isPending />
      ) : query.data.total === 0 ? (
        <EmptyState
          testId="network-blank"
          heading="No machines yet"
          body="Your first scan finds the machines on your network and what needs fixing."
          action={<FirstScanCta />}
          note={<FirstScanNote />}
        />
      ) : (
        <div className="flex flex-col gap-4">
          <DataTable
            {...table}
            rows={recentRows}
            rowAction={{
              kind: 'link',
              to: (host) => `/network/${host.host_id}`,
              label: (host) => `Open ${host.hostname || host.ip}`,
            }}
            rowTone={(host) =>
              isSilent(host.last_seen_at, now) ? 'muted' : undefined
            }
            collapsedGroup={{
              rows: quietRows,
              label: (count) => `Not seen recently (${count})`,
              testId: 'network-quiet',
            }}
          />
          <Pagination
            page={page}
            perPage={HOSTS_PER_PAGE}
            total={query.data.total}
            onPageChange={setPage}
            testId="network"
          />
        </div>
      )}
    </div>
  )
}

export default Network
