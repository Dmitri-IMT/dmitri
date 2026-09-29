---
type: Module
title: frontend scan status and severity order
description: scanStatusLabel maps every ScanStatus including cancelled and Stopped early; hidesCounts dashes count cells; bySeverityDesc is the only guaranteed worst-first order.
resource: frontend/src/lib/scanStatus.ts
tags: [frontend, scans, severity, cancel]
timestamp: 2026-09-29T00:00:00Z
---

# frontend scan status and severity order

## Purpose

Two React-free modules the tables branch on. Status copy and count hiding live here so the scan list
and scan detail cannot drift. Finding order is imposed here because no list endpoint guarantees
severity order.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `scanStatusLabel(status, terminatedBy?)` | Maps every `ScanStatus`. Unfinished → "Running…"; `completed` → "Completed"; `completed` + `terminatedBy === "user_cancel"` → "Stopped early"; `failed` → "Failed"; `cancelled` → "Stopped". | `frontend/src/lib/scanStatus.ts:5` |
| `isUnfinished(status)` | True for the three unfinished values only (`pending`/`accepted`/`processing`). | `frontend/src/lib/scanStatus.ts:30` |
| `hidesCounts(status)` | True when unfinished, `failed`, or `cancelled`. Count cells that would otherwise show `0` or "None" must dash instead. | `frontend/src/lib/scanStatus.ts:47` |
| `SEVERITY_ORDER` | `critical` < `high` < `medium` < `low` as rank numbers. | `frontend/src/lib/severity.ts:5` |
| `bySeverityDesc` | Stable comparator (equal severities keep input order). Used by scan-detail and host-detail finding tables. | `frontend/src/lib/severity.ts:12` |

## How it connects

- Scan list `scanListColumns` and device history columns pass `terminated_by` into
  `scanStatusLabel` for the **Stopped early** label.
- Scan detail uses `isUnfinished` for the still-running branch, `cancelled` for
  `ScanStoppedNotice variant="empty"`, and `bySeverityDesc` before render.
- Host findings reuse `bySeverityDesc`.
- Failed-scan **sentences** stay in [scan-failure-reasons](./scan-failure-reasons.md), not here.
  Command lifecycle labels live in [command-status](./command-status.md).

## Notes / gotchas

- Neither file imports React. The tests enumerate the `ScanStatus` union rather than sampling it.
- **`scanStatusPill` and `StatusPill` are gone** (spec 042). Status is semibold or body text only.
- A completed scan with zero findings still shows the Completed label, not an em dash.
- **Two stop labels.** Scan `cancelled` (no results) → **Stopped**. Scan `completed` +
  `terminated_by == "user_cancel"` → **Stopped early**.

# Citations

[1] [specs/039-frontend-scans-hosts-read-surfaces/TRUTH.md](../../../specs/039-frontend-scans-hosts-read-surfaces/TRUTH.md)
[2] [specs/042-design-system/TRUTH.md](../../../specs/042-design-system/TRUTH.md)
[3] [specs/049-remote-scan-cancel/plan.md](../../../specs/049-remote-scan-cancel/plan.md)
