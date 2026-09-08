import {
  Fragment,
  useEffect,
  useId,
  useRef,
  useState,
  type MouseEvent,
  type ReactElement,
  type ReactNode,
} from 'react'
import {
  ChevronDown,
  ChevronRight,
  ChevronUp,
  ChevronsUpDown,
} from 'lucide-react'
import { Link, useLocation } from 'react-router'
import { fromHere } from '@/lib/navFrom'
import LoadingSkeleton from '@/components/LoadingSkeleton'
import { Button } from '@/components/ui/button'

export type SortOrder = 'asc' | 'desc'

type DataTableColumnBase<Row> = {
  label: string
  width: string
  render: (row: Row) => ReactNode
  align?: 'right'
}

export type DataTableColumn<Row, SortKey extends string = never> =
  | (DataTableColumnBase<Row> & { key: string; sortable?: false })
  | (DataTableColumnBase<Row> & { key: SortKey; sortable: true })

export type DataTableSort<SortKey extends string = never> = {
  by: SortKey
  order: SortOrder
  onChange: (key: SortKey) => void
}

export type DataTableRowAction<Row> =
  | {
      kind: 'link'
      to: (row: Row) => string
      label: (row: Row) => string
    }
  | {
      kind: 'expand'
      panel: (row: Row) => ReactNode
      label: (row: Row) => string
      openRowId: string | null
      onOpenRowChange: (rowId: string | null) => void
    }

export type DataTableRowTone = 'muted' | undefined

export type DataTableCollapsedGroup<Row> = {
  rows: Row[]
  label: (count: number) => string
  testId: string
}

export type DataTableProps<Row, SortKey extends string = never> = {
  columns: DataTableColumn<Row, SortKey>[]
  rows: Row[]
  rowId: (row: Row) => string
  testId: string
  caption: string
  isPending?: boolean
  skeletonRows?: number
  empty?: ReactNode
  sort?: DataTableSort<SortKey>
  rowAction?: DataTableRowAction<Row>
  rowTone?: (row: Row) => DataTableRowTone
  collapsedGroup?: DataTableCollapsedGroup<Row>
}

const INTERACTIVE_ROW =
  'group relative h-row cursor-pointer border-t border-border text-caption-md hover:bg-card focus-within:bg-card focus-within:ring-3 focus-within:ring-inset focus-within:ring-ring/50 active:bg-border'

const INERT_ROW = 'h-row border-t border-border text-caption-md'

function columnTextAlign(align: 'right' | undefined): string {
  return align === 'right' ? 'text-right' : ''
}

function sortButtonJustify(align: 'right' | undefined): string {
  return align === 'right' ? 'justify-end' : 'justify-start'
}

