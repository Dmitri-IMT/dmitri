---
type: Module
title: Backend routers — reads, identity admin, ingest and commands
description: The FastAPI read, identity admin, device revoke/restore, scan/machine deletion, ingest and command-channel HTTP/WS routers with their auth gates.
resource: backend/src/api/routers
tags: [backend, fastapi, routers, read, ingest, auth, tenancy, websocket, command-channel, identity-admin, agents]
timestamp: 2026-10-23T14:36:51Z
---

# Backend routers — reads, identity admin, ingest and commands

## Purpose

`routers/` holds the FastAPI `APIRouter`s that are the wired HTTP/WebSocket surface in the backend beyond
`/api/v1/health`. Each router is a thin adapter: it depends on `get_session`, calls one function in
[`services/read.py`](/backend/services.md) or the agent-channel services, and returns the appropriate
[`schemas`](/backend/schemas.md) model. `main.py` mounts all routers via `app.include_router(...)`.

As of spec 017 / DMI-61 these four routes are no longer open. Each takes
`caller: CallerIdentity = Depends(require_user)` and passes `org_id=caller.org_id` down into the read
service, so the tenant boundary is enforced in SQL rather than in the handler. Remote cancel
(DMI-145) adds admin `POST /commands/{id}/cancel`.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `read_hosts()` | `GET /api/v1/hosts` (optional `page`, `per_page`, `sort_by`, `sort_order`, `group` default `active`) → `list_hosts(...)` → `HostListResponse`. | `backend/src/api/routers/hosts.py:28` |
| `read_host()` | `GET /api/v1/hosts/{host_id}` → `get_host_detail(...)` → `HostDetailResponse`, or `404` if `None` — including for a row belonging to another org. | `backend/src/api/routers/hosts.py:46` |
| `delete_all_hosts_route()` / `delete_host_route()` | Admin-only `DELETE /api/v1/hosts` (`deleteAllHosts`, → `HostDeletionResponse {deleted}`) and `DELETE /api/v1/hosts/{host_id}` (`deleteHost`, `204`; unknown or foreign id → `404`), gated by `require_admin_row`. See [services](/backend/services.md) deletion rows and [ADR-022](../../../docs/adr/ADR-022-scan-and-machine-deletion.md). | `backend/src/api/routers/hosts.py:68`, `:80` |
| `ingest_scan_route()` | `POST /api/v1/scans` (`operation_id="ingestScan"`, `202`) behind `Depends(require_agent)` → `ingest_scan(...)` → `ScanIngestAcceptedResponse`. `ScanOwnershipError` → `403 Forbidden`; `ScanClosedError` → `400 "Scan is no longer accepting results"`. | `backend/src/api/routers/scans.py:32` |
| `read_scans()` | `GET /api/v1/scans` (optional `page`, `per_page`, `status`, `sort_by`, `sort_order`) → `list_scans(...)` → `ScanListResponse`. Empty org or filter mismatch → 200 with an empty page, never 404. | `backend/src/api/routers/scans.py:55` |
| `read_scan()` | `GET /api/v1/scans/{scan_id}` → `get_scan_detail(...)` → `ScanDetailResponse`, or `404` if `None`. | `backend/src/api/routers/scans.py:76` |
| `delete_all_scans_route()` / `delete_scan_route()` | Admin-only `DELETE /api/v1/scans` (`deleteAllScans`, → `ScanDeletionResponse {deleted, skipped, machines_removed}`) and `DELETE /api/v1/scans/{scan_id}` (`deleteScan`, `204`), gated by `require_admin_row`. An unfinished scan → `ScanRunningError` → `409 scan_running`; unknown or foreign id → `404`. | `backend/src/api/routers/scans.py:110`, `:125` |
| `read_scan_ai_analysis()` | `GET /api/v1/scans/{scan_id}/analysis` (`getScanAIAnalysis`) behind `require_user`; `?language=` (`en`/`pt-BR`/`ru`, default `en`) selects the row. See [ai](/backend/ai.md). | `backend/src/api/routers/scans.py:160` |
| `request_scan_ai_analysis_route()` | `POST /api/v1/scans/{scan_id}/analysis` (`requestScanAIAnalysis`, 202), same `?language=`. `409` if already requested for that language. | `backend/src/api/routers/scans.py:185` |
| `read_scan_report()` / `download_scan_report()` | `GET /api/v1/scans/{scan_id}/reports/{kind}` and `/download` (PDF), both with `?language=`. | `backend/src/api/routers/scans.py:305`, `:338` |
| `get_ai_usage()` | `GET /api/v1/ai/usage` (`getAIUsage`) — org-scoped summary + recent rows. | `backend/src/api/routers/ai.py:50` |
| `list_context_chat()` / `list_context_conversations()` / `ask_context_chat()` | Private paginated `GET /api/v1/ai/chat/history` and `/ai/chat/conversations`; `POST /api/v1/ai/chat` returns its saved message and conversation IDs. Scope is `scan`/`host`/`finding`. POST writes usage and transcript in one commit; provider failures commit usage alone. | `backend/src/api/routers/ai.py:135`, `:166`, `:186` |
| `read_findings()` | `GET /api/v1/findings` (optional `page`, `per_page`, `severity`, `scan_id`, `host_id`) → `list_findings(...)` → `FindingListResponse`. Foreign ids → empty page, not 404. | `backend/src/api/routers/findings.py:18` |
| `read_home()` | `GET /api/v1/home` behind `require_user`. Three `Query(1, ge=1)` page integers, no `per_page`. Returns `HomeSnapshot`. Viewers are allowed. | `backend/src/api/routers/home.py:15` |
| `read_current_user()` | `GET /api/v1/users/me` → caller profile (`user_id`, `email`, `role`, `org_name`), with role loaded from the DB row by `require_user_row` and `org_name` from the caller's `Org` row (the SPA's typed confirmation for "delete all" compares against it). | `backend/src/api/routers/users.py:44` |
| `delete_current_user_route()` | `DELETE /api/v1/users/me` (`204`) for either role; maps `LastAdminError` to `409 last_admin`. | `backend/src/api/routers/users.py:36` |
| `list_org_users_route()` | Admin-only `GET /api/v1/users`; returns the caller org's members as `{data: OrgMember[]}`, ordered by activity. Exposes `last_seen_at`, never `last_login_at`. | `backend/src/api/routers/users.py:51` |
| `update_user_role_route()` | Admin-only `PATCH /api/v1/users/{user_id}`, gated by `require_admin_row` so the actor's row is on hand for the activity log. Refuses self-targeting with `409 self_target`, maps last-admin refusal to `409 last_admin`, and returns the updated `OrgMember`; foreign/unknown id → 404. | `backend/src/api/routers/users.py:75` |
| `delete_user_route()` | Admin-only `DELETE /api/v1/users/{user_id}` (`204`), gated by `require_admin_row`. Self-targeting → `409 self_target`; foreign/unknown id → 404. | `backend/src/api/routers/users.py:107` |
| `list_agents_route()` | `GET /api/v1/agents` (`listAgents`) behind `require_user` → `{data: AgentSummary[]}`, org-scoped in SQL. Viewers may read; an org with no agents gets an empty list, never a 404. | `backend/src/api/routers/agents.py:49` |
| `read_agent_route()` | `GET /api/v1/agents/{agent_id}` behind `require_user` → `AgentDetail`, which adds the Pi's currently reported `available_subnets`. Unknown **and** foreign ids both → `404` with the same body. | `backend/src/api/routers/agents.py:62` |
| `update_agent_target_subnet_route()` | Admin-only `PATCH /api/v1/agents/{agent_id}` (`updateAgentTargetSubnet`) → the full `AgentDetail`, so the SPA needs no refetch. Resolution order is fixed: missing/foreign row → `404`, no `hello` report → `409 device_offline`, value the Pi did not report → `422 subnet_not_reported`, then commit. | `backend/src/api/routers/agents.py:74` |
| `revoke_agent_route()` | Admin-only `POST /api/v1/agents/{agent_id}/revoke`. Delegates to the async `revoke_agent()` service and maps `None` to 404 (missing and foreign ids alike). | `backend/src/api/routers/agents.py:106` |
| `restore_agent_route()` | Admin-only `POST /api/v1/agents/{agent_id}/restore`. Clears revocation and returns the full detail; repeat restore is a 200 no-op. | `backend/src/api/routers/agents.py:120` |
| `create_agent_command()` | `POST /api/v1/agents/{agent_id}/commands` behind `require_admin` → `201` + `CommandSummary`. Order: `sweep_stale_commands(agent_id=...)` → `active_command_for` busy check → the reported-subnet check → `enqueue` → `await deliver`. `IntegrityError` from the partial unique index maps to the **same** `409 device_busy`; `SubnetNotReportedError` → `422 subnet_not_reported`; `DeviceOfflineError` → `503 device_offline`. | `backend/src/api/routers/agents.py:144` |
| `read_command()` | `GET /api/v1/commands/{command_id}` → `get_command_detail(...)` → `CommandDetail`, or `404` for an unknown id or another org's command. **Pure read** — the sweep is deliberately not called here. | `backend/src/api/routers/commands.py:18` |
| `cancel_command_route()` | Admin-only `POST /api/v1/commands/{command_id}/cancel` (`cancelCommand`). Connected Pi → send `AgentCancelFrame`, return `202`. Offline or already terminal → retire/idempotent `200`. Missing/foreign → `404`. `uploading` → `409 command_not_cancellable`. | `backend/src/api/routers/commands.py:42` |
| `connect_agent_commands()` | `WebSocket /api/v1/agents/{agent_id}/commands` — `require_agent_ws` → `accept()` → `agent_connections.register` + `mark_connected` → `run_agent_channel(session_factory, ...)` → `finally: unregister` + `mark_disconnected`. Inbound `hello`/`status`; after hello, catch-up may send `AgentCancelFrame`s; `status` drives `apply_status`, and commands are delivered outbound over this socket by `deliver`. | `backend/src/api/routers/agents.py:181` |

