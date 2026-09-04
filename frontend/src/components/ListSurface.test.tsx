import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { UseQueryResult } from '@tanstack/react-query'
import ListSurface, { type ListSurfaceProps } from '@/components/ListSurface'
import type { DataTableColumn } from '@/components/DataTable'
import { renderWithProviders } from '@/test/renderWithProviders'

type Row = { id: string; name: string }

const columns: DataTableColumn<Row>[] = [
  {
    key: 'name',
    label: 'Name',
    width: 'w-full',
    render: (row) => row.name,
  },
]

const rows: Row[] = [
  { id: 'one', name: 'First' },
  { id: 'two', name: 'Second' },
]

function readyQuery(data: {
  data: Row[]
  total?: number
}): UseQueryResult<{ data: Row[]; total?: number }> {
  return {
    isError: false,
    isPending: false,
    data,
    refetch: async () => ({}) as never,
  } as unknown as UseQueryResult<{ data: Row[]; total?: number }>
}

function ListHarness({
  query,
  partitionRows,
  pagination,
  empty,
}: {
  query: UseQueryResult<{ data: Row[]; total?: number }>
  partitionRows?: ListSurfaceProps<Row>['partitionRows']
  pagination?: ListSurfaceProps<Row>['pagination']
  empty?: ListSurfaceProps<Row>['empty']
}) {
  return (
    <ListSurface
      testId="example"
      query={query}
      columns={columns}
      rowId={(row) => row.id}
      caption="Example rows"
      errorMessage="Couldn't load."
      empty={empty ?? { heading: 'Nothing here', body: 'No rows yet.' }}
      rowAction={{
        kind: 'link',
        to: (row) => `/rows/${row.id}`,
        label: (row) => `Open ${row.name}`,
      }}
      partitionRows={partitionRows}
      pagination={pagination}
    />
  )
}

describe('ListSurface', () => {
  it('renders a table without pagination when pagination is omitted', () => {
    renderWithProviders(<ListHarness query={readyQuery({ data: rows })} />)

    expect(screen.getByTestId('example-table')).toBeVisible()
    expect(screen.queryByTestId('example-pagination')).not.toBeInTheDocument()
  })

  it('renders pagination when provided', () => {
    renderWithProviders(
      <ListHarness
        query={readyQuery({ data: rows, total: 40 })}
        pagination={{
          page: 1,
          perPage: 20,
          onPageChange: () => {},
        }}
      />,
    )

    expect(screen.getByTestId('example-pagination')).toBeVisible()
  })

  it('passes partitioned rows and collapsedGroup to DataTable', () => {
    renderWithProviders(
      <ListHarness
        query={readyQuery({ data: rows })}
        partitionRows={(all) => ({
          rows: [all[0]],
          collapsedGroup: {
            rows: [all[1]],
            label: (count) => `Grouped (${count})`,
            testId: 'example-group',
          },
        })}
      />,
    )

    expect(screen.getByTestId('example-table-row-one')).toBeVisible()
    expect(
      screen.queryByTestId('example-table-row-two'),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId('example-group-group')).toBeVisible()
  })

  it('renders empty.note when the list payload is empty', () => {
    renderWithProviders(
      <ListHarness
        query={readyQuery({ data: [], total: 0 })}
        empty={{
          heading: 'Nothing here',
          body: 'No rows yet.',
          note: <p data-testid="empty-note">Ask your admin.</p>,
        }}
      />,
    )

    expect(screen.getByTestId('example-blank')).toBeVisible()
    expect(screen.getByTestId('empty-note')).toBeVisible()
  })
})
