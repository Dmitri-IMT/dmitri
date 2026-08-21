import Timestamp from '@/components/Timestamp'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { OrgDirectory } from '@/hooks/useOrgDirectory'
import { lastSeenCell, statusLabel, type DirectoryRow } from '@/lib/directory'

type Role = DirectoryRow['role']

const COLUMNS = ['Person', 'Role', 'Status', 'Last seen']
const ROLE_LABEL = { admin: 'Admin', viewer: 'Viewer' } as const

// `table-fixed` splits columns evenly unless told otherwise, which gave the actions cell
// a button's width plus a column of dead space while Person truncated. Shares, not widths:
// each column is a percentage of whatever the table is, so the whole row scales with the
// shell and nothing is pinned to a pixel count. Person yields share below `sm`, where the
// table is narrow enough that Last seen would otherwise clip its own text.
//   below sm: 30 · 15 · 20 · 25 · 10     sm and up: 35 · 15 · 20 · 20 · 10
function Columns() {
  return (
    <colgroup>
      <col className="w-3/10 sm:w-7/20" />
      <col className="w-3/20" />
      <col className="w-1/5" />
      <col className="w-1/4 sm:w-1/5" />
      <col className="w-1/10" />
    </colgroup>
  )
}

function Headings() {
  return (
    <thead>
      <tr className="h-8 text-left text-caption-md text-muted-foreground uppercase">
        {COLUMNS.map((column) => (
          <th key={column} className="truncate font-normal">
            {column}
          </th>
        ))}
        <th className="font-normal">
          <span className="sr-only">Actions</span>
        </th>
      </tr>
    </thead>
  )
}

function RoleCell({
  row,
  onRoleChange,
}: {
  row: DirectoryRow
  onRoleChange: (row: DirectoryRow, next: Role) => void
}) {
  if (row.kind === 'invite' || row.isSelf) {
    return (
      <span data-testid={`row-role-text-${row.id}`}>
        {ROLE_LABEL[row.role]}
      </span>
    )
  }
  // The trigger is stripped of its box so the value sits on the same left edge as the
  // plain-text roles in rows that carry no dropdown, and so nothing in the cell is taller
  // than the locked row height. Only the chevron marks it as a control; the focus ring
  // survives as `ring-3`, which needs no border.
  return (
    <Select
      value={row.role}
      onValueChange={(next) => onRoleChange(row, next as Role)}
    >
      <SelectTrigger
        data-testid={`row-role-${row.id}`}
        aria-label={`Role for ${row.email}`}
        className="h-auto rounded-none border-0 px-0 py-0 text-caption-md"
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="viewer">Viewer</SelectItem>
        <SelectItem value="admin">Admin</SelectItem>
      </SelectContent>
    </Select>
  )
}

function LastSeenCell({ row }: { row: DirectoryRow }) {
  const cell = lastSeenCell(row)
  return cell.kind === 'time' ? (
    <Timestamp value={cell.value} />
  ) : (
    <>{cell.value}</>
  )
}

function Row({
  row,
  onRoleChange,
  onRemove,
  onRevoke,
}: {
  row: DirectoryRow
  onRoleChange: (row: DirectoryRow, next: Role) => void
  onRemove: (row: DirectoryRow) => void
  onRevoke: (row: DirectoryRow) => void
}) {
  const isSelf = row.kind === 'member' && row.isSelf
  return (
    <tr
      data-testid={isSelf ? 'user-row-self' : `user-row-${row.id}`}
      className="h-8 border-t border-border text-caption-md"
    >
      <td className="max-w-0 truncate pr-4" title={row.email}>
        {row.email}
      </td>
      <td className="pr-4">
        <RoleCell row={row} onRoleChange={onRoleChange} />
      </td>
      <td
        data-testid={`row-status-${row.id}`}
        className="max-w-0 truncate pr-4"
        title={statusLabel(row)}
      >
        {statusLabel(row)}
      </td>
      <td
        data-testid={`row-last-seen-${row.id}`}
        className="max-w-0 truncate pr-4"
      >
        <LastSeenCell row={row} />
      </td>
      <td className="text-right">
        {row.kind === 'invite' ? (
          <Button
            type="button"
            variant="outline"
            size="xs"
            onClick={() => onRevoke(row)}
            data-testid={`row-revoke-${row.id}`}
          >
            Revoke
          </Button>
        ) : (
          !row.isSelf && (
            <Button
              type="button"
              variant="outline"
              size="xs"
              onClick={() => onRemove(row)}
              data-testid={`row-remove-${row.id}`}
            >
              Remove
            </Button>
          )
        )}
      </td>
    </tr>
  )
}

function SkeletonRows() {
  return (
    <tbody>
      {[0, 1, 2].map((index) => (
        <tr key={index} className="h-8 border-t border-border">
          {[0, 1, 2, 3, 4].map((cell) => (
            <td key={cell} className="pr-4">
              <span className="block h-3 w-full bg-muted" />
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  )
}

function DirectoryTable({
  directory,
  onRoleChange,
  onRemove,
  onRevoke,
}: {
  directory: OrgDirectory
  onRoleChange: (row: DirectoryRow, next: Role) => void
  onRemove: (row: DirectoryRow) => void
  onRevoke: (row: DirectoryRow) => void
}) {
  switch (directory.state) {
    case 'loading':
      return (
        <table data-testid="users-loading" className="w-full table-fixed">
          <Columns />
          <Headings />
          <SkeletonRows />
        </table>
      )
    case 'error':
      return (
        <div
          className="flex flex-col items-center gap-4 py-12 text-center"
          data-testid="users-error"
        >
          <p>Couldn&apos;t load your organisation.</p>
          <Button
            type="button"
            variant="outline"
            data-testid="users-error-retry"
            onClick={directory.retry}
          >
            Try again
          </Button>
        </div>
      )
    case 'blank':
      return (
        <p
          data-testid="users-blank"
          className="py-12 text-center text-muted-foreground"
        >
          You&apos;re the only person here.
        </p>
      )
    case 'ready':
      return (
        <table data-testid="users-table" className="w-full table-fixed">
          <Columns />
          <Headings />
          <tbody>
            {directory.rows.map((row) => (
              <Row
                key={row.id}
                row={row}
                onRoleChange={onRoleChange}
                onRemove={onRemove}
                onRevoke={onRevoke}
              />
            ))}
          </tbody>
        </table>
      )
  }
}

export default DirectoryTable