## How it connects

- **Upstream** — mounted in [`main.py`](/backend/api.md) via `app.include_router`.
- **Downstream** — each handler calls exactly one function in
  [`services/read.py`](/backend/services.md), which queries the [ORM models](/backend/models.md)
  (`HostRecord`, `ScanHostRecord`, `ScanRecord`, `FindingRecord`, `PortRecord`) and returns
  [`schemas/read.py`](/backend/schemas.md) models directly as `response_model`.

## Notes / gotchas

- **All three list routes validate paging identically.** `read_hosts`, `read_scans` and
  `read_findings` each declare `page: int = Query(1, ge=1)` and
  `per_page: int = Query(20, ge=1, le=100)`, matching the contract's `Page`/`PerPage` parameters, so
  an out-of-range value is refused with a 422 rather than clamped. `read_hosts` spells the two
  defaults as `DEFAULT_PAGE` / `DEFAULT_PER_PAGE` imported from
  [`services/read.py`](/backend/services.md) rather than repeating the literals its service already
  defaults to; `read_scans` and `read_findings` still inline them. `read_hosts` gained these params
  in DMI-84 — before that it accepted no paging params and `list_hosts` silently capped every
  response at 20 rows while `total` reported the true count. DMI-100 then gave it
  `sort_by: HostSortBy = Query("last_seen_at")` and `sort_order: SortOrder = Query("desc")` in the
  same shape `read_scans` uses, so only the `status`/`severity`-style **filter** params are still
  specific to `read_scans` and `read_findings`. The contract also declares a free-text `q` on
  `/api/v1/hosts` that `read_hosts` deliberately does not accept — search is cut from v1, and the
  fidelity gate carries a named exemption for it (see [contracts](/contracts.md)).
