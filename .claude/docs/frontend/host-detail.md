---
type: Module
title: frontend detail read state
description: readDetailState turns one detail query into loading/error/notFound/ready, ReadDetailGate renders the three non-ready states, and each independent second read owns its own section states.
resource: frontend/src/lib/detailState.ts
tags: [frontend, hosts, scans, findings, tanstack-query]
timestamp: 2026-08-27T16:30:00Z
---

# frontend detail read state

## Purpose

A detail screen renders a **state**, never raw query flags. `readDetailState` is the one place the
404-versus-error rule lives, and `ReadDetailGate` ([tables](./tables.md)) is the one place those
states are **rendered** — neither `/scans/:scanId` nor `/hosts/:hostId` switches over them itself.

One read per gate. Host detail makes a second, independent read (that host's findings), and it is
**not** folded into the page state: a pending or failed findings read must not throw away a host
whose identity, ports and history already arrived (DESIGN §5.6, TRUTH rule 23).

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `DetailState<T>` | `{ state: 'loading' }` / `{ state: 'error'; retry }` / `{ state: 'notFound' }` / `{ state: 'ready'; data: T }`. | `frontend/src/lib/detailState.ts:4` |
| `readDetailState(id, query)` | Empty `id` **or** a 404 (`readApiError(...).status === 404`) is `notFound`; any other error carries a `retry` that refetches; pending is `loading`; otherwise `ready` with the data. Called inline by `ScanDetail` and by `HostDetail` — one `useQuery` each, so neither earns a hook wrapper. | `frontend/src/lib/detailState.ts:10` |
| `HostFindings` | The host's findings section: its own `useQuery` on `listFindings({ host_id, per_page: 100 })`, its own open-row state, and its own three states — skeleton while pending, `host-findings-error` + Retry on failure, the positive sentence when empty. Retrying it refetches findings only; the host record is a separate key. | `frontend/src/pages/hosts/HostFindings.tsx:11` |

## How it connects

- Consumes [api](./api.md)'s `getHost`, `getScan` and `listFindings`.
- Both detail screens hand `readDetailState`'s result to `ReadDetailGate`
  ([tables](./tables.md)), which owns the `NotFoundNotice` / `ErrorRetry` / placeholder-header
  chrome. `HostFindings` sits inside the gate's ready view, alongside the ports and history
  tables (see [screens](./screens.md)).
- Findings on both screens open `pages/scans/FindingPanel.tsx` inside the shared `FindingsTable`.

## Notes / gotchas

- **The gate stops at `ready`.** Scan detail's failed / unfinished split stays inside `ScanDetail`:
  those are domain states of a scan, not read states of a query.
- **Two reads, two states — deliberately.** The earlier `useHostDetail` hook folded them into one
  `DetailState`, which blanked a loaded host whenever findings were pending or failed. It was
  deleted; do not reintroduce it. The `useHomeReview` / `useOrgDirectory` fold is right *there*
  because those reads compose into a single verdict — these two do not.
- **Page error copy differs from section error copy**: "Couldn't load this host." (host read) vs
  "Couldn't load this host's findings." (findings read). Both carry `[Retry]`.
- Opening a finding panel fetches nothing extra; the panel is the embedded `FindingRecord`.

# Citations

[1] [specs/039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md](../../../specs/039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md)
[2] [specs/039-frontend-scans-hosts-read-surfaces/DESIGN.md](../../../specs/039-frontend-scans-hosts-read-surfaces/DESIGN.md)
