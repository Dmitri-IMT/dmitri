import type { ReactElement } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import DataTable, {
  type DataTableColumn,
  type DataTableRowAction,
  type DataTableSort,
} from '@/components/DataTable'
import EmptyState from '@/components/EmptyState'
import ErrorRetry from '@/components/ErrorRetry'
import Pagination from '@/components/Pagination'

type ListPage<Row> = { data: Row[]; total: number }

export type ListSurfaceProps<Row, SortKey extends string = never> = {
  testId: string
  query: UseQueryResult<ListPage<Row>>
  columns: DataTableColumn<Row, SortKey>[]
  rowId: (row: Row) => string
  caption: string
  errorMessage: string
  empty: { heading: string; body: string }
  rowAction: DataTableRowAction<Row>
  sort?: DataTableSort<SortKey>
  page: number
  perPage: number
  onPageChange: (page: number) => void
}

function ListSurface<Row, SortKey extends string = never>({
  testId,
  query,
  columns,
  rowId,
  caption,
  errorMessage,
  empty,
  rowAction,
  sort,
  page,
  perPage,
  onPageChange,
}: ListSurfaceProps<Row, SortKey>): ReactElement {
  const table = {
    columns,
    rowId,
    testId: `${testId}-table`,
    caption,
    sort,
  }

  if (query.isError) {
    return (
      <ErrorRetry
        testId={`${testId}-error`}
        message={errorMessage}
        onRetry={() => {
          void query.refetch()
        }}
      />
    )
  }

  if (query.isPending) return <DataTable {...table} rows={[]} isPending />

  if (query.data.total === 0) {
    return (
      <EmptyState
        testId={`${testId}-blank`}
        heading={empty.heading}
        body={empty.body}
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <DataTable {...table} rows={query.data.data} rowAction={rowAction} />
      <Pagination
        page={page}
        perPage={perPage}
        total={query.data.total}
        onPageChange={onPageChange}
        testId={testId}
      />
    </div>
  )
}

export default ListSurface
