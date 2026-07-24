---
type: Module
title: Backend routers — hosts, scans, findings
description: The three FastAPI routers that wire the read path — GET /hosts, /hosts/{id}, /scans/{id}, /findings.
resource: backend/src/api/routers
tags: [backend, fastapi, routers, read]
timestamp: 2026-07-22T00:00:00Z
---

# Backend routers — hosts, scans, findings

## Purpose

`routers/` holds the FastAPI `APIRouter`s that are the only wired HTTP surface in the backend beyond
`/api/v1/health`. Each router is a thin adapter: it depends on `get_session`, calls one function in
[`services/read.py`](/backend/services.md), and returns the [`read.py` response model](/backend/schemas.md)
that function built. `main.py` mounts all three via `app.include_router(...)`.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `read_hosts()` | `GET /api/v1/hosts` → `list_hosts(session)` → `HostListResponse`. | `backend/src/api/routers/hosts.py:15` |
| `read_host()` | `GET /api/v1/hosts/{host_id}` → `get_host_detail(session, host_id)` → `HostDetailResponse`, or `404` if `None`. | `backend/src/api/routers/hosts.py:20` |
| `read_scan()` | `GET /api/v1/scans/{scan_id}` → `get_scan_detail(session, scan_id)` → `ScanDetailResponse`, or `404` if `None`. | `backend/src/api/routers/scans.py:15` |
| `read_findings()` | `GET /api/v1/findings` (optional `host_id` query param) → `list_findings(session, host_id=host_id)` → `FindingListResponse`. | `backend/src/api/routers/findings.py:15` |

## How it connects

- **Upstream** — mounted in [`main.py`](/backend/api.md) via `app.include_router`.
- **Downstream** — each handler calls exactly one function in
  [`services/read.py`](/backend/services.md), which queries the [ORM models](/backend/models.md)
  (`HostRecord`, `ScanHostRecord`, `ScanRecord`, `FindingRecord`, `PortRecord`) and returns
  [`schemas/read.py`](/backend/schemas.md) models directly as `response_model`.

## Notes / gotchas

- No pagination query params are exposed yet on `read_hosts`/`read_findings` — `list_hosts` /
  `list_findings` default to `page=1, per_page=20` internally; the routers don't forward `page`.
- Auth routes live in `routers/auth.py` but are documented separately — see [auth](/backend/auth.md).
  Ingest (`POST /api/v1/scans`) is still not wired — see the note in [api](/backend/api.md).

# Citations

[1] [specs/015-read-path](../../../specs/015-read-path/TRUTH.md)
[2] [docs/adr/ADR-014-host-identity-resolution.md](../../../docs/adr/ADR-014-host-identity-resolution.md)
