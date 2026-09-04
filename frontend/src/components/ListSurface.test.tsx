import type { ReactElement } from 'react'
import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { UseQueryResult } from '@tanstack/react-query'
import ListSurface, {
  type ListSurfaceProps,
} from '@/components/ListSurface'
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

function readyQuery<Data>(data: Data): UseQueryResult<Data> {
  return {
    isError: false,
    isPending: false,
    data,
    refetch: async () => ({}) as never,
  } as unknown as UseQueryResult<Data>
}

function ListHarness({
  query,
  partitionRows,
  pagination,
  blank,
}: {
  query: UseQueryResult<{ items: Row[]; total?: number }>
  partitionRows?: ListSurfaceProps<Row, { items: Row[]; total?: number }>['partitionRows']
  pagination?: ListSurfaceProps<Row, { items: Row[]; total?: number }>['pagination']
  blank?: ReactElement
}) {
  return (
    <ListSurface
      testId="example"
      query={query}
      selectRows={(data) => data.items}
      isEmpty={(data) => data.items.length === 0}
      columns={columns}
      rowId={(row) => row.id}
      caption="Example rows"
      errorMessage="Couldn't load."
      empty={{ heading: 'Nothing here', body: 'No rows yet.' }}
      blank={blank}
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
    renderWithProviders(
      <ListHarness query={readyQuery({ items: rows })} />,
    )

    expect(screen.getByTestId('example-table')).toBeVisible()
    expect(screen.queryByTestId('example-pagination')).not.toBeInTheDocument()
  })

  it('renders pagination when provided', () => {
    renderWithProviders(
      <ListHarness
        query={readyQuery({ items: rows, total: 40 })}
        pagination={{
          page: 1,
          perPage: 20,
          onPageChange: () => {},
          total: (data) => data.total ?? 0,
        }}
      />,
    )

    expect(screen.getByTestId('example-pagination')).toBeVisible()
  })

  it('passes partitioned rows and collapsedGroup to DataTable', () => {
    renderWithProviders(
      <ListHarness
        query={readyQuery({ items: rows })}
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

  it('renders blank instead of EmptyState when blank is provided', () => {
    renderWithProviders(
      <ListHarness
        query={readyQuery({ items: [] })}
        blank={<p data-testid="custom-blank">Custom blank</p>}
      />,
    )

    expect(screen.getByTestId('custom-blank')).toBeVisible()
    expect(screen.queryByTestId('example-blank')).not.toBeInTheDocument()
  })
})
