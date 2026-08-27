---
type: Module
title: frontend detail read unions
description: readDetailState turns one detail query into loading/error/notFound/ready for both detail screens; useHostDetail layers the host's findings read on top.
resource: frontend/src/hooks/useHostDetail.ts
tags: [frontend, hosts, scans, findings, tanstack-query]
timestamp: 2026-08-27T15:00:00Z
---

# frontend detail read unions

## Purpose

A detail screen renders a **state**, never raw query flags. `readDetailState` is the one place the
404-versus-error rule lives; both `/scans/:scanId` and `/hosts/:hostId` switch over its result.
Host detail additionally makes two reads (the host record and that host's findings) and must not
paint a half page, so `useHostDetail` folds the second one in the same way
[directory](./directory.md)'s `useOrgDirectory` does: error outranks pending.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `DetailState<T>` | `{ state: 'loading' }` / `{ state: 'error'; retry }` / `{ state: 'notFound' }` / `{ state: 'ready'; data: T }`. | `frontend/src/lib/detailState.ts:4` |
| `readDetailState(id, query)` | Empty `id` **or** a 404 (`readApiError(...).status === 404`) is `notFound`; any other error carries a `retry` that refetches; pending is `loading`; otherwise `ready` with the data. Used directly by `ScanDetail`. | `frontend/src/lib/detailState.ts:10` |
| `HostDetail` | `{ state: 'loading' }` / `{ state: 'error'; retry }` / `{ state: 'notFound' }` / `{ state: 'ready'; host; findings }`. | `frontend/src/hooks/useHostDetail.ts:11` |
| `useHostDetail(hostId)` | `readDetailState` over `getHost` (keyed `queryKeys.hosts.detail`), then the findings read (`listFindingsForHost`, keyed `queryKeys.findings.list({ host_id, per_page: 100 })`) folded in: either error is `error`, either pending is `loading`. `retry` refetches both. | `frontend/src/hooks/useHostDetail.ts:17` |

## How it connects

- Consumes [api](./api.md)'s `getHost` and `listFindingsForHost`.
- Consumed by [screens](./screens.md)'s `HostDetail`; `readDetailState` is also consumed directly
  by `ScanDetail`. Both screens render the `notFound` branch through the shared `NotFoundNotice`
  in [tables](./tables.md). Findings on both screens open `pages/scans/FindingPanel.tsx` inside
  the shared `FindingsTable`.

## Notes / gotchas

- **`useHostDetail` stays a hook because it composes two queries.** Scan detail has one query and
  calls `readDetailState` inline — a `useScanDetail` wrapper around a single `useQuery` would not
  earn its keep.
- **Page-level error, not a findings-section error.** Either read failing shows “Couldn't load
  this host.” plus `[Retry]`. DESIGN §5.6's independent findings retry was not built.
- Opening a finding panel fetches nothing extra; the panel is the embedded `FindingRecord`.

# Citations

[1] [specs/039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md](../../../specs/039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md)