- **`DELETE /users/me` must stay declared above `DELETE /users/{user_id}`.** FastAPI matches in
  registration order; with the parameterised path first, `/users/me` is parsed as a uuid path param
  and answers `422` instead of deleting the caller. Both `/me` operations sit above it in the file.
- **The two 409s are raised literally in the handler bodies, on purpose.**
  `test_contract_fidelity.py::test_error_code_fidelity` AST-scans each named route function for
  literal `ApiError(...)` calls, so raising `last_admin` from
  [`services/users.py`](/backend/services.md) instead of mapping it in the router would make the
  contract gate blind to it. The `404` stays a bare `HTTPException` — `DEFAULT_CODES_BY_STATUS`
  already yields `not_found`.
- **Self-targeting is `409 self_target`, not `404`.** The caller can see their own row on the Users
  screen, so denying its existence would be a lie the SPA then has to word around; the caller holds
  every permission and it is the request's shape that refuses. A foreign-org target *is* `404`, per
  the read path's convention below.
- **Removal is a hard delete with no revocation step.** The FK cascade on `refresh_tokens` /
  `password_reset_tokens` ([migrations](/backend/migrations.md)) is the session teardown; neither
  route touches `services/auth.py` and neither sets `Set-Cookie`. The already-issued access token
  stays usable for its remaining ~15 minutes on the claims-only routes — known bug **DMI-104**,
  deliberately not patched here.
