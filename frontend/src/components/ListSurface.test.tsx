import { useState } from 'react'
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
  collapsedGroup,
  emptyRow,
  pagination,
  empty,
}: {
  query: UseQueryResult<{ data: Row[]; total?: number }>
  collapsedGroup?: Omit<
    NonNullable<ListSurfaceProps<Row>['collapsedGroup']>,
    'isOpen' | 'onOpenChange'
  >
  emptyRow?: ListSurfaceProps<Row>['emptyRow']
  pagination?: ListSurfaceProps<Row>['pagination']
  empty?: ListSurfaceProps<Row>['empty']
}) {
  const [isGroupOpen, setIsGroupOpen] = useState(false)

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
      collapsedGroup={
        collapsedGroup && {
          ...collapsedGroup,
          isOpen: isGroupOpen,
          onOpenChange: setIsGroupOpen,
        }
      }
      emptyRow={emptyRow}
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
          total: 40,
          onPageChange: () => {},
          label: 'Example pages',
        }}
      />,
    )

    expect(screen.getByTestId('example-pagination')).toBeVisible()
    expect(
      screen.getByRole('navigation', { name: 'Example pages' }),
    ).toBeVisible()
  })

  it('passes a collapsed group through to DataTable', () => {
    renderWithProviders(
      <ListHarness
        query={readyQuery({ data: [rows[0]] })}
        collapsedGroup={{
          rows: [rows[1]],
          count: 1,
          label: (count) => `Grouped (${count})`,
          testId: 'example-group',
        }}
      />,
    )

    expect(screen.getByTestId('example-table-row-one')).toBeVisible()
    expect(
      screen.queryByTestId('example-table-row-two'),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId('example-group-group')).toBeVisible()
  })

  it('renders the table with an empty row rather than the blank state when only a group has rows', () => {
    renderWithProviders(
      <ListHarness
        query={readyQuery({ data: [], total: 0 })}
        emptyRow={<span data-testid="example-no-rows">Nothing active.</span>}
        collapsedGroup={{
          rows: [rows[1]],
          count: 1,
          label: (count) => `Grouped (${count})`,
          testId: 'example-group',
        }}
      />,
    )

    expect(screen.queryByTestId('example-blank')).not.toBeInTheDocument()
    expect(screen.getByTestId('example-no-rows')).toBeVisible()
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
