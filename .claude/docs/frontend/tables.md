---
type: Module
title: frontend shared tables
description: DataTable with a discriminated rowAction and an optional right-align per column, Pagination that greys edge controls, EmptyState with no CTA, outline StatusPill, and LoadingSkeleton bars on --border.
resource: frontend/src/components/DataTable.tsx
tags: [frontend, ui, tables, react]
timestamp: 2026-08-27T00:00:00Z
---

# frontend shared tables

## Purpose

Spec 039 (DMI-88) turned the Foundations table promise into one component set. Every table-led
read screen — scan list, scan detail (findings, hosts, ports), host inventory, host detail
(findings, ports, history) — uses these primitives. Users still owns its own directory table.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `DataTable` | Headings, body, loading skeleton and empty body. Optional `sort` + `onSort`; optional discriminated `rowAction`: `link`, `expand`, or absent. | `frontend/src/components/DataTable.tsx:62` |
| `DataTableRowAction` | `link` puts one `<Link>` in the first cell and a `<tr>` mouse handler that ignores clicks that originated in an anchor. `expand` is a disclosure (`aria-expanded` / `aria-controls`) over a `colSpan` panel row. Absent means **no button and no link in any row**. | `frontend/src/components/DataTable.tsx:32` |
| `DataTableColumn` | `key`, `label`, `width`, `render`, optional `sortable`, and optional `align: 'right'`. `align` moves the **heading** as well as the cell, so a numeric column's label sits over its digits instead of drifting to the far left of the column. | `frontend/src/components/DataTable.tsx:17` |
| `Pagination` | Range line plus Previous/Next. Unavailable edge controls stay mounted, greyed, and `tabIndex={-1}`. The whole component is absent when `total <= perPage`. | `frontend/src/components/Pagination.tsx:11` |
| `EmptyState` | Heading, body, ornament. **No** `action`/`cta` prop — that absence is what keeps scan/host blank states CTA-free until DMI-89. | `frontend/src/components/EmptyState.tsx:9` |
| `StatusPill` | Outline-only tone-and-label (`running` / `failed` / `neutral`). Never takes a `ScanStatus`. | `frontend/src/components/StatusPill.tsx:16` |
| `LoadingSkeleton` | `rows × columns` bars using `bg-border` (not `bg-muted`, which is white on this palette). Used only inside a pending `DataTable`. | `frontend/src/components/LoadingSkeleton.tsx:10` |

## How it connects

- Scan list and host inventory pass `rowAction: { type: 'link' }`. Scan-detail findings and
  host-detail findings use `expand` into [screens](./screens.md)'s `FindingPanel`. Scan-detail
  host rows combine expand (ports) with an `Open {hostname}` link. Ports tables pass no
  `rowAction`.
- Sort clicks call `onSort(columnKey)` only; flip-versus-switch and page reset live in
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

# Citations

[1] [specs/039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md](../../../specs/039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md)
[2] [docs/ui/SCREENS.md](../../../docs/ui/SCREENS.md)
