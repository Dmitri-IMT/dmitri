---
type: Module
title: Backend routers — hosts, scans, findings
description: The three FastAPI routers that wire the read path — GET /hosts, /hosts/{id}, /scans/{id}, /findings — now behind require_user and scoped to the caller's org.
resource: backend/src/api/routers
tags: [backend, fastapi, routers, read, auth, tenancy]
timestamp: 2026-07-27T00:00:00Z
---

# Backend routers — hosts, scans, findings

## Purpose

`routers/` holds the FastAPI `APIRouter`s that are the only wired HTTP surface in the backend beyond
`/api/v1/health`. Each router is a thin adapter: it depends on `get_session`, calls one function in
[`services/read.py`](/backend/services.md), and returns the [`read.py` response model](/backend/schemas.md)
that function built. `main.py` mounts all three via `app.include_router(...)`.

As of spec 017 / DMI-61 these four routes are no longer open. Each takes
`caller: CallerIdentity = Depends(require_user)` and passes `org_id=caller.org_id` down into the read
service, so the tenant boundary is enforced in SQL rather than in the handler.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `read_hosts()` | `GET /api/v1/hosts` → `list_hosts(session, org_id=caller.org_id)` → `HostListResponse`. | `backend/src/api/routers/hosts.py` |
| `read_host()` | `GET /api/v1/hosts/{host_id}` → `get_host_detail(...)` → `HostDetailResponse`, or `404` if `None` — including for a row belonging to another org. | `backend/src/api/routers/hosts.py` |
| `read_scan()` | `GET /api/v1/scans/{scan_id}` → `get_scan_detail(...)` → `ScanDetailResponse`, or `404` if `None`. | `backend/src/api/routers/scans.py` |
| `read_findings()` | `GET /api/v1/findings` (optional `host_id` query param) → `list_findings(..., host_id=host_id)` → `FindingListResponse`. | `backend/src/api/routers/findings.py` |

## How it connects

- **Upstream** — mounted in [`main.py`](/backend/api.md) via `app.include_router`.
- **Downstream** — each handler calls exactly one function in
  [`services/read.py`](/backend/services.md), which queries the [ORM models](/backend/models.md)
  (`HostRecord`, `ScanHostRecord`, `ScanRecord`, `FindingRecord`, `PortRecord`) and returns
  [`schemas/read.py`](/backend/schemas.md) models directly as `response_model`.

## Notes / gotchas

- No pagination query params are exposed yet on `read_hosts`/`read_findings` — `list_hosts` /
  `list_findings` default to `page=1, per_page=20` internally; the routers don't forward `page`.
- **A foreign row is 404, never 403.** The read service returns `None` for a row outside the
  caller's org and the router turns that into a 404; answering 403 would confirm the row exists in
  some other tenant.
- **`viewer` and `admin` both read.** These four routes require only `require_user`, per the AUTH.md
  role matrix — `require_admin` gates invitation, not reading.
- **`read_findings`'s `host_id` is not a tenant escape.** The org predicate is applied in
  `list_findings` independently of the `host_id` branch, so asking for a foreign host's id returns
  empty rather than another org's findings.
- Auth and invite routes live in `routers/auth.py` and `routers/invites.py` but are documented
  separately — see [auth](/backend/auth.md). Ingest (`POST /api/v1/scans`) is still not wired — see
  the note in [api](/backend/api.md).

# Citations

[1] [specs/015-read-path](../../../specs/015-read-path/TRUTH.md)
[2] [docs/adr/ADR-014-host-identity-resolution.md](../../../docs/adr/ADR-014-host-identity-resolution.md)
