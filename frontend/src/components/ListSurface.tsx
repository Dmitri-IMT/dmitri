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

export type ListSurfaceProps<Row, Data, SortKey extends string = never> = {
  testId: string
  query: UseQueryResult<Data>
  selectRows: (data: Data) => Row[]
  isEmpty: (data: Data) => boolean
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
  blank?: ReactNode
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
    onPageChange: (page: number) => void
    total: (data: Data) => number
  }
}

function ListSurface<Row, Data, SortKey extends string = never>({
  testId,
  query,
  selectRows,
  isEmpty,
  columns,
  rowId,
  caption,
  errorMessage,
  empty,
  blank,
  rowAction,
  rowTone,
  sort,
  partitionRows,
  pagination,
}: ListSurfaceProps<Row, Data, SortKey>): ReactElement {
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

  if (isEmpty(query.data)) {
    if (blank) return <>{blank}</>
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

  const selected = selectRows(query.data)
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
          total={pagination.total(query.data)}
          onPageChange={pagination.onPageChange}
          testId={testId}
        />
      )}
    </div>
  )
}

export default ListSurface
