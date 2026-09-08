---
type: Module
title: frontend scan status and severity order
description: scanStatusLabel maps every ScanStatus to a label; hidesCounts dashes count cells; bySeverityDesc is the only guaranteed worst-first order.
resource: frontend/src/lib/scanStatus.ts
tags: [frontend, scans, severity]
timestamp: 2026-09-04T00:00:00Z
---

# frontend scan status and severity order

## Purpose

Two React-free modules the tables branch on. Status copy and count hiding live here so the scan list
and scan detail cannot drift. Finding order is imposed here because no list endpoint guarantees
severity order.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `scanStatusLabel(status)` | Maps all five `ScanStatus` values to a string. Unfinished (`pending`/`accepted`/`processing`) → "Running…"; `completed` → "Completed"; `failed` → "Failed". Rendered as plain text — no pill chrome. | `frontend/src/lib/scanStatus.ts:13` |
| `isUnfinished(status)` | True for the three unfinished values only. | `frontend/src/lib/scanStatus.ts:17` |
| `hidesCounts(status)` | True when `isUnfinished(status)` or `status === 'failed'`. Count cells that would otherwise show `0` or "None" must dash instead. | `frontend/src/lib/scanStatus.ts:25` |
| `SEVERITY_ORDER` | `critical` < `high` < `medium` < `low` as rank numbers. | `frontend/src/lib/severity.ts:5` |
| `bySeverityDesc` | Stable comparator (equal severities keep input order). Used by scan-detail and host-detail finding tables. | `frontend/src/lib/severity.ts:12` |

## How it connects

- Scan list `scanListColumns` uses `scanStatusLabel`, `hidesCounts`, and [screens](./screens.md)'s
  `SeverityWord` for the highest-severity column.
- Scan detail uses `isUnfinished` for the still-running branch and `bySeverityDesc` before render.
- Host findings reuse `bySeverityDesc`.
- Failed-scan **sentences** stay in [scan-failure-reasons](./scan-failure-reasons.md), not here.
  Command lifecycle labels live in [command-status](./command-status.md).

## Notes / gotchas

- Neither file imports React. The tests enumerate the `ScanStatus` union rather than sampling it.
- **`scanStatusPill` and `StatusPill` are gone** (spec 042). Status is semibold or body text only.
- A completed scan with zero findings still shows the Completed label, not an em dash.

# Citations

[1] [specs/039-frontend-scans-hosts-read-surfaces/TRUTH.md](../../../specs/039-frontend-scans-hosts-read-surfaces/TRUTH.md)
[2] [specs/042-design-system/TRUTH.md](../../../specs/042-design-system/TRUTH.md)
