import type { ReactElement, ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import DataTable, {
  type DataTableCollapsedGroup,
  type DataTableColumn,
  type DataTableRowAction,
  type DataTableRowTone,
  type DataTableSort,
} from '@/components/DataTable'
import EmptyState from '@/components/EmptyState'
import ErrorRetry from '@/components/ErrorRetry'
import Pagination from '@/components/Pagination'

type ListPage<Row> = { data: Row[]; total?: number }

export type ListSurfaceProps<Row, SortKey extends string = never> = {
  testId: string
  query: UseQueryResult<ListPage<Row>>
  columns: DataTableColumn<Row, SortKey>[]
  rowId: (row: Row) => string
  caption: string
  errorMessage: string
  empty: {
    heading: string
    body: string
    action?: ReactNode
    note?: ReactNode
  }
  rowAction: DataTableRowAction<Row>
  rowTone?: (row: Row) => DataTableRowTone
  sort?: DataTableSort<SortKey>
  partitionRows?: (rows: Row[]) => {
    rows: Row[]
    collapsedGroup?: DataTableCollapsedGroup<Row>
  }
  pagination?: {
    page: number
    perPage: number
    total: number
    onPageChange: (page: number) => void
  }
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
  rowTone,
  sort,
  partitionRows,
  pagination,
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

  const isEmpty = (query.data.total ?? query.data.data.length) === 0

  if (isEmpty) {
    return (
      <EmptyState
        testId={`${testId}-blank`}
        heading={empty.heading}
        body={empty.body}
        action={empty.action}
        note={empty.note}
      />
    )
  }

  const selected = query.data.data
  const partitioned = partitionRows
    ? partitionRows(selected)
    : { rows: selected }

  return (
    <div className="flex flex-col gap-4">
      <DataTable
        {...table}
        rows={partitioned.rows}
        rowAction={rowAction}
        rowTone={rowTone}
        collapsedGroup={partitioned.collapsedGroup}
      />
      {pagination && (
        <Pagination
          page={pagination.page}
          perPage={pagination.perPage}
          total={pagination.total}
          onPageChange={pagination.onPageChange}
          testId={testId}
        />
      )}
    </div>
  )
}

export default ListSurface