- **A foreign row is 404, never 403.** The read service returns `None` for a row outside the
  caller's org and the router turns that into a 404; answering 403 would confirm the row exists in
  some other tenant.
- **Revoke commits before closing the socket.** A frame or delivery that races the close therefore
  sees `revoked_at` through the existing DMI-97 gates. Restore does no socket work; the Pi's hourly
  redial is the recovery path.
- **Business reads and identity-admin reads use different gates.** Scan/host/finding reads and
  `/users/me` accept viewers; `GET /users`, role changes, invite listing/revocation, and invite
  creation require `require_admin`. The four admin **mutations** (role change, member removal,
  invite create, invite revoke) use `require_admin_row` instead, which adds the caller's `User`
  row — see [auth](/backend/auth.md). `test_auth_wiring.py` walks nested dependencies, so it
  still sees the admin gate through that pairing.
- **`read_findings`'s `host_id` is not a tenant escape.** The org predicate is applied in
  `list_findings` independently of the `host_id` branch, so asking for a foreign host's id returns
  empty rather than another org's findings.
- **`POST /commands` answers 403, not 404, for an unknown or cross-org `agent_id`** — the published
  contract defines only 401/403/409/503/500 for that operation, so there is no 404 to return.
  `GET /commands/{id}` keeps the read path's 404-for-foreign-row convention.
- **Both 409 paths return the same body.** The read-side busy check and the unique-index
  `IntegrityError` (a double-clicked "Scan now") are indistinguishable to the caller by design —
  `_device_busy_error()` is the single constructor.
- **`routers/agents.py` now answers 403 and 404 for the same unknown id, depending on the verb.**
  `POST /commands` keeps its 403 (the contract publishes no 404 for it); the DMI-78 read and PATCH
  routes follow the read path's 404-for-foreign-row convention. That is a contract constraint, not
  an inconsistency to tidy.
- **The PATCH's 409 and 422 are literal `ApiError(...)` calls in the handler body**, for the same
  AST-scan reason as the users routes above — as is the new `422 subnet_not_reported` arm on
  `create_agent_command`. Each maps to its **own** contract response component
  (`AgentOfflineConflict`, `TargetSubnetNotReported`, `ScanSubnetNotReported`), because
  `ERROR_RESPONSE_ROUTES` maps one component to exactly one handler; collapsing two of them onto a
  shared component would leave one literal unverified.
