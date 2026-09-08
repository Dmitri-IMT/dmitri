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

const quietRows: Row[] = [
  { id: 'three', name: 'Third row', detail: 'Third detail' },
  { id: 'four', name: 'Fourth row', detail: 'Fourth detail' },
]

const collapsedGroup = {
  rows: quietRows,
  label: (count: number) => `Not seen recently (${count})`,
  testId: 'example-quiet',
}

const baseProps = {
  columns,
  rows,
  rowId: (row: Row) => row.id,
  testId: 'example-table',
  caption: 'Example rows',
}

describe('DataTable', () => {
  it('renders its caption, its headings, and a horizontal scroll container', () => {
    const { container } = renderWithProviders(<DataTable {...baseProps} />)

    const table = screen.getByRole('table', { name: 'Example rows' })
    expect(table).toBeVisible()
    expect(screen.getByRole('columnheader', { name: 'Name' })).toBeVisible()
    expect(screen.getByRole('columnheader', { name: 'Detail' })).toBeVisible()
    expect(container.querySelector('div.overflow-x-auto')).toContainElement(
      table,
    )
  })

  it('gives every row the same shape whatever its content length', () => {
    const uneven: Row[] = [
      { id: 'short', name: 'A', detail: 'B' },
      {
        id: 'long',
        name: 'A hostname long enough to need truncating in its cell',
        detail: 'A detail string long enough to need truncating in its cell',
      },
    ]
    renderWithProviders(<DataTable {...baseProps} rows={uneven} />)

    const shapes = uneven.map(
      (row) => screen.getByTestId(`example-table-row-${row.id}`).className,
    )
    expect(new Set(shapes).size).toBe(1)
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
    expect(firstRow).toHaveAttribute('data-row-action', 'link')
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
    expect(screen.getByTestId('location-state')).toHaveTextContent(
      '{"from":"/"}',
    )

    await user.click(
      within(screen.getByTestId('example-table-row-two')).getByRole('link', {
        name: 'Open Second row',
      }),
    )
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/rows/two')
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
    expect(screen.getByTestId('example-table-row-one')).toHaveAttribute(
      'data-row-action',
      'expand',
    )
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

  it('lets a nested cell link win over the stretched row link', async () => {
    const user = userEvent.setup()
    const columnsWithLink: DataTableColumn<Row, 'name'>[] = [
      columns[0],
      {
        ...columns[1],
        render: (row) => <Link to={`/details/${row.id}`}>{row.detail}</Link>,
      },
    ]
    const rowAction: DataTableRowAction<Row> = {
      kind: 'link',
      to: (row) => `/rows/${row.id}`,
      label: (row) => `Open ${row.name}`,
    }

    renderWithProviders(
      <>
        <DataTable
          {...baseProps}
          columns={columnsWithLink}
          rowAction={rowAction}
        />
        <LocationProbe />
      </>,
    )

    await user.click(screen.getByRole('link', { name: 'First detail' }))
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
  it('draws all three sort states as distinct icon elements, never glyphs', () => {
    const sortableColumns: DataTableColumn<Row, 'name' | 'detail'>[] = [
      { ...columns[0], key: 'name', sortable: true },
      { ...columns[1], key: 'detail', sortable: true },
    ]

    function marker(label: string) {
      return within(screen.getByRole('columnheader', { name: label }))
        .getByRole('button', { name: label })
        .querySelector('svg')
    }

    function noGlyphs() {
      expect(screen.getByTestId('example-table').textContent).not.toMatch(
        /[\u25b2\u25bc\u2191\u2193]/,
      )
    }

    const { unmount } = renderWithProviders(
      <DataTable
        {...baseProps}
        columns={sortableColumns}
        sort={{ by: 'name', order: 'asc', onChange: vi.fn() }}
      />,
    )

    expect(screen.getByRole('columnheader', { name: 'Name' })).toHaveAttribute(
      'aria-sort',
      'ascending',
    )
    expect(
      screen.getByRole('columnheader', { name: 'Detail' }),
    ).toHaveAttribute('aria-sort', 'none')
    expect(marker('Name')).toBeInTheDocument()
    expect(marker('Detail')).toBeInTheDocument()
    const ascending = marker('Name')?.innerHTML
    const unsorted = marker('Detail')?.innerHTML
    expect(ascending).not.toBe(unsorted)
    noGlyphs()
    unmount()

    renderWithProviders(
      <DataTable
        {...baseProps}
        columns={sortableColumns}
        sort={{ by: 'name', order: 'desc', onChange: vi.fn() }}
      />,
    )

    expect(screen.getByRole('columnheader', { name: 'Name' })).toHaveAttribute(
      'aria-sort',
      'descending',
    )
    expect(marker('Name')?.innerHTML).not.toBe(ascending)
    expect(marker('Name')?.innerHTML).not.toBe(unsorted)
    noGlyphs()
  })

  it('marks only the rows the caller tones as muted', () => {
    renderWithProviders(
      <DataTable
        {...baseProps}
        rowTone={(row) => (row.id === 'two' ? 'muted' : undefined)}
      />,
    )

    expect(screen.getByTestId('example-table-row-two')).toHaveAttribute(
      'data-tone',
      'muted',
    )
    expect(screen.getByTestId('example-table-row-one')).not.toHaveAttribute(
      'data-tone',
    )
  })

  it('renders the collapsed group last, closed, and announcing its count', () => {
    renderWithProviders(
      <DataTable {...baseProps} collapsedGroup={collapsedGroup} />,
    )

    const allRows = screen.getAllByRole('row')
    expect(allRows[allRows.length - 1]).toBe(
      screen.getByTestId('example-quiet-group'),
    )
    const toggle = screen.getByRole('button', {
      name: 'Not seen recently (2)',
    })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(toggle).toHaveAttribute('data-variant', 'link')
    expect(
      screen.queryByTestId('example-table-row-three'),
    ).not.toBeInTheDocument()
  })

  it('expands and collapses the group with Enter and Space', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <DataTable {...baseProps} collapsedGroup={collapsedGroup} />,
    )

    await user.tab()
    const toggle = screen.getByRole('button', {
      name: 'Not seen recently (2)',
    })
    expect(toggle).toHaveFocus()
    expect(
      document.getElementById(toggle.getAttribute('aria-controls') ?? ''),
    ).toBeInTheDocument()

    await user.keyboard('{Enter}')
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByTestId('example-table-row-three')).toBeVisible()
    expect(screen.getByTestId('example-table-row-four')).toBeVisible()

    await user.keyboard(' ')
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(
      screen.queryByTestId('example-table-row-three'),
    ).not.toBeInTheDocument()
  })

  it('gives expanded group members the same tone and navigation as ordinary rows', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <DataTable
        {...baseProps}
        collapsedGroup={collapsedGroup}
        rowTone={(row) => (quietRows.includes(row) ? 'muted' : undefined)}
        rowAction={{
          kind: 'link',
          to: (row) => `/rows/${row.id}`,
          label: (row) => `Open ${row.name}`,
        }}
      />,
    )

    await user.click(
      screen.getByRole('button', { name: 'Not seen recently (2)' }),
    )

    const quietRow = screen.getByTestId('example-table-row-three')
    expect(quietRow).toHaveAttribute('data-tone', 'muted')
    expect(
      within(quietRow).getByRole('link', { name: 'Open Third row' }),
    ).toHaveAttribute('href', '/rows/three')
    expect(screen.getByTestId('example-table-row-one')).not.toHaveAttribute(
      'data-tone',
    )
  })
})
