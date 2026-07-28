---
type: Module
title: Backend routers — hosts, scans, findings
description: The five FastAPI routers on the read path plus users/me and the agent WebSocket command channel — GET /hosts, /hosts/{id}, /scans, /scans/{id}, /findings, GET /users/me (behind require_user_row) and WSS /agents/{agent_id}/commands (behind require_agent_ws).
resource: backend/src/api/routers
tags: [backend, fastapi, routers, read, auth, tenancy, websocket, command-channel]
timestamp: 2026-07-27T22:15:00Z
---

# Backend routers — hosts, scans, findings

## Purpose

`routers/` holds the FastAPI `APIRouter`s that are the wired HTTP/WebSocket surface in the backend beyond
`/api/v1/health`. Each router is a thin adapter: it depends on `get_session`, calls one function in
[`services/read.py`](/backend/services.md) or the agent-channel services, and returns the appropriate
[`schemas`](/backend/schemas.md) model. `main.py` mounts all routers via `app.include_router(...)`.

As of spec 017 / DMI-61 these four routes are no longer open. Each takes
`caller: CallerIdentity = Depends(require_user)` and passes `org_id=caller.org_id` down into the read
service, so the tenant boundary is enforced in SQL rather than in the handler.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `read_hosts()` | `GET /api/v1/hosts` → `list_hosts(session, org_id=caller.org_id)` → `HostListResponse`. | `backend/src/api/routers/hosts.py` |
| `read_host()` | `GET /api/v1/hosts/{host_id}` → `get_host_detail(...)` → `HostDetailResponse`, or `404` if `None` — including for a row belonging to another org. | `backend/src/api/routers/hosts.py` |
| `read_scans()` | `GET /api/v1/scans` (optional `page`, `per_page`, `status`, `sort_by`, `sort_order`) → `list_scans(...)` → `ScanListResponse`. Empty org or filter mismatch → 200 with an empty page, never 404. | `backend/src/api/routers/scans.py:22` |
| `read_scan()` | `GET /api/v1/scans/{scan_id}` → `get_scan_detail(...)` → `ScanDetailResponse`, or `404` if `None`. | `backend/src/api/routers/scans.py:43` |
| `read_findings()` | `GET /api/v1/findings` (optional `page`, `per_page`, `severity`, `scan_id`, `host_id`) → `list_findings(...)` → `FindingListResponse`. Foreign ids → empty page, not 404. | `backend/src/api/routers/findings.py:16` |
| `read_current_user()` | `GET /api/v1/users/me` → takes the caller's `User` from `require_user_row` (which owns the lookup and the missing-row 401) and returns `UserProfileResponse` with **role from the DB row**, not JWT claims. Read-only, no path param. | `backend/src/api/routers/users.py:13` |
| `connect_agent_commands()` | `WebSocket /api/v1/agents/{agent_id}/commands` — `require_agent_ws` → `accept()` → `agent_connections.register` + `touch_agent_last_seen` → `run_agent_channel` → `finally: unregister`. Inbound `hello`/`status` frames only; no command delivery. | `backend/src/api/routers/agents.py` |

## How it connects

- **Upstream** — mounted in [`main.py`](/backend/api.md) via `app.include_router`.
- **Downstream** — each handler calls exactly one function in
  [`services/read.py`](/backend/services.md), which queries the [ORM models](/backend/models.md)
  (`HostRecord`, `ScanHostRecord`, `ScanRecord`, `FindingRecord`, `PortRecord`) and returns
  [`schemas/read.py`](/backend/schemas.md) models directly as `response_model`.

## Notes / gotchas

- `read_hosts` still ignores contract `page`/`per_page` — `list_hosts` defaults internally; only
  `read_scans` and `read_findings` expose pagination and filter query params on the wire.
- **A foreign row is 404, never 403.** The read service returns `None` for a row outside the
  caller's org and the router turns that into a 404; answering 403 would confirm the row exists in
  some other tenant.
- **`viewer` and `admin` both read.** These four routes require only `require_user`, per the AUTH.md
  role matrix — `require_admin` gates invitation, not reading.
- **`read_findings`'s `host_id` is not a tenant escape.** The org predicate is applied in
  `list_findings` independently of the `host_id` branch, so asking for a foreign host's id returns
  empty rather than another org's findings.
- Auth and invite routes live in `routers/auth.py` and `routers/invites.py` but are documented
  separately — see [auth](/backend/auth.md). `GET /api/v1/users/me` closes contract ask C16 — role
  is authoritative from the profile resource, not the JWT. Ingest (`POST /api/v1/scans`) is still
  not wired — see the note in [api](/backend/api.md). The agent command channel is the first product
  route mounting [device auth](/backend/device-auth.md) (`require_agent_ws`).

# Citations

[1] [specs/015-read-path](../../../specs/015-read-path/TRUTH.md)
[2] [docs/adr/ADR-014-host-identity-resolution.md](../../../docs/adr/ADR-014-host-identity-resolution.md)
[3] [specs/018-agent-ws-command-channel](../../../specs/018-agent-ws-command-channel/TRUTH.md)
[4] [specs/019-users-me-and-error-envelope](../../../specs/019-users-me-and-error-envelope/TRUTH.md)
[5] [specs/021-scan-list-and-finding-filters](../../../specs/021-scan-list-and-finding-filters/TRUTH.md)
