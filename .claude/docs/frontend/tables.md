---
type: Module
title: frontend shared tables
description: DataTable with a discriminated rowAction, stretched-link rows and compile-time sort keys, ListSurface holding the one list-page state machine, Pagination that greys edge controls, EmptyState with no CTA, outline StatusPill, and LoadingSkeleton bars on --border.
resource: frontend/src/components/DataTable.tsx
tags: [frontend, ui, tables, react]
timestamp: 2026-08-27T15:00:00Z
---

# frontend shared tables

## Purpose

Spec 039 (DMI-88) turned the Foundations table promise into one component set. Every table-led
read screen — scan list, scan detail (findings, hosts, ports), host inventory, host detail
(findings, ports, history) — uses these primitives. Users still owns its own directory table.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `DataTable` | Headings, body, loading skeleton and empty body. Generic over `Row` **and** `SortKey`; optional `sort`; optional discriminated `rowAction`: `link`, `expand`, or absent. | `frontend/src/components/DataTable.tsx:64` |
| `DataTableRowAction` | `link` puts one `<Link>` in the first cell whose absolutely-positioned child span covers the `relative` `<tr>` — **one** destination, no row `onClick` and no `useNavigate`. `expand` is a disclosure (`aria-expanded` / `aria-controls`) over a `colSpan` panel row, and keeps its own `closest('button, a')` guard so an in-panel link is not swallowed. Absent means **no button and no link in any row**. | `frontend/src/components/DataTable.tsx:34` |
| `DataTableColumn` | A two-member union over the same base (`label`, `width`, `render`, optional `align: 'right'`): a plain column takes any string `key`, a `sortable: true` column's `key` must be the table's `SortKey`. `align` moves the **heading** as well as the cell, so a numeric column's label sits over its digits instead of drifting to the far left of the column. | `frontend/src/components/DataTable.tsx:24` |
| `DataTableSort` | `{ by, order, onChange }` all typed in the same `SortKey`, so `Hosts.handleSort(key: HostSortBy)` is the only legal handler and a mistyped column key fails to compile instead of no-opping. | `frontend/src/components/DataTable.tsx:28` |
| `ListSurface` | The one list-page state machine — error → pending skeleton → blank → table + pagination — shared by the scan list and the host inventory. One `testId` prefix derives all four (`-table`, `-error`, `-blank`, and the pagination's own). Pages own only their query params, columns and copy. | `frontend/src/components/ListSurface.tsx:29` |
| `NotFoundNotice` | The shared 404 block for a detail route: the sentence at `${testId}-not-found` and a real Back link at `${testId}-back`. Both detail screens render it; neither inlines the chrome. | `frontend/src/components/NotFoundNotice.tsx:11` |
| `Pagination` | Range line plus Previous/Next. Unavailable edge controls stay mounted, greyed, and `tabIndex={-1}`. The whole component is absent when `total <= perPage`. | `frontend/src/components/Pagination.tsx:11` |
| `EmptyState` | Heading, body, ornament. **No** `action`/`cta` prop — that absence is what keeps scan/host blank states CTA-free until DMI-89. | `frontend/src/components/EmptyState.tsx:9` |
| `StatusPill` | Outline-only tone-and-label (`running` / `failed` / `neutral`). Never takes a `ScanStatus`. | `frontend/src/components/StatusPill.tsx:16` |
| `LoadingSkeleton` | `rows × columns` bars using `bg-border` (not `bg-muted`, which is white on this palette). Used only inside a pending `DataTable`. | `frontend/src/components/LoadingSkeleton.tsx:10` |

## How it connects

- Scan list and host inventory render through `ListSurface` with `rowAction: { kind: 'link' }`.
  Both findings sections use `expand` into [screens](./screens.md)'s `FindingPanel`. Scan-detail
  host rows combine expand (ports) with an `Open {hostname}` link. Ports tables pass no
  `rowAction`.
- **One** `FindingsTable` serves both screens: `hosts` present adds the Host column via
  `findingColumns(hostColumn?)`, and `testId` / `caption` / `emptyTestId` / `emptyCopy` carry the
  per-screen strings. Both ports tables share `portColumns`.
- Sort clicks call `sort.onChange(columnKey)` only; flip-versus-switch and page reset live in
  `Hosts.tsx`.

## Notes / gotchas

- **No `onRowClick`, no `href` string, no `expandable` boolean.** Those would allow a fourth
  interaction the component has no states for.
- **Column widths are named Tailwind fraction utilities**, never pixel widths.
- **Numbers right-align only when the column is not first.** Findings `Port` and the `Open ports`
  counts carry `align: 'right'`; the ports tables' leading `Port` column does not, because a
  right-aligned first column pushes the table's visible start into the middle of the page while
  every neighbouring table starts flush left. `docs/ui/SCREENS.md` § Foundations, Consistency
  rule 10 governs.
- **Severity is the last column of both findings tables.** It was the first column as shipped;
  review moved it on 2026-08-27 to match the other table-led screens. `docs/ui/SCREENS.md`
  § Foundations, Consistency rule 11 governs.
- **Row testids are `${testId}-row-${id}`**, not the shorter aliases in older spec drafts.
- **A link row is one anchor, stretched.** The whole-row mouse target is the anchor's overlay
  span, so the first cell drops `truncate` (the anchor's inner span truncates instead) — an
  `overflow: hidden` cell would clip the overlay back to that column. Tests must click the row's
  link, not the `<tr>`: jsdom does no layout, so the overlay covers nothing there.
- **The expand effect fires on a closed→open transition only**, and moves focus to the caret
  **only on the first render** — the `?finding=` deep link DESIGN §9 calls "the one programmatic
  move". A later mouse click scrolls but never steals focus.

# Citations

[1] [specs/039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md](../../../specs/039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md)
[2] [docs/ui/SCREENS.md](../../../docs/ui/SCREENS.md)
