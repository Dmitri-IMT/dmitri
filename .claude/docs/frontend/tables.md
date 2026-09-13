---
type: Module
title: frontend shared tables
description: DataTable with rowAction, rowTone and collapsedGroup; ListSurface and ReadDetailGate hold list- and detail-page state machines; Pagination, EmptyState, SeverityWord, and LoadingSkeleton.
resource: frontend/src/components/DataTable.tsx
tags: [frontend, ui, tables, react]
timestamp: 2026-09-13T18:00:00Z
---

# frontend shared tables

## Purpose

Spec 039 (DMI-88) turned the Foundations table promise into one component set; spec 042 (DMI-131)
extended it with muted row tone and a collapsible quiet group. Every table-led read screen — scan
list, scan detail (findings, hosts, ports), network inventory, host detail (findings, ports,
history), devices list, Home attention table — uses these primitives. Users still owns its own
directory table.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `DataTable` | Headings, body, loading skeleton and empty body. Generic over `Row` **and** `SortKey`; optional `sort`; optional discriminated `rowAction`; optional `rowTone` (`'muted' \| undefined`); optional `collapsedGroup` — `count`, `label`, `isOpen`, `onOpenChange`, and a `content` slot that draws the open group's tbody with `DataTable`'s own row renderers. | `frontend/src/components/DataTable.tsx:104` |
| `DataTableRowAction` | `link` puts one `<Link data-row-link>` in the first cell — **one** destination, no `useNavigate`. The `<tr>` `onClick` (`handleLinkRowClick`) clicks that link unless the click landed on another `a` or `button` (for example a `CellLink`). `expand` is a disclosure (`aria-expanded` / `aria-controls`) over a `colSpan` panel row. Absent means **no button and no link in any row**. | `frontend/src/components/DataTable.tsx:40`, `:151` |
| `DataTableRowTone` | `'muted' \| undefined`. Muted rows keep full interactivity but render with subdued ink — used for offline devices and machines not seen recently. | `frontend/src/components/DataTable.tsx:54` |
| `DataTableCollapsedGroup` | Controlled disclosure: required `isOpen` + `onOpenChange`, `count` (not a row count), `label`, `testId`, and `content`. `DataTable` draws only the disclosure row; while closed it renders an empty `tbody` as the `aria-controls` target. No rows, pending, error, footer or columns of its own. Network's quiet bucket uses the active response's `quiet_total`. | `frontend/src/components/DataTable.tsx:67` |
| `DataTableGroupBody` | What `content` receives: the group `id` (for its `tbody`), `columnCount`, `renderRows(rows, columns, tone?)` — `DataTable`'s own row renderer, so group rows keep shape, tone and `rowAction` — and `spanningRow(node)` for a full-width error or pager row. | `frontend/src/components/DataTable.tsx:56` |
| `DataTableColumn` | A two-member union over the same base (`label`, `width`, `render`, optional `align: 'right'`): a plain column takes any string `key`, a `sortable: true` column's `key` must be the table's `SortKey`. | `frontend/src/components/DataTable.tsx:30` |
| `DataTableSort` | `{ by, order, onChange }` all typed in the same `SortKey`. | `frontend/src/components/DataTable.tsx:34` |
| `ListSurface` | The one list-page state machine — error → pending skeleton → blank → table + optional pagination — shared by Scans, Network and Devices. Query payload is `ListPage<Row>` (`{ data, total? }`). Pagination, when passed, owns `page` / `perPage` / `total` / `onPageChange`. Optional `collapsedGroup` passes through to `DataTable` (Network supplies it; blank is suppressed when `collapsedGroup.count > 0`). Optional `rowTone` passes through. | `frontend/src/components/ListSurface.tsx` |
| `NotFoundNotice` | The shared 404 block for a detail route: the sentence at `${testId}-not-found` and a real Back link at `${testId}-back`. Rendered by `ReadDetailGate`, never by a screen. | `frontend/src/components/NotFoundNotice.tsx:11` |
| `ReadDetailGate` | The detail-page counterpart to `ListSurface`: takes a `DetailState<T>`, `backTo`, and `backLabel`; owns notFound → error → loading with a placeholder `PageHeader` in non-ready states. Calls `children(data)` only when ready. | `frontend/src/components/ReadDetailGate.tsx:18` |
| `EmptyMark` | The `—` absence mark. One definition; every column module and cell renderer imports it. | `frontend/src/components/EmptyMark.tsx:2` |
| `Pagination` | Required `label` becomes the nav `aria-label` (for example `Scan pages`, `Attention pages`). Previous/Next stay icon-only. Unavailable edge controls stay mounted, greyed, and `tabIndex={-1}`. The whole component is absent when `total <= perPage`. | `frontend/src/components/Pagination.tsx:20` |
| `EmptyState` | Centred heading, body, optional `action` and `note` slots — no ornament. Devices blank is the one list blank with `note` only and no `action`. | `frontend/src/components/EmptyState.tsx:11` |
| `SeverityWord` | Severity as semibold text (`Critical` / `High` / …). Null severity renders `EmptyMark`. Replaces `SeverityBadge`. | `frontend/src/components/SeverityWord.tsx:13` |
| `LoadingSkeleton` | `rows × columns` bars using `bg-border`, inside one `<tbody>`. Rendered by a pending `DataTable`, Home loading and `QuietMachineGroup`. Bars mount only after `useSkeletonDelay` (250 ms) so a fast read never flashes. | `frontend/src/components/LoadingSkeleton.tsx:13` |
| `useSkeletonDelay` | `false` until 250 ms after mount, then `true`. Shared by `LoadingSkeleton`, Home loading, and Users `SkeletonRows`. | `frontend/src/hooks/useSkeletonDelay.ts:6` |

