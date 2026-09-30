---
type: Module
title: frontend detail read state
description: readDetailState turns one detail query into loading/error/notFound/ready, ReadDetailGate renders the three non-ready states with back links, and each independent second read owns its own section states.
resource: frontend/src/lib/detailState.ts
tags: [frontend, hosts, scans, devices, tanstack-query]
timestamp: 2026-09-30T00:00:00Z
---

# frontend detail read state

## Purpose

A detail screen renders a **state**, never raw query flags. `readDetailState` is the one place the
404-versus-error rule lives, and `ReadDetailGate` ([tables](./tables.md)) is the one place those
states are **rendered** — neither `/scans/:scanId`, `/network/:hostId`, nor `/devices/:agentId`
switches over them itself.

One read per gate. Host detail makes a second, independent read (that host's findings), and it is
**not** folded into the page state: a pending or failed findings read must not throw away a host
whose identity, profile, exposures, ports and history already arrived. Identity and services come from `HostDetailResponse`
(`machine_type`, optional `device_profile`, `ExposureRead[]`, `HostPort[]`); findings carry `host_hostname` / `first_seen_at` on the same
`FindingRecord` shape.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `DetailState<T>` | `{ state: 'loading' }` / `{ state: 'error'; retry }` / `{ state: 'notFound' }` / `{ state: 'ready'; data: T }`. | `frontend/src/lib/detailState.ts:4` |
| `readDetailState(id, query)` | Empty `id` **or** a 404 (`readApiError(...).status === 404`) is `notFound`; any other error carries a `retry` that refetches; pending is `loading`; otherwise `ready` with the data. Called inline by `ScanDetail`, `HostDetail`, and `DeviceDetail`. | `frontend/src/lib/detailState.ts:10` |
| `ReadDetailGate` `backTo` / `backLabel` | Required on every detail gate. `NotFoundNotice` renders a real back link using both props — `/network` for machines, `/devices` for boxes. | `frontend/src/components/ReadDetailGate.tsx:12` |
| `HostFindings` | The host's findings section: its own `useQuery` on `listFindings({ host_id, per_page: 100 })`, its own open-row state, and its own three states. Retrying it refetches findings only. | `frontend/src/pages/hosts/HostFindings.tsx:11` |
| `HostProfile` | Renders the structured operating-system name and Nmap accuracy with the stored device profile, confidence, evidence, conflicts, and limitations; missing fields remain unknown and are never inferred in the browser. | `frontend/src/pages/hosts/HostProfile.tsx:59` |
| `HostExposures` | Renders latest-scan exposure inventory or the explicit legacy-unavailable state from `HostDetailResponse`. | `frontend/src/pages/hosts/HostExposures.tsx:7` |

## How it connects

- Consumes [api](./api.md)'s `getHost`, `getScan`, `getAgent`, and `listFindings`.
- Scan, host and device detail screens hand `readDetailState`'s result to `ReadDetailGate`
  ([tables](./tables.md)), which owns the `NotFoundNotice` / `ErrorRetry` / placeholder-header
  chrome. `HostFindings` sits inside the host gate's ready view inside a `Card` shell (see
  [screens](./screens.md)).
- Findings on both scan and host screens open `pages/scans/FindingPanel.tsx` inside the shared
  `FindingsTable`.

## Notes / gotchas

- **The gate stops at `ready`.** Scan detail's failed / unfinished split stays inside `ScanDetail`:
  those are domain states of a scan, not read states of a query.
- **Two reads, two states — deliberately on host detail.** Do not reintroduce `useHostDetail`.
- **Page error copy differs from section error copy**: "Couldn't load this machine." (host read) vs
  "Couldn't load this machine's findings." (findings read). Device detail uses device wording.
- Opening a finding panel fetches nothing extra; the panel is the embedded `FindingRecord`.

# Citations

[1] [specs/039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md](../../../specs/039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md)
[2] [specs/042-design-system/TRUTH.md](../../../specs/042-design-system/TRUTH.md)
