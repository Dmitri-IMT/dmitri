import type { ReactElement } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  HOSTS_PER_PAGE,
  listHosts,
  type HostListParams,
  type HostSortBy,
} from '@/api/hosts'
import { queryKeys } from '@/api/queryKeys'
import type { DataTableGroupBody } from '@/components/DataTable'
import LoadingSkeleton from '@/components/LoadingSkeleton'
import Pagination from '@/components/Pagination'
import { Button } from '@/components/ui/button'
import { hostListColumns } from '@/pages/hosts/hostListColumns'
import type { components } from '@/types/openapi'
import useI18n from '@/i18n/useI18n'

type HostSummary = components['schemas']['HostSummary']

type QuietMachineGroupProps = {
  body: DataTableGroupBody<HostSummary, HostSortBy>
  now: Date
  sortBy: HostSortBy
  sortOrder: HostListParams['sort_order']
  page: number
  onPageChange: (page: number) => void
}

const SKELETON_ROWS = 3

/**
 * The open "Not seen recently" group on Network: its own read of the quiet
 * machines, its pager, and its loading and error rows. The page lives with the
 * caller, because the table remounts this group whenever the active list loads.
 */
function QuietMachineGroup({
  body,
  now,
  sortBy,
  sortOrder,
  page,
  onPageChange,
}: QuietMachineGroupProps): ReactElement {
  const { t } = useI18n()
  const params: HostListParams = {
    page,
    per_page: HOSTS_PER_PAGE,
    sort_by: sortBy,
    sort_order: sortOrder,
    group: 'quiet',
  }
  const query = useQuery({
    queryKey: queryKeys.hosts.list(params),
    queryFn: () => listHosts(params),
  })

  if (query.isPending) {
    return (
      <LoadingSkeleton
        id={body.id}
        testId="network-quiet-loading"
        rows={SKELETON_ROWS}
        columns={body.columnCount}
      />
    )
  }

  if (query.isError) {
    return (
      <tbody id={body.id}>
        {body.spanningRow(
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
                void query.refetch()
              }}
            >
              Retry
            </Button>
          </span>,
        )}
      </tbody>
    )
  }

  return (
    <tbody id={body.id}>
      {body.renderRows(query.data.data, hostListColumns(now, true, t), 'muted')}
      {body.spanningRow(
        <Pagination
          page={page}
          perPage={HOSTS_PER_PAGE}
          total={query.data.total}
          onPageChange={onPageChange}
          testId="network-quiet"
          label="Quiet machine pages"
        />,
      )}
    </tbody>
  )
}

export default QuietMachineGroup
