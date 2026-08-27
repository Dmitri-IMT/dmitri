---
type: Module
title: frontend host-detail read union
description: useHostDetail folds GET /hosts/{id} and GET /findings?host_id= into one loading/error/notFound/ready union, mirroring useOrgDirectory.
resource: frontend/src/hooks/useHostDetail.ts
tags: [frontend, hosts, findings, tanstack-query]
timestamp: 2026-08-26T00:00:00Z
---

# frontend host-detail read union

## Purpose

Host detail makes two reads (the host record and that host's findings) and must not paint a half
page. `useHostDetail` collapses them the same way [directory](./directory.md)'s `useOrgDirectory`
does: error outranks pending; a host 404 is `notFound`, not a generic error.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `HostDetail` | `{ state: 'loading' }` / `{ state: 'error'; retry }` / `{ state: 'notFound' }` / `{ state: 'ready'; host; findings }`. | `frontend/src/hooks/useHostDetail.ts:11` |
| `useHostDetail(hostId)` | `getHost` keyed `queryKeys.hosts.detail`; `listFindingsForHost` keyed `queryKeys.findings.list({ host_id, per_page: 100 })`. Empty `hostId` is `notFound`. `retry` refetches both. | `frontend/src/hooks/useHostDetail.ts:17` |

## How it connects

- Consumes [api](./api.md)'s `getHost` and `listFindingsForHost`.
- Consumed by [screens](./screens.md)'s `HostDetail`. Findings open
  `pages/scans/FindingPanel.tsx` — the same component scan detail uses.

## Notes / gotchas

- **Page-level error, not a findings-section error.** Either read failing shows “Couldn't load
  this host.” plus `[Retry]`. DESIGN §5.6's independent findings retry was not built.
- Opening a finding panel fetches nothing extra; the panel is the embedded `FindingRecord`.

# Citations

[1] [specs/039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md](../../../specs/039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md)