## How it connects

- Scan list renders through `ListSurface` with `rowAction: { kind: 'link' }` and
  `FirstScanCta` / `FirstScanNote` in `empty`.
- Network and Devices render through `ListSurface`; Network passes a controlled `collapsedGroup`
  whose count is `quiet_total` from `GET /hosts` (`group=active`). Its `content` is
  `QuietMachineGroup`, which owns the `group=quiet` query, skeleton, error row and pager; Network
  keeps only the open state and the quiet page number ([screens](./screens.md)).
- [devices-screen](./devices-screen.md)'s `CommandStatus` renders status as plain text from
  [command-status](./command-status.md).
- Both findings sections use `expand` into [screens](./screens.md)'s `FindingPanel`. Scan-detail
  host rows combine expand (ports) with an `Open {hostname}` link. Ports tables pass no
  `rowAction`.
- **One** `FindingsTable` serves scan detail and host detail; Home uses its own `AttentionTable`
  column set over the same `FindingRecord` type.

## Notes / gotchas

- **No `onRowClick`, no `href` string, no `expandable` boolean.** Those would allow a fourth
  interaction the component has no states for.
- **Column widths are named Tailwind fraction utilities**, never pixel widths.
- **Every column left-aligns; numbers keep tabular figures** (`FOUNDATIONS.md` §Tables). Older
  screens may still pass `align: 'right'` until a named follow-up restyle.
- **Severity is the last column of findings tables.**
- **Row testids are `${testId}-row-${id}`**, not the shorter aliases in older spec drafts.
- **A link row is one anchor plus a row click handler — never a stretched overlay.** An
  `absolute inset-0` span inside a `relative` `<tr>` broke in Safari: WebKit ignores `relative` on
  table rows, so every row's overlay covered the viewport and the last row took every click,
  including the nav. Middle-click / Cmd-click opens a new tab only from the first-cell link.
- **The expand effect fires on a closed→open transition only**, and moves focus to the caret
  **only on the first render** — the `?finding=` deep link.
- **`StatusPill` is deleted** (spec 042). Scan and command status render as text.

# Citations

[1] [specs/039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md](../../../specs/039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md)
[2] [specs/042-design-system/TRUTH.md](../../../specs/042-design-system/TRUTH.md)
[3] [docs/ui/FOUNDATIONS.md](../../../docs/ui/FOUNDATIONS.md)