function DataTable<Row, SortKey extends string = never>({
  columns,
  rows,
  rowId,
  testId,
  caption,
  isPending = false,
  skeletonRows = 3,
  empty,
  sort,
  rowAction,
  rowTone,
  collapsedGroup,
}: DataTableProps<Row, SortKey>): ReactElement {
  const location = useLocation()
  const tableId = useId()
  const [isGroupOpen, setIsGroupOpen] = useState(false)
  const rowRefs = useRef(new Map<string, HTMLTableRowElement>())
  const triggerRefs = useRef(new Map<string, HTMLButtonElement>())
  const openRowId = rowAction?.kind === 'expand' ? rowAction.openRowId : null
  const previousOpenRowId = useRef<string | null>(null)
  const isFirstRender = useRef(true)

  useEffect(() => {
    const isDeepLink = isFirstRender.current
    const opened = openRowId !== null && openRowId !== previousOpenRowId.current
    isFirstRender.current = false
    previousOpenRowId.current = openRowId
    if (!opened) return

    rowRefs.current.get(openRowId)?.scrollIntoView({ block: 'nearest' })
    if (isDeepLink) triggerRefs.current.get(openRowId)?.focus()
  }, [openRowId])

  function panelId(id: string) {
    return `${tableId}-panel-${encodeURIComponent(id)}`
  }

  function handleExpandRowClick(
    event: MouseEvent<HTMLTableRowElement>,
    id: string,
  ) {
    if ((event.target as HTMLElement).closest('button, a')) return
    if (rowAction?.kind === 'expand') {
      rowAction.onOpenRowChange(rowAction.openRowId === id ? null : id)
    }
  }

  function renderCell(
    row: Row,
    column: DataTableColumn<Row, SortKey>,
    index: number,
  ) {
    const content = column.render(row)

    if (index === 0 && rowAction?.kind === 'link') {
      return (
        <Link
          to={rowAction.to(row)}
          state={fromHere(location)}
          aria-label={rowAction.label(row)}
          className="block underline-offset-4 outline-none group-hover:underline group-focus-within:underline focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <span className="block truncate">{content}</span>
          <span aria-hidden="true" className="absolute inset-0" />
        </Link>
      )
    }

    if (index === 0 && rowAction?.kind === 'expand') {
      const id = rowId(row)
      const isOpen = rowAction.openRowId === id
      return (
        <Button
          ref={(element) => {
            if (element) triggerRefs.current.set(id, element)
            else triggerRefs.current.delete(id)
          }}
          type="button"
          variant="link"
          aria-label={rowAction.label(row)}
          aria-expanded={isOpen}
          aria-controls={panelId(id)}
          data-testid={`${testId}-caret-${id}`}
          className="h-auto w-full justify-start gap-1 rounded-none px-0 py-0 text-caption-md font-normal text-foreground no-underline"
          onClick={() => rowAction.onOpenRowChange(isOpen ? null : id)}
          onKeyDown={(event) => {
            if (event.key === 'Escape' && isOpen) {
              event.preventDefault()
              rowAction.onOpenRowChange(null)
            }
          }}
        >
          <ChevronRight
            aria-hidden="true"
            className={`size-3 shrink-0 transition-transform ease-standard ${isOpen ? 'rotate-90' : ''}`}
          />
          <span className="truncate">{content}</span>
        </Button>
      )
    }

    return content
  }

  function renderRow(row: Row) {
    const id = rowId(row)
    const isLink = rowAction?.kind === 'link'
    const isExpand = rowAction?.kind === 'expand'
    const isOpen = isExpand && rowAction.openRowId === id
    const tone = rowTone?.(row)

    return (
      <Fragment key={id}>
        <tr
          ref={(element) => {
            if (element) rowRefs.current.set(id, element)
            else rowRefs.current.delete(id)
          }}
          data-testid={`${testId}-row-${id}`}
          data-tone={tone}
          data-row-action={isLink ? 'link' : isExpand ? 'expand' : undefined}
          className={`${
            isLink || isExpand
              ? `${INTERACTIVE_ROW} ${isOpen ? 'bg-card' : ''}`
              : INERT_ROW
          } ${tone === 'muted' ? 'text-muted-foreground' : ''}`}
          onClick={
            isExpand ? (event) => handleExpandRowClick(event, id) : undefined
          }
        >
          {columns.map((column, index) => (
            <td
              key={column.key}
              className={`max-w-0 pr-4 align-middle ${
                index === 0 && isLink ? '' : 'truncate'
              } ${columnTextAlign(column.align)}`}
            >
              {renderCell(row, column, index)}
            </td>
          ))}
        </tr>
        {isOpen && (
          <tr>
            <td
              id={panelId(id)}
              data-testid={`${testId}-panel-${id}`}
              colSpan={columns.length}
              className="border-b border-dashed border-border bg-card"
            >
              {rowAction.panel(row)}
            </td>
          </tr>
        )}
      </Fragment>
    )
  }

  const groupId = `${tableId}-group`
  const isEmpty = rows.length === 0 && !collapsedGroup?.rows.length

  return (
    <div className="overflow-x-auto">
      <table data-testid={testId} className="w-full table-fixed text-left">
        <caption className="sr-only">{caption}</caption>
        <colgroup>
          {columns.map((column) => (
            <col key={column.key} className={column.width} />
          ))}
        </colgroup>
        <thead>
          <tr className="h-row border-b border-dashed border-border text-caption-md text-muted-foreground">
            {columns.map((column) => {
              const isActive = sort?.by === column.key
              const ariaSort = sort
                ? isActive
                  ? sort.order === 'asc'
                    ? 'ascending'
                    : 'descending'
                  : 'none'
                : undefined

              return (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={ariaSort}
                  className={`truncate pr-4 font-normal uppercase ${columnTextAlign(column.align)}`}
                >
                  {sort && column.sortable ? (
                    <Button
                      type="button"
                      variant="link"
                      aria-label={column.label}
                      data-testid={`${testId}-sort-${column.key}`}
                      className={`h-auto max-w-full gap-1 rounded-none px-0 py-0 text-caption-md font-normal text-muted-foreground underline-offset-4 hover:text-foreground hover:underline focus-visible:text-foreground focus-visible:underline active:decoration-2 ${sortButtonJustify(column.align)}`}
                      onClick={() => sort.onChange(column.key)}
                    >
                      <span
                        className={
                          isActive ? 'font-semibold text-foreground' : ''
                        }
                      >
                        {column.label}
                      </span>
                      {isActive ? (
                        sort.order === 'asc' ? (
                          <ChevronUp aria-hidden="true" className="size-4" />
                        ) : (
                          <ChevronDown aria-hidden="true" className="size-4" />
                        )
                      ) : (
                        <ChevronsUpDown aria-hidden="true" className="size-4" />
                      )}
                    </Button>
                  ) : (
                    column.label
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        {isPending ? (
          <LoadingSkeleton rows={skeletonRows} columns={columns.length} />
        ) : isEmpty ? (
          <tbody>
            <tr>
              <td colSpan={columns.length} className="py-12 text-center">
                {empty}
              </td>
            </tr>
          </tbody>
        ) : (
          <tbody>{rows.map((row) => renderRow(row))}</tbody>
        )}
        {!isPending && collapsedGroup && collapsedGroup.rows.length > 0 && (
          <>
            <tbody>
              <tr
                data-testid={`${collapsedGroup.testId}-group`}
                className={INERT_ROW}
              >
                <td colSpan={columns.length} className="pr-4 align-middle">
                  <Button
                    type="button"
                    variant="link"
                    aria-expanded={isGroupOpen}
                    aria-controls={groupId}
                    data-testid={`${collapsedGroup.testId}-toggle`}
                    className="h-auto gap-1 rounded-none px-0 py-0 text-caption-md font-normal text-muted-foreground no-underline"
                    onClick={() => setIsGroupOpen(!isGroupOpen)}
                  >
                    <ChevronRight
                      aria-hidden="true"
                      className={`size-4 shrink-0 transition-transform ease-standard ${isGroupOpen ? 'rotate-90' : ''}`}
                    />
                    {collapsedGroup.label(collapsedGroup.rows.length)}
                  </Button>
                </td>
              </tr>
            </tbody>
            <tbody id={groupId}>
              {isGroupOpen && collapsedGroup.rows.map((row) => renderRow(row))}
            </tbody>
          </>
        )}
      </table>
    </div>
  )
}

export default DataTable
