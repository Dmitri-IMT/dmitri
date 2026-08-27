---
type: Module
title: frontend scan status and severity order
description: scanStatusPill maps every ScanStatus to tone and label; isUnfinished hides counts; bySeverityDesc is the only guaranteed worst-first order.
resource: frontend/src/lib/scanStatus.ts
tags: [frontend, scans, severity]
timestamp: 2026-08-26T00:00:00Z
---

# frontend scan status and severity order

## Purpose

Two React-free modules the tables branch on. Status copy and unfinished-count hiding live here so
the scan list and scan detail cannot drift. Finding order is imposed here because no list endpoint
guarantees severity order.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `scanStatusPill(status)` | Maps all five `ScanStatus` values. Unfinished (`pending`/`accepted`/`processing`) → running “Running…”; `completed` → neutral “Completed”; `failed` → failed “Failed”. | `frontend/src/lib/scanStatus.ts:20` |
| `isUnfinished(status)` | True for the three unfinished values only. Count cells that would otherwise show `0` or “None” must dash instead. | `frontend/src/lib/scanStatus.ts:24` |
| `SEVERITY_ORDER` | `critical` < `high` < `medium` < `low` as rank numbers. | `frontend/src/lib/severity.ts:5` |
| `bySeverityDesc` | Stable comparator (equal severities keep input order). Used by scan-detail and host-detail finding tables. | `frontend/src/lib/severity.ts:12` |

## How it connects

- Scan list `ScanRow` uses both status helpers. Failed rows also hide counts.
- Scan detail uses `isUnfinished` for the still-running branch and `bySeverityDesc` before render.
- Host findings reuse `bySeverityDesc`. Pill chrome is [tables](./tables.md)'s `StatusPill`.
- Failed-scan **sentences** stay in [scan-failure-reasons](./scan-failure-reasons.md), not here.

## Notes / gotchas

- Neither file imports React. The tests enumerate the `ScanStatus` union rather than sampling it.
- A completed scan with zero findings still shows the Completed pill, not an em dash.

# Citations

[1] [specs/039-frontend-scans-hosts-read-surfaces/TRUTH.md](../../../specs/039-frontend-scans-hosts-read-surfaces/TRUTH.md)
