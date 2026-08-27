import { useState } from 'react'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Link } from 'react-router'
import DataTable, {
  type DataTableColumn,
  type DataTableRowAction,
} from '@/components/DataTable'
import LocationProbe from '@/test/LocationProbe'
import { renderWithProviders } from '@/test/renderWithProviders'

type Row = {
  id: string
  name: string
  detail: string
}

const rows: Row[] = [
  { id: 'one', name: 'First row', detail: 'First detail' },
  { id: 'two', name: 'Second row', detail: 'Second detail' },
]

const columns: DataTableColumn<Row, 'name'>[] = [
  {
    key: 'name',
    label: 'Name',
    width: 'w-1/2',
    render: (row) => row.name,
    sortable: true,
  },
  {
    key: 'detail',
    label: 'Detail',
    width: 'w-1/2',
    render: (row) => row.detail,
  },
]

const baseProps = {
  columns,
  rows,
  rowId: (row: Row) => row.id,
  testId: 'example-table',
  caption: 'Example rows',
}

describe('DataTable', () => {
  it('renders its caption, uppercase headings, and named column widths', () => {
    const { container } = renderWithProviders(<DataTable {...baseProps} />)

    expect(screen.getByRole('table', { name: 'Example rows' })).toBeVisible()
    expect(screen.getByRole('columnheader', { name: 'Name' })).toHaveClass(
      'uppercase',
    )
    expect(screen.getByRole('columnheader', { name: 'Detail' })).toHaveClass(
      'uppercase',
    )
    expect(container.querySelectorAll('col')[0]).toHaveClass('w-1/2')
  })

  it('keeps headings while pending, ignores rows, and uses the requested skeleton count', () => {
    renderWithProviders(<DataTable {...baseProps} isPending skeletonRows={2} />)

    expect(screen.getByRole('columnheader', { name: 'Name' })).toBeVisible()
    expect(screen.queryByText('First row')).not.toBeInTheDocument()
    expect(screen.getAllByRole('row')).toHaveLength(3)
  })

  it('renders empty content only for an empty, non-pending body', () => {
    const { unmount } = renderWithProviders(
      <DataTable {...baseProps} rows={[]} empty={<p>No rows.</p>} />,
    )

    expect(screen.getByText('No rows.')).toBeVisible()
    unmount()

    renderWithProviders(
      <DataTable {...baseProps} rows={[]} isPending empty={<p>No rows.</p>} />,
    )

    expect(screen.queryByText('No rows.')).not.toBeInTheDocument()
  })

  it('gives a link row one semantic destination and navigates on a row click', async () => {
    const user = userEvent.setup()
    const rowAction: DataTableRowAction<Row> = {
      kind: 'link',
      to: (row) => `/rows/${row.id}`,
      label: (row) => `Open ${row.name}`,
    }
    renderWithProviders(
      <>
        <DataTable {...baseProps} rowAction={rowAction} />
        <LocationProbe />
      </>,
    )

    const firstRow = screen.getByTestId('example-table-row-one')
    const link = within(firstRow).getByRole('link', { name: 'Open First row' })
    expect(link).toHaveAttribute('href', '/rows/one')
    expect(within(firstRow).getAllByRole('link')).toHaveLength(1)
    expect(firstRow).not.toHaveAttribute('tabindex')
    expect(firstRow).toHaveClass(
      'relative',
      'focus-within:bg-card',
      'focus-within:ring-3',
      'focus-within:ring-inset',
      'focus-within:ring-ring/50',
    )
    expect(link.querySelector('span[aria-hidden="true"]')).toHaveClass(
      'absolute',
      'inset-0',
    )

    await user.tab()
    expect(link).toHaveFocus()

    await user.click(link)
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/rows/one')
  })

  it('opens an accessible disclosure by keyboard and closes it with Escape', async () => {
    const user = userEvent.setup()

    function ExpandableTable() {
      const [openRowId, setOpenRowId] = useState<string | null>(null)
      return (
        <DataTable
          {...baseProps}
          rowAction={{
            kind: 'expand',
            panel: (row) => <p>Panel for {row.name}</p>,
            label: (row) => `Show details for ${row.name}`,
            openRowId,
            onOpenRowChange: setOpenRowId,
          }}
        />
      )
    }

    renderWithProviders(<ExpandableTable />)
    await user.tab()
    const trigger = screen.getByRole('button', {
      name: 'Show details for First row',
    })
    expect(screen.getByTestId('example-table-row-one')).toHaveClass(
      'focus-within:bg-card',
      'focus-within:ring-3',
      'focus-within:ring-inset',
      'focus-within:ring-ring/50',
    )
    expect(trigger).toHaveFocus()
    expect(trigger).toHaveAttribute('aria-expanded', 'false')

    await user.keyboard('{Enter}')
    const panel = screen.getByTestId('example-table-panel-one')
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(trigger).toHaveAttribute('aria-controls', panel.id)
    expect(panel).toHaveTextContent('Panel for First row')

    await user.keyboard('{Escape}')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(trigger).toHaveFocus()
    expect(screen.queryByText('Panel for First row')).not.toBeInTheDocument()
  })

  it('toggles an expand row by clicking its non-interactive cells', async () => {
    const user = userEvent.setup()

    function ExpandableTable() {
      const [openRowId, setOpenRowId] = useState<string | null>(null)
      return (
        <DataTable
          {...baseProps}
          rowAction={{
            kind: 'expand',
            panel: (row) => <p>Panel for {row.name}</p>,
            label: (row) => `Show details for ${row.name}`,
            openRowId,
            onOpenRowChange: setOpenRowId,
          }}
        />
      )
    }

    renderWithProviders(<ExpandableTable />)
    await user.click(screen.getByText('First detail'))
    expect(screen.getByText('Panel for First row')).toBeVisible()
    await user.click(screen.getByText('First detail'))
    expect(screen.queryByText('Panel for First row')).not.toBeInTheDocument()
  })

  it('lets the disclosure button toggle once and ignores links inside the row', async () => {
    const user = userEvent.setup()
    const columnsWithLink: DataTableColumn<Row, 'name'>[] = [
      columns[0],
      {
        ...columns[1],
        render: (row) => <Link to={`/details/${row.id}`}>{row.detail}</Link>,
      },
    ]

    function ExpandableTable() {
      const [openRowId, setOpenRowId] = useState<string | null>(null)
      return (
        <>
          <DataTable
            {...baseProps}
            columns={columnsWithLink}
            rowAction={{
              kind: 'expand',
              panel: (row) => <p>Panel for {row.name}</p>,
              label: (row) => `Show details for ${row.name}`,
              openRowId,
              onOpenRowChange: setOpenRowId,
            }}
          />
          <LocationProbe />
        </>
      )
    }

    renderWithProviders(<ExpandableTable />)
    const trigger = screen.getByRole('button', {
      name: 'Show details for First row',
    })

    await user.click(trigger)
    expect(screen.getByText('Panel for First row')).toBeVisible()

    await user.click(screen.getByRole('link', { name: 'First detail' }))
    expect(screen.getByText('Panel for First row')).toBeVisible()
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      '/details/one',
    )
  })

  it('scrolls a controlled open row into view', () => {
    const scrollIntoView = vi
      .spyOn(Element.prototype, 'scrollIntoView')
      .mockImplementation(() => {})

    renderWithProviders(
      <DataTable
        {...baseProps}
        rowAction={{
          kind: 'expand',
          panel: (row) => <p>Panel for {row.name}</p>,
          label: (row) => `Show details for ${row.name}`,
          openRowId: 'two',
          onOpenRowChange: vi.fn(),
        }}
      />,
    )

    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'nearest' })
    expect(
      screen.getByRole('button', {
        name: 'Show details for Second row',
      }),
    ).toHaveFocus()
    scrollIntoView.mockRestore()
  })

  it('renders inert rows without buttons, links, handlers, or focus targets', () => {
    renderWithProviders(<DataTable {...baseProps} />)

    const firstRow = screen.getByTestId('example-table-row-one')
    expect(within(firstRow).queryByRole('button')).not.toBeInTheDocument()
    expect(within(firstRow).queryByRole('link')).not.toBeInTheDocument()
    expect(firstRow).not.toHaveAttribute('tabindex')
    expect(firstRow).not.toHaveClass('cursor-pointer')
  })

  it('only activates sortable columns and delegates the column key', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    renderWithProviders(
      <DataTable
        {...baseProps}
        sort={{ by: 'name', order: 'asc', onChange }}
      />,
    )

    const activeHeading = screen.getByRole('columnheader', { name: 'Name' })
    const inactiveHeading = screen.getByRole('columnheader', { name: 'Detail' })
    expect(activeHeading).toHaveAttribute('aria-sort', 'ascending')
    expect(inactiveHeading).toHaveAttribute('aria-sort', 'none')
    expect(
      within(inactiveHeading).queryByRole('button'),
    ).not.toBeInTheDocument()

    await user.click(
      within(activeHeading).getByRole('button', { name: 'Name' }),
    )
    expect(onChange).toHaveBeenCalledWith('name')
  })
})
