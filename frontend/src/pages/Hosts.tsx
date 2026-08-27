import { type ReactNode, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  HOST_LIST_DEFAULT_SORT,
  HOSTS_PER_PAGE,
  listHosts,
  type HostListParams,
  type HostSortBy,
} from '@/api/hosts'
import { queryKeys } from '@/api/queryKeys'
import DataTable from '@/components/DataTable'
import EmptyState from '@/components/EmptyState'
import ErrorRetry from '@/components/ErrorRetry'
import PageHeader from '@/components/PageHeader'
import Pagination from '@/components/Pagination'
import { hostListColumns } from '@/pages/hosts/HostRow'

function Hosts() {
  const [page, setPage] = useState(1)
  const [sortBy, setSortBy] = useState<HostSortBy>(
    HOST_LIST_DEFAULT_SORT.sort_by,
  )
  const [sortOrder, setSortOrder] = useState<HostListParams['sort_order']>(
    HOST_LIST_DEFAULT_SORT.sort_order,
  )

  function handleSort(key: string) {
    const next = key as HostSortBy
    setSortOrder(
      next === sortBy
        ? sortOrder === 'desc'
          ? 'asc'
          : 'desc'
        : next === 'last_seen_at'
          ? 'desc'
          : 'asc',
    )
    setSortBy(next)
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

  let body: ReactNode

  if (query.isError) {
    body = (
      <ErrorRetry
        testId="hosts-error"
        message="Couldn't load the hosts."
        onRetry={() => {
          void query.refetch()
        }}
      />
    )
  } else if (query.isPending) {
    body = (
      <DataTable
        columns={hostListColumns}
        rows={[]}
        rowId={(host) => host.host_id}
        testId="hosts-table"
        caption="Host inventory"
        isPending
        sort={{ by: sortBy, order: sortOrder, onChange: handleSort }}
      />
    )
  } else if (query.data.total === 0) {
    body = (
      <EmptyState
        testId="hosts-blank"
        heading="No hosts yet."
        body="Once a scan runs, every device Dmitri finds on your network shows up here. Scanning is set up on the Pi itself."
      />
    )
  } else {
    body = (
      <div className="flex flex-col gap-4">
        <DataTable
          columns={hostListColumns}
          rows={query.data.data}
          rowId={(host) => host.host_id}
          testId="hosts-table"
          caption="Host inventory"
          sort={{ by: sortBy, order: sortOrder, onChange: handleSort }}
          rowAction={{
            kind: 'link',
            to: (host) => `/hosts/${host.host_id}`,
            label: (host) => `Open ${host.hostname || host.ip}`,
          }}
        />
        <Pagination
          page={page}
          perPage={HOSTS_PER_PAGE}
          total={query.data.total}
          onPageChange={setPage}
          testId="hosts"
        />
      </div>
    )
  }

  return (
    <div data-testid="hosts-page" className="flex flex-col gap-12">
      <PageHeader
        title="Hosts"
        subtitle="Every device Dmitri has found on your network."
      />
      {body}
    </div>
  )
}

export default Hosts