- **`device_offline` on the PATCH is a 409, not the WS path's 503.** Same machine code, different
  meaning: 503 says delivery failed, 409 says you cannot choose a network for a Pi that is not
  reporting one. The connected-but-pre-`hello` case answers the same 409 — one
  `get_hello() is None` check covers both.
- **The two OPTIONS preflights use the `@router.options(...)` decorator** with no path parameter
  declared, matching `routers/commands.py`; the older `add_api_route` preflight on
  `/agents/{agent_id}/commands` is left as it was.
- **The command routes split across two files on purpose.** The write path hangs off the agent
  (`routers/agents.py`, alongside the WS handler that delivers it); the read path is command-scoped
  and org-scoped, so it gets its own `routers/commands.py`.
- **Ingest and read share `routers/scans.py`.** `POST /api/v1/scans` sits in the same module as the
  two read routes but is the only one behind [device auth](/backend/device-auth.md)
  (`require_agent`) rather than `require_user` — a Pi submits, a human reads.
- **The ingest router is a thin adapter and owns no rules.** Ownership, terminal-state refusal and
  idempotency all live in [`ingest_scan`](/backend/services.md); the handler only translates
  `ScanOwnershipError` → 403 and `ScanClosedError` → 400. Do not reimplement those checks here.
- **Auth runs before body validation on ingest.** Declaring `payload: ScanIngestRequest` as a plain
  body param while `require_agent` is a sub-`Depends` means FastAPI solves the dependency first, so
  an unsigned request carrying an invalid body answers **401, not 422**. The one exception is a body
  that is not valid JSON at all — decoding precedes dependency solving, so that is a 422.
- **Ingest status codes.** `401` unauthenticated (bad/missing/stale signature, replayed nonce);
  `403` revoked device or a scan owned by another agent/org; `400` results arriving after the
  command was written off; `422` payload shape. A separately re-signed repeat is accepted and writes
  nothing new; a byte-identical replay is 401 on the nonce.
- Auth and invite routes live in `routers/auth.py` and `routers/invites.py` but are documented
  separately — see [auth](/backend/auth.md). `GET /api/v1/users/me` closes contract ask C16 — role
  is authoritative from the profile resource, not the JWT. The agent command channel and ingest are
  the product routes mounting [device auth](/backend/device-auth.md) (`require_agent_ws` /
  `require_agent`).

# Citations

[1] [specs/015-read-path](../../../specs/015-read-path/TRUTH.md)
[2] [docs/adr/ADR-014-host-identity-resolution.md](../../../docs/adr/ADR-014-host-identity-resolution.md)
[3] [specs/018-agent-ws-command-channel](../../../specs/018-agent-ws-command-channel/TRUTH.md)
[4] [specs/019-users-me-and-error-envelope](../../../specs/019-users-me-and-error-envelope/TRUTH.md)
[5] [specs/021-scan-list-and-finding-filters](../../../specs/021-scan-list-and-finding-filters/TRUTH.md)
[6] [specs/022-command-enqueue-delivery](../../../specs/022-command-enqueue-delivery/plan.md)
[7] [specs/024-scan-ingest-endpoint](../../../specs/024-scan-ingest-endpoint/TRUTH.md)
[8] [specs/029-account-removal-api](../../../specs/029-account-removal-api/TRUTH.md)
[9] [docs/adr/ADR-017-account-removal.md](../../../docs/adr/ADR-017-account-removal.md)
[10] [specs/030-users-invites-admin-api](../../../specs/030-users-invites-admin-api/TRUTH.md)
[11] [specs/031-agents-read-surface-target-subnet](../../../specs/031-agents-read-surface-target-subnet/TRUTH.md)
[12] [specs/048-parked-channel-recovery](../../../specs/048-parked-channel-recovery/TRUTH.md)
