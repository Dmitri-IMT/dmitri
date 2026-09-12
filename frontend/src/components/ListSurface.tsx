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

type ListSurfaceEmpty =
  | {
      kind?: 'page'
      heading: string
      body: string
      action?: ReactNode
      note?: ReactNode
    }
  | { kind: 'section'; body: string }

export type ListSurfaceProps<Row, SortKey extends string = never> = {
  testId: string
  query: UseQueryResult<ListPage<Row>>
  columns: DataTableColumn<Row, SortKey>[]
  rowId: (row: Row) => string
  caption: string
  errorMessage: string
  empty: ListSurfaceEmpty
  rowAction: DataTableRowAction<Row>
  rowTone?: (row: Row) => DataTableRowTone
  sort?: DataTableSort<SortKey>
  collapsedGroup?: DataTableCollapsedGroup<Row, SortKey>
  emptyRow?: ReactNode
  pagination?: {
    page: number
    perPage: number
    total: number
    onPageChange: (page: number) => void
    label: string
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
  collapsedGroup,
  emptyRow,
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

  const isEmpty =
    (query.data.total ?? query.data.data.length) === 0 && !collapsedGroup?.count

  if (isEmpty) {
    if (empty.kind === 'section') {
      return (
        <p data-testid={`${testId}-blank`} className="text-body-md">
          {empty.body}
        </p>
      )
    }
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

  return (
    <div className="flex flex-col gap-4">
      <DataTable
        {...table}
        rows={query.data.data}
        empty={emptyRow}
        rowAction={rowAction}
        rowTone={rowTone}
        collapsedGroup={collapsedGroup}
      />
      {pagination && (
        <Pagination
          page={pagination.page}
          perPage={pagination.perPage}
          total={pagination.total}
          onPageChange={pagination.onPageChange}
          testId={testId}
          label={pagination.label}
        />
      )}
    </div>
  )
}

export default ListSurface
