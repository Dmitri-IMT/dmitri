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
import { FirstScanCta, FirstScanNote } from '@/components/FirstScanCta'
import ListSurface from '@/components/ListSurface'
import PageHeader from '@/components/PageHeader'
import { hostListColumns } from '@/pages/hosts/hostListColumns'

function Hosts() {
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

  return (
    <div data-testid="hosts-page" className="flex flex-col gap-12">
      <PageHeader
        title="Hosts"
        subtitle="Every device Dmitri has found on your network."
      />
      <ListSurface
        testId="hosts"
        query={query}
        columns={hostListColumns}
        rowId={(host) => host.host_id}
        caption="Host inventory"
        errorMessage="Couldn't load the hosts."
        empty={{
          heading: 'No hosts yet.',
          body: 'Once a scan runs, every device Dmitri finds on your network shows up here.',
          action: <FirstScanCta />,
          note: <FirstScanNote />,
        }}
        sort={{ by: sortBy, order: sortOrder, onChange: handleSort }}
        rowAction={{
          kind: 'link',
          to: (host) => `/hosts/${host.host_id}`,
          label: (host) => `Open ${host.hostname || host.ip}`,
        }}
        page={page}
        perPage={HOSTS_PER_PAGE}
        onPageChange={setPage}
      />
    </div>
  )
}

export default Hosts
