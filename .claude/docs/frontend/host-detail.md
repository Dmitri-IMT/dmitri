---
type: Module
title: frontend detail read unions
description: readDetailState turns one detail query into loading/error/notFound/ready for both detail screens; useHostDetail layers the host's findings read on top, and ReadDetailGate renders the three non-ready states.
resource: frontend/src/hooks/useHostDetail.ts
tags: [frontend, hosts, scans, findings, tanstack-query]
timestamp: 2026-08-27T15:00:00Z
---

# frontend detail read unions

## Purpose

A detail screen renders a **state**, never raw query flags. `readDetailState` is the one place the
404-versus-error rule lives, and `ReadDetailGate` ([tables](./tables.md)) is the one place those
states are **rendered** — neither `/scans/:scanId` nor `/hosts/:hostId` switches over them itself.
Host detail additionally makes two reads (the host record and that host's findings) and must not
paint a half page, so `useHostDetail` folds the second one in the same way
[directory](./directory.md)'s `useOrgDirectory` does: error outranks pending.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `DetailState<T>` | `{ state: 'loading' }` / `{ state: 'error'; retry }` / `{ state: 'notFound' }` / `{ state: 'ready'; data: T }`. | `frontend/src/lib/detailState.ts:4` |
| `readDetailState(id, query)` | Empty `id` **or** a 404 (`readApiError(...).status === 404`) is `notFound`; any other error carries a `retry` that refetches; pending is `loading`; otherwise `ready` with the data. Used directly by `ScanDetail`. | `frontend/src/lib/detailState.ts:10` |
| `HostDetail` | The ready payload only — `{ host; findings }`. The hook returns `DetailState<HostDetail>`, not a second hand-written union. | `frontend/src/hooks/useHostDetail.ts:11` |
| `useHostDetail(hostId)` | Returns `DetailState<HostDetail>`. `readDetailState` over `getHost` (keyed `queryKeys.hosts.detail`), then the findings read (`listFindings`, one `{ host_id, per_page: 100 }` object serving both the key and the request) folded in: either error is `error`, either pending is `loading`. `retry` refetches both. | `frontend/src/hooks/useHostDetail.ts:16` |

## How it connects

- Consumes [api](./api.md)'s `getHost` and `listFindings`.
- Consumed by [screens](./screens.md)'s `HostDetail`; `readDetailState` is also consumed directly
  by `ScanDetail`. Both screens hand the result to `ReadDetailGate` ([tables](./tables.md)), which
  owns the `NotFoundNotice` / `ErrorRetry` / placeholder-header chrome. Findings on both screens open `pages/scans/FindingPanel.tsx` inside
  the shared `FindingsTable`.

## Notes / gotchas

- **`useHostDetail` stays a hook because it composes two queries.** Scan detail has one query and
  calls `readDetailState` inline — a `useScanDetail` wrapper around a single `useQuery` would not
  earn its keep.
- **Page-level error, not a findings-section error.** Either read failing shows “Couldn't load
  this host.” plus `[Retry]`. DESIGN §5.6's independent findings retry was not built.
- **The gate stops at `ready`.** Scan detail's failed / unfinished split stays inside `ScanDetail`:
  those are domain states of a scan, not read states of a query, and host detail has no counterpart.
- Opening a finding panel fetches nothing extra; the panel is the embedded `FindingRecord`.

# Citations

[1] [specs/039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md](../../../specs/039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md)
