---
type: Module
title: Backend services — persistence, host identity, read, enrichment, risk
description: Backend business logic for ingest, reads, enrichment, command delivery and cancel, presence, and idempotent device revoke/restore.
resource: backend/src/api/services/persistence.py
tags: [backend, services, persistence, ingest, read, enrichment, worker, risk, command-channel, presence, tenancy, agents, cancel]
timestamp: 2026-09-28T00:00:00Z
---

# Backend services — persistence, host identity, read, enrichment, risk

## Purpose

`services/` is where the backend actually does its work. `persistence.py` writes an ingested
`ScanIngestRequest` into the [tables](/backend/models.md), resolves host identity, and enqueues
enrichment jobs; since DMI-63 it also owns the **authorisation and lifecycle rules** for ingest via
`ingest_scan`. Since DMI-145 a late upload is accepted when the command is already `cancelled`
(other terminal commands still get `ScanClosedError`). `hosts.py` resolves each scan's
`ScanHostRecord`s to durable `HostRecord`s.
`inventory.py` reconciles durable `host_ports` / `host_findings` / `machine_type` /
`vulnerability_count` after identity is written. `read.py` answers
the wired [read-path routers](/backend/routers.md) — list/detail queries over hosts, scans, and
findings. `worker.py` is the long-running poll loop. `enrichment.py` claims and processes jobs,
calling the three upstream clients — `nvd.py`, `kev.py`, `epss.py` — each of which caches in the DB.
`risk.py` computes a deterministic, explainable risk score. `commands.py` owns **all** DB work for
the command channel — enqueue, the busy check, the atomic status transition, the staleness sweep and
WebSocket delivery — and `agent_presence.py` projects socket connectedness into `agents.connected_at`
so the worker process can reason about it without reading the API's memory.
(`services/__init__.py` is a placeholder.) `ingest_scan` is now reached over HTTP via
`POST /api/v1/scans` ([routers](/backend/routers.md)) alongside the read path, the
[auth routes](/backend/auth.md) and the command routes; the enrichment worker is still driven by the
poll loop rather than a live agent.
`agents.py` joins the persisted `agents` row with the in-memory connection registry for list/detail,
stores the chosen `target_subnet`, and owns the idempotent admin revoke/restore writes.
`users.py` owns account removal plus member listing and role changes. `org_lock.py` supplies the
transaction-scoped per-org advisory lock that serializes admin-reducing role changes.
The auth services (`auth.py`, `tokens.py`, `passwords.py`, `mailer.py`) are documented in
[auth](/backend/auth.md).

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `ScanOwnershipError` / `ScanClosedError` | The two ingest refusals, mapped by the router to `403` / `400`. | `backend/src/api/services/persistence.py:27`, `:31` |
| `ingest_scan()` | The ingest gate. Three cases on `session.get(ScanRecord, scan_id)`: **A** unknown id → `persist_scan(command=None)`, creating an unrequested scan complete; **B** already `completed` → verify `agent_id`/`org_id` match (else `ScanOwnershipError`) and return it untouched, so a late progress report is a no-op; **C** placeholder → `command_for_scan`, reject a missing/foreign command with `ScanOwnershipError` and a terminal one with `ScanClosedError` **except** `cancelled` (DMI-145 late partial), else fill it. | `backend/src/api/services/persistence.py` |
| `persist_scan()` | Keyword signature `(session, scan, *, org_id, agent_id, command, now)`. Fills the requested placeholder or inserts an unrequested scan; on success sets command to `cancelled` when the command was already `cancelled` or `metadata.terminated_by == "user_cancel"`, else `done`; activity is `scan_cancelled` in those cases instead of `scan_finished`. | `backend/src/api/services/persistence.py` |
| `persist_industrial_services()` | Load existing services and units for the scan host once, upsert in memory, flush after services then after units. | `backend/src/api/services/industrial.py:42` |
| `upsert_finding()` | Dedups on `finding_dedupe_key`. New → insert (initial confidence `probable` if `cve_id` else `tentative`) + `refresh_risk_snapshot`. Existing → merge references/source-labels, take `_max_severity`/`_max_confidence`, prefer the higher cvss, re-run risk. | `backend/src/api/services/persistence.py:161` |
| `finding_dedupe_key()` | `ip|protocol|port|unit_id or na|(cve_id or lowercased title)`. | `backend/src/api/services/persistence.py:244` |
| `_persist_scan_host()` | Inserts one `ScanHostRecord` (`ip`/`mac`/`hostname`/`vendor`) for the scan. | `backend/src/api/services/persistence.py:262` |
| `_enqueue_enrichment_jobs()` | One `nvd_cpe` job per `(port, CPE)`; per finding with a `cve_id` → `nvd_cve` + `kev_cve` + `epss_cve`, dedup via a `seen` set. | `backend/src/api/services/persistence.py:302` |
| `command_for_scan()` | Looks up the `Command` a `scan_id` belongs to, or `None`. Used by `ingest_scan` for the Case C ownership check. | `backend/src/api/services/commands.py:111` |
| `LastAdminError` | Refuses a self-delete or role change that would leave the org without an admin; routers map it to `409 last_admin`. | `backend/src/api/services/users.py:12` |
| `count_org_admins()` | Counts admin rows in one org. Role change calls it only after taking the org advisory lock. | `backend/src/api/services/users.py:16` |
| `list_org_members()` | Returns one org's users ordered by `last_seen_at DESC NULLS LAST`, then `id` for deterministic ties. | `backend/src/api/services/users.py:24` |
| `change_member_role()` | Takes `actor: User` (the row `require_admin_row` loaded) and the org-admin advisory lock, performs an org-scoped lookup, protects the final admin, writes the role, appends `role_changed`, and commits. Unknown/foreign target returns `None`. | `backend/src/api/services/users.py:35` |
| `delete_self()` | Appends `account_deleted` then hard-deletes the caller unless they are their org's only admin. | `backend/src/api/services/users.py:77` |
| `delete_member()` | Takes `actor: User`. Appends `member_removed` then org-scoped hard delete; unknown and foreign identifiers both return `False`. | `backend/src/api/services/users.py:94` |
| `append_activity()` | Inserts one `activity` row in the caller's transaction. Duplicate unique key is a no-op. Does not commit. | `backend/src/api/services/activity.py:37` |
| `append_scan_activity()` | The single writer for `scan_started` / `scan_finished` / `scan_failed` / `scan_cancelled`. Takes `org_id`, `scan_id`, `scan_mode` and `occurred_at` from the caller. Best-effort: insert runs in a savepoint; on `SQLAlchemyError` logs `logger.exception("Failed to append scan activity")` and does not abort the caller's transaction. | `backend/src/api/services/activity.py:50` |
| `activity_text()` | Admin/viewer sentence matrix. Scan and machine rows are identical across roles. | `backend/src/api/services/activity.py:45` |
| `read_home_snapshot()` | Attention page, notices, review state, paged activity, derived events. | `backend/src/api/services/home.py:188` |
| `page_attention()` | Latest-scan findings with `host_hostname` from current `HostRecord.hostname`. Starts from `read.finding_read_query()` and adds only the attention filters and sort. | `backend/src/api/services/home.py:46` |
| `derive_home_events()` | Current-state box-offline, member-idle, and new-machine facts. Revoked agents are deliberately excluded from box-offline events. Member idle is one SQL predicate over `users`; box offline stays a Python loop because it needs the registry overlay. Never stored. | `backend/src/api/services/home.py:103` |
| `build_notices()` | Only remaining notice kind is `failed_scan`. The `stale_coverage` ("No successful scan in N days") notice was removed end to end — DMI-179 — service, `HomeNoticeKind`, the OpenAPI enum and the generated frontend types. | `backend/src/api/services/home.py:177` |
| `ORG_ADMIN_LOCK_NAMESPACE` / `lock_org_admins()` | Namespace `8818`; executes two-key `pg_advisory_xact_lock(namespace, hashtext(org_id))`, released automatically on commit or rollback. | `backend/src/api/services/org_lock.py:8` |
| `_fields()` | The single builder behind both agent shapes, including persisted `revoked_at`, registry-derived `online`/`last_seen_at`, target subnet, and active command. | `backend/src/api/services/agents.py:18` |
| `list_agents()` | Org's agents ordered `created_at, id` → `AgentSummary[]`. Keyword-only `org_id`, filtered in SQL. | `backend/src/api/services/agents.py:31` |
| `get_agent_detail()` / `_detail()` | Summary fields plus `available_subnets` from `agent_connections.get_hello(...)`; unknown or foreign id → `None`. | `backend/src/api/services/agents.py:54`, `:46` |
| `set_target_subnet()` | Admin write. Foreign/unknown row → `None`; no `hello` → `AgentOfflineError`; an unreported value → `SubnetNotReportedError`; else commit and return detail. | `backend/src/api/services/agents.py:63` |
| `revoke_agent()` / `restore_agent()` / `_set_revoked_at()` | Org-scoped idempotent writes through one `_set_revoked_at` helper. Revoke keeps the first timestamp and is async: it commits in a threadpool, then closes any registered socket with `4001 revoked`, so the write and the socket kill have one owner (the same shape as `deliver()`). Restore clears the timestamp. Both preserve identity, name and target subnet and return the same detail shape as GET. | `backend/src/api/services/agents.py:94`, `:111`, `:81` |
| `AgentOfflineError` | "Cannot choose a network for a Pi that is reporting none" — router maps it to `409 device_offline`. Lives here, unlike `SubnetNotReportedError`. | `backend/src/api/services/agents.py:13` |
| `SubnetNotReportedError` | Declared in `commands.py` beside `AgentNotFoundError`/`DeviceBusyError`/`DeviceOfflineError` and imported by `agents.py`; raised by both `_claim_agent` and `set_target_subnet`, mapped to `422 subnet_not_reported`. | `backend/src/api/services/commands.py:44` |
| `identity_key()` | `mac:<MAC upper>` if a MAC is present, else `ip:<ip>` — the durable-identity key. | `backend/src/api/services/hosts.py:17` |
| `upsert_hosts_for_scan()` | For every `ScanHostRecord` in the scan: looks up a `HostRecord` by `(org_id, identity_key)`; creates one on first sight, else updates it **only if this scan is the newest seen so far** (extends `first_seen_at`, and on newest overwrites the ip/mac/hostname/vendor snapshot + `open_ports_count`/`highest_severity`); sets `scan_host.host_id`. | `backend/src/api/services/hosts.py:24` |
| `reconcile_scan_inventory()` / `reconcile_scan_host_inventory()` | Reconciles durable ports/findings. For the latest scan, current assessment copies type/profile/version; a newer legacy scan uses the old type fallback and clears the profile projection/version; older scans change neither. | `backend/src/api/services/inventory.py:20` |
| `DEFAULT_PAGE` / `DEFAULT_PER_PAGE` / `QUIET_AFTER_DAYS` | `1` / `20` / `7`. Quiet is last seen more than seven days ago. | `backend/src/api/services/read.py:49` |
| `_HOST_SORT_COLUMNS` | Sortable host columns: `last_seen_at`, `hostname`, `vendor`, `ip` (`cast` to `INET`), `vulnerability_count`. **Not** `machine_type`. Always with a `HostRecord.id` tie-breaker. | `backend/src/api/services/read.py` |
| `list_hosts()` | Paginated `HostRecord` list → `HostListResponse`. Keyword-only `org_id`; `group` `active` (default) or `quiet` filters in SQL; `total` is the requested group; `quiet_total` is the whole-inventory quiet count. | `backend/src/api/services/read.py:67` |
| `get_host_detail()` | Returns the durable profile projection and latest scan's assessment status/version/exposures; a legacy latest scan reports unavailable rather than reconstructed assessment. | `backend/src/api/services/read.py:131` |
| `get_scan_detail()` | Returns stored per-scan profiles and exposures when the policy version exists, otherwise an explicit unavailable assessment with empty exposures. | `backend/src/api/services/read.py:230` |
| `list_scans()` | Paginated `ScanRecord` list with per-scan `host_count`/`finding_count`/`highest_severity` aggregates (four-query strategy, no N+1) → `ScanListResponse`. Optional `status` filter; `sort_by`/`sort_order` with `scan_id` tie-breaker. Requires keyword-only `org_id`. | `backend/src/api/services/read.py:194` |
| `list_findings()` | Paginated findings via `finding_read_query()`, optionally filtered by `host_id`, `severity`, `scan_id`. Ordered by `FindingRecord.id`. Requires `org_id`. | `backend/src/api/services/read.py:299` |
| `finding_read_query()` / `to_finding_reads()` | The one finding read: a select of `FindingRecord`, `ScanHostRecord.host_id`, `HostRecord.hostname`, `HostFindingRecord`, `ModbusUnitRecord` and `IndustrialServiceRecord` with those outer-joined; the mapper reads rows by name into `FindingRead`. Callers add filters, sort and paging only. | `backend/src/api/services/read.py:529` |
| `run_worker_loop()` | Reads poll interval + batch size from `Settings` and runs `run_worker_once()` through `_poll_forever`, which sleeps when idle or after a logged exception. | `backend/src/api/services/worker.py:29` |
| `run_worker_once()` | Opens a session via `get_session()`, sweeps stale commands, then `process_pending_enrichment_jobs`. Returns the enrichment count only. No AI provider. | `backend/src/api/services/worker.py:72` |
| `run_ai_worker_loop()` / `run_ai_worker_once()` | AI tick on its own thread and session, also through `_poll_forever`. Documented in [ai](/backend/ai.md). Enrichment `run_worker_once` does not call them. | `backend/src/api/services/worker.py:46`, `:57` |
| `claim_jobs()` / `retry_or_fail()` | Shared job runtime for `enrichment_jobs` and `ai_scan_analyses`. `claim_jobs` fails stale jobs out of attempts, then selects `pending` (due `next_attempt_at`) or stale running jobs by `created_at,id` with `FOR UPDATE SKIP LOCKED` on Postgres, and bumps `attempts`. `retry_or_fail` sets `pending` + `next_attempt_at`, or `failed` + `completed_at`. | `backend/src/api/services/jobs.py:10`, `:72` |
| `claim_pending_enrichment_jobs()` | `claim_jobs` with running status `running` and exhausted error `enrichment_attempts_exhausted`. | `backend/src/api/services/enrichment.py:25` |
| `process_claimed_enrichment_job()` | Dispatches by `job_type` to `_process_cpe/cve/kev/epss_job`; success → `completed`; exception → rollback + `failed` with `last_error`. After each terminal path commits, calls `_enqueue_auto_analysis_safely` for that scan. | `backend/src/api/services/enrichment.py:44` |
| `_enqueue_auto_analysis_safely()` | Best-effort `enqueue_auto_scan_analysis` when `AI_AUTO_ANALYSIS` is on; logs failures, never fails enrichment. | `backend/src/api/services/enrichment.py:115` |
| `_process_cpe_job()` | NVD-by-CPE → one new finding per match (source `nvd_enrichment`, confidence `probable`) via `upsert_finding`, then `reconcile_scan_host_inventory` before commit so enrichment-created findings land in `host_findings`. | `backend/src/api/services/enrichment.py:116` |
| `_process_cve_job()` | NVD-by-CVE → **upgrades** the existing finding to `confirmed`, refreshes cvss/severity/references, adds the `nvd` label + evidence, re-runs risk. | `backend/src/api/services/enrichment.py:167` |
| `_process_kev_job()` / `_process_epss_job()` | Fetch + `upsert_kev_record`/`upsert_epss_record`, tag the finding with the `kev`/`epss` label + evidence, re-run risk. | `backend/src/api/services/enrichment.py:199` |
| `NvdClient` + `parse_nvd_matches()` | `query_by_cpe`/`query_by_cve` with a `NvdCacheRecord` DB cache (12h TTL), sends the `apiKey` header when set; parser prefers CVSS V31→V30→V2, `_severity_from_cvss` (≥9 critical, ≥7 high, ≥4 medium, else low). | `backend/src/api/services/nvd.py:13` |
| `KevClient` + `parse_kev_record()` + `upsert_kev_record()` | Fetches the full CISA KEV JSON feed, scans `vulnerabilities[]` for the CVE (`date_added`, `known_ransomware` from `knownRansomwareCampaignUse`, `required_action`); per-CVE `KevCacheRecord` (24h TTL). | `backend/src/api/services/kev.py:13` |
| `EpssClient` + `parse_epss_record()` + `upsert_epss_record()` | FIRST EPSS query by CVE (`?cve=`), `epss_score` (0–1) + `percentile`; per-CVE `EpssCacheRecord` (24h TTL). | `backend/src/api/services/epss.py:13` |
| `refresh_risk_snapshot()` | Deterministic scorer (see below); upserts one `RiskSnapshotRecord` per finding. | `backend/src/api/services/risk.py:28` |
| `status_rank()` | The monotonic Pi-owned ladder `queued 0 → delivered 1 → running 2 → uploading 3 → done/failed/cancelled 4`. Replaced the old pairwise `_LEGAL_EDGES` map so a transition is order-independent and idempotent. | `backend/src/api/services/command_lifecycle.py` |
| `is_terminal()` | True for exactly `done`/`failed`/`cancelled`/`expired`. Shared by the busy check and the sweeper. | `backend/src/api/services/command_lifecycle.py` |
| `next_status()` | The transition guard for the **backend-owned** edges. Pi-owned targets go through the rank; `delivered`/`expired` keep explicit guards, because rank alone would permit `delivered → expired` and break the "expired means it never reached the Pi" invariant. Illegal edges raise `InvalidCommandTransition`. | `backend/src/api/services/command_lifecycle.py` |
| `scan_status_for()` | Pure projection of a command status → Scan status (`queued`/`delivered`→`pending`, `running`→`accepted`, `uploading`→`processing`, `done`→`completed`, `failed`/`expired`→`failed`, `cancelled`→`cancelled`). Kept separate from `next_status` so the read path can reuse it without a transition. | `backend/src/api/services/command_lifecycle.py` |
| `InvalidCommandTransition` | Custom domain exception (not `ValueError`); message names `current` and `target`. | `backend/src/api/services/command_lifecycle.py` |
| `enqueue()` | Inserts one `queued` `Command` (`org_id`/`agent_id`/`scan_mode`/`subnet`/`created_at`) and commits. Writes **no** `scan_id` — the stub scan is created in `_record_delivery`, not here. | `backend/src/api/services/commands.py` |
| `cancel_command()` | Admin cancel (DMI-145). Terminal → idempotent `200`. `uploading` → `CommandNotCancellableError`. Socket present → send `AgentCancelFrame`, return `202` (Pi confirms later). No socket → retire to `cancelled` + mirror scan/activity, return `200`. | `backend/src/api/services/commands.py:175` |
| `cancelled_command_ids_for_agent()` | Reconnect catch-up: command `cancelled`, scan still `cancelled` (no results), inside the mode's max duration. Fed to `agent_ws` after hello. | `backend/src/api/services/commands.py:94` |
| `CommandNotCancellableError` | Raised when cancel hits `uploading`; router maps to `409 command_not_cancellable`. | `backend/src/api/services/commands.py` |
| `_claim_agent()` | The enqueue path's sync DB phase: authorize the agent, sweep, busy-check, then — since DMI-78 — refuse a `subnet` the connected Pi is not reporting, before inserting the row. | `backend/src/api/services/commands.py` |
| `get_command_detail()` | Org-scoped `GET /commands/{id}` read. Wraps stored `error_code` in `normalise_error_code` before building `CommandDetail`, so an off-contract row returns `"unknown"` rather than a pydantic 500. | `backend/src/api/services/commands.py` |
| `active_command_for()` | The busy check: first `Command` for the agent in any of the four non-terminal statuses (`queued`/`delivered`/`running`/`uploading`), not just running/uploading — otherwise a stuck `queued` would let a second job onto the Pi. | `backend/src/api/services/commands.py` |
| `apply_status()` | One atomic conditional `UPDATE ... WHERE id AND agent_id AND rank(status) < rank(:next) AND scan_id IS NOT NULL RETURNING …`. On `cancelled`, mirrors scan status only when the scan is not already `completed` (keeps uploaded partials), and appends `scan_cancelled` activity (not `scan_failed`). | `backend/src/api/services/commands.py` |
| `sweep_stale_commands()` | Flips stale non-terminal commands in two `UPDATE`s in one transaction; `_retire_commands()` shares only the `UPDATE … RETURNING`. **Disconnect pass** (joins `Agent` for presence): `connected_at IS NULL AND last_seen_at < now - grace` — `queued → expired` with `error_code=device_offline` (never reached the Pi), otherwise `failed` with `error_code=agent_disconnected`. **Duration pass** (runs second, so a dead agent keeps `agent_disconnected`; command-row predicate only, no join): delivered rows (`scan_id IS NOT NULL`) whose `COALESCE(delivered_at, created_at)` is past the mode budget from `Settings.command_max_duration_by_mode()` (a SQL `CASE` on `scan_mode`) → `failed` with `error_code=scan_timeout`. Queue wait does not count, and a queued, undelivered command is never duration-swept. Failed rows also call `append_scan_activity`, fed by the same `RETURNING`. Optional `agent_id` narrows it to one agent. | `backend/src/api/services/commands.py:177` |
| `_record_delivery()` | Sync DB phase of durable delivery: flush a stub `ScanRecord` (`pending`), call `append_scan_activity` for `scan_started` (best-effort — see `activity.py`), then `UPDATE` the command from `queued` to `delivered` with `delivered_at` + `scan_id` and commit. A zero rowcount rolls back and raises `DeviceOfflineError`. Never call on the event loop. | `backend/src/api/services/commands.py:300` |
| `deliver()` | `async`. Reads revocation first — `await run_in_threadpool(agent_presence.agent_is_revoked, ...)`, hoisted **above** the `if` and evaluated before the `or` so short-circuiting cannot hide it, and offloaded because a sync read here would block the event loop and stall every live socket. No registered socket **or a revoked agent** → close the socket if one is registered (`close_revoked`, `4001`, its own flat `if` so the close reads as a revoked-socket action rather than a quirk of the `or`), expire the command (`_expire_queued_command`, which records `error_code=device_offline` — the same reason the sweep's `queued` branch writes, so a command expired at dispatch is not the one silent record) and raise `DeviceOfflineError` immediately (retrying a dict lookup is a no-op). The revocation branch reuses that offline outcome verbatim: no new error code, no new terminal status, no stub scan. It is the gate for an **idle** revoked agent, which holds a registered socket and sends no frame, so the per-frame check never fires for it. The extra `SELECT` is deliberate — `enqueue()` commits and `expire_on_commit` defaults to `True`, so `_claim_agent`'s load is expired; reading earlier would be a time-of-check/time-of-use gap. When a socket exists, **`_record_delivery` runs first** (stub scan + `delivered` commit), then the `AgentCommandFrame` is sent **once**. **Any** send exception is caught after durable delivery and logged (`logger.exception("Failed to send command %s", …)`) — there is no transport-vs-bug split, because the commit point already happened. `_fail_unsent_command` then sets the command `failed` / `agent_disconnected` at once (via `_retire_commands` + `_mirror_retired_commands`, so the stub scan and `scan_failed` activity match the sweep), `deliver` returns that `failed` command and the router answers `201` (ADR-011 amendment 2026-09-15, DMI-171). ADR-011 amendments 2026-08-13 and 2026-09-14: one attempt; the operator clicking again is the retry. | `backend/src/api/services/commands.py:344` |
| `DeviceOfflineError` | Raised by `deliver` only **before** durable delivery: no registered socket, a revoked agent, or a zero-rowcount race in `_record_delivery` (`queued` → `expired`, no stub scan). The router maps it to `503 device_offline`. Post-durable send failures do **not** raise this — they return the committed command. | `backend/src/api/services/commands.py:32` |
| `mark_connected()` / `mark_disconnected()` / `reconcile_all()` | The durable presence projection: set `agents.connected_at` + touch `last_seen_at` on connect, clear it on disconnect, and `UPDATE agents SET connected_at = NULL` at API startup to recover from a hard crash where the `finally` never ran. Each has an `async_*` wrapper that runs the sync body in a threadpool. | `backend/src/api/services/agent_presence.py:40` |
| `agent_is_revoked()` / `touch_unless_revoked()` / `async_agent_is_revoked()` / `async_touch_unless_revoked()` | The revocation reads behind both DMI-97 gates. `agent_is_revoked` is the plain predicate used by the delivery gate and by the dispatcher's reject arm. `touch_unless_revoked` returns `"revoked"` for a revoked agent **without writing** and `"ok"` after bumping `last_seen_at` — a `Literal`, not a bool, so a write-named helper never reports its exception case as a bare `True` — **one `session.get(Agent, …)` serves both the check and the bump**, which is what keeps the per-frame cost at one `Agent` SELECT. Both **fail closed**: no `try/except`, so a failing lookup propagates rather than reading as "not revoked". An unknown `agent_id` reads as not-revoked (`False` / `"ok"`) — a missing row is a determinate answer, not a failed read — matching `mark_connected`/`mark_disconnected`'s silent-return precedent. Both `async_*` wrappers live here rather than at the call site: this module owns the session/threadpool lifecycle for presence, so `agent_ws` never opens a `Session` of its own. | `backend/src/api/services/agent_presence.py:22`, `:27`, `:62` |
| `register()` / `unregister()` / `set_hello()` / `touch()` / `is_online()` / `get_socket()` / `last_seen_at()` / `get_hello()` / `close_revoked()` | In-process WebSocket connection registry — one live socket per `agent_id`, identity-aware unregister/hello/touch (reconnect race fix), displaced sockets closed with `CLOSE_REPLACED`/`replaced`. The two close codes are now named constants, `CLOSE_REPLACED = 4000` and `CLOSE_REVOKED = 4001` (DMI-97), and both are published in the WS operation's close-code table in `contracts/openapi/openapi.yaml` — the Pi keys its reconnect behaviour on them, so they are contract values. `close_revoked()` is best-effort: it returns early unless the socket is `CONNECTED`, swallows a raising `close()`, and deliberately does **not** unregister or touch presence — the route's `finally` owns both, and duplicating would double-write `connected_at`. Otherwise still a pure in-memory registry with no I/O. | `backend/src/api/services/agent_connections.py:12`, `:48` |
| `run_agent_channel()` / `handle_agent_frame()` / `_parse_frame()` / `_apply_status_frame()` / `send_error()` | WS receive loop. Takes a session **factory**, not a session: each frame opens its own `Session` inside a `run_in_threadpool` call, so no DB session or pool slot is held across the long-lived socket. **Every inbound frame re-checks revocation (DMI-97)**. Dispatch is **parse-once** into `_Hello` / `_Status` / `_Reject`. After an accepted hello, `cancelled_command_ids_for_agent` drives catch-up `AgentCancelFrame`s for offline cancels still inside the mode budget (DMI-145). `status` frames go through `apply_status` (including `cancelled`). Malformed frames send `AgentErrorFrame` then check revocation; `unknown command_id` keeps plain `send_error`. | `backend/src/api/services/agent_ws.py` |

## The risk score

`refresh_risk_snapshot` (`backend/src/api/services/risk.py:28`) combines a severity weight
(low `.25` → critical `1.0`), a confidence weight (tentative `.5` → confirmed `1.0`), the EPSS
score, a KEV boost `+0.3`, a ransomware boost `+0.1`, and an exposed-service boost `+0.05`:

- `exploitability = min(1, epss*0.7 + kev_boost + ransomware_boost)`
- `risk_score = min(100, severity*45 + exploitability*35 + confidence*15 + exposed*100)`

with a human-readable `rationale` string. It is intentionally deterministic and explainable — any
ML/AI scoring is future work.

## How it connects

- `ingest_scan` is called by `ingest_scan_route` ([routers](/backend/routers.md)) with the
  `AgentIdentity` that `require_agent` resolved; it delegates the writing to `persist_scan`, which
  consumes a [`ScanIngestRequest`](/backend/schemas.md) and writes the
  [ORM models](/backend/models.md) as step 2 of the [overview data flow](/backend/overview.md),
  calling `upsert_hosts_for_scan` in the same transaction to resolve durable host identity.
- `ingest_scan` reads `commands.py`'s `command_for_scan` and `command_lifecycle.is_terminal` — the
  ingest gate reuses the command channel's own terminal-state definition rather than restating it.
- `read.py`'s functions back the [hosts/scans/findings routers](/backend/routers.md) directly — this
  is the one service group actually invoked over HTTP.
- The worker entry [`worker_main.py`](/backend/api.md) starts [AI](/backend/ai.md) in a daemon
  thread when configured, then `run_worker_loop`. Enrichment cadence comes from `Settings`.
- `commands.py` backs the command [routers](/backend/routers.md) (`POST /agents/{agent_id}/commands`,
  `GET /commands/{command_id}`, `POST /commands/{command_id}/cancel`), is called by `agent_ws.py` for
  inbound `status` frames and hello catch-up, and is swept by `worker.py`.
- `agent_presence.py` is written from `routers/agents.py` (connect / `finally`) and `main.py` (startup
  reconcile); it is read in SQL by `sweep_stale_commands`.
- Every enrichment path ends in `refresh_risk_snapshot`, so a finding always has a current risk row.
- Upstream cache tables (`nvd_cache`, `kev_cache`, `epss_cache`) and result tables
  (`kev_records`, `epss_records`, `risk_snapshots`) are defined in [models](/backend/models.md).

## Notes / gotchas

- **Removal is a hard delete and the database does the cascade.** `session.delete(user)` emits a
  single `DELETE FROM users WHERE id = ...`; there are no `Relationship()` declarations anywhere in
  `models/`, so SQLAlchemy neither pre-deletes nor nulls dependents — `refresh_tokens` and
  `password_reset_tokens` go through the FK's `ON DELETE CASCADE`
  ([migrations](/backend/migrations.md)). Nothing in `auth.py` is called; the cascade **is** the
  session teardown. Org data (scans, hosts, findings, agents) is the org's and is untouched, and the
  freed address can be invited again.
- **Role-change concurrency is serialized per org.** `change_member_role` takes the
  transaction-scoped advisory lock before reading the target or counting admins, so two mutual
  demotions cannot both pass. The namespace and org key are centralized in `org_lock.py` so later
  admin-reducing writes can adopt the same mechanism. The existing removal routes do not yet take
  this lock; ADR-017's broader DMI-105 removal hardening remains separate.
- **The read path is org-scoped in SQL, and `org_id` is required.** All four `read.py` entry points
  take a keyword-only `org_id: UUID` with no default, so a caller cannot silently omit it. Scoping is
  a plain `WHERE org_id = :org_id` — there is no `OR org_id IS NULL` and no fallback branch, which
  means a row with a `NULL org_id` (legacy pre-tenancy data) is visible to **nobody**. That is
  deliberate: no backfill and no `NOT NULL` tightening were done. Private helpers stay unscoped
  because they only ever receive already-scoped ids.
- **Presence and reported networks are never stored.** `online` and `available_subnets` have no
  column; `agents.target_subnet` (the human's *choice*) does. Both derived fields come from the
  in-process `agent_connections` registry through `_fields`/`_detail`, so a restart forgets them and
  a `last_seen_at` of `null` means exactly "never connected" — after a disconnect it falls back to
  the persisted row value rather than going null again.
- **The subnet check fails closed on exact string equality.** Both `_claim_agent` and
  `set_target_subnet` compare against `{entry.cidr for entry in reported}` verbatim; deliberately no
  `ipaddress.ip_network` parsing, which would accept equivalent spellings and add a failure mode
  inside the enqueue path.
- **Silence is not contradiction.** When `get_hello()` returns `None`, `_claim_agent` falls straight
  through to `enqueue` — it must **not** raise. Today's `503 device_offline` comes from `deliver()`
  *after* the row exists, which is what leaves the command `expired`; refusing earlier would answer
  503 with no row and break that lifecycle contract. The PATCH is the opposite case and does refuse,
  with a 409.
- **A stale choice is refused, never repaired.** If the Pi stops reporting the stored
  `target_subnet`, the scan is refused with a 422 and the `agents` row is left exactly as it is —
  nothing clears or corrects it behind the operator's back.
- **`SubnetNotReportedError` lives in `commands.py` for import direction.** `agents.py` imports
  `active_command_for` from `commands.py`; declaring the exception in `agents.py` and importing it
  back would be a cycle.
- **Confidence ladder.** `tentative` → `probable` (agent CVE or CPE match) → `confirmed` (NVD-by-CVE).
  `upsert_finding` only ever raises confidence via `_max_confidence`, never lowers it.
- **Idempotency moved up into `ingest_scan` (DMI-63).** `persist_scan` no longer short-circuits on an
  existing `scan_id`; `ingest_scan`'s Case B owns that, and it now checks **ownership first** — a
  foreign agent submitting a known `scan_id` gets a `ScanOwnershipError`, not a silent no-op. A
  repeated *owned* submission still writes nothing new.
- **Ingest is one transaction with one commit.** Every write inside `persist_scan` is `flush()`ed,
  never committed, until a single commit point: `session.commit()` for an unrequested scan, or
  `apply_status(...)` (which commits on success and rolls back on a zero-rowcount race) when filling
  a placeholder. Adding a `commit()` anywhere in that call tree breaks the all-or-nothing guarantee
  that `test_ingest_scan.py`'s two rollback tests exist to protect.
- **`nvd_cpe` dedup is per `(port, cpe)`, not per distinct CPE.** The key is
  `("nvd_cpe", port_record.id, cpe_record.cpe)`, so the same CPE on two different ports is two jobs.
  That is deliberate — `EnrichmentJobRecord.port_id` is load-bearing for `enrichment.py`'s per-port
  finding attachment. Spec prose that says "one job per distinct CPE" means *within a port*.
- **Host identity is scan-order-sensitive.** `upsert_hosts_for_scan` only overwrites the `HostRecord`
  snapshot (ip/mac/hostname/vendor/open_ports_count/highest_severity) when the incoming scan's
  `timestamp` is `>=` the current `last_seen_at`; an out-of-order (backfilled) scan only extends
  `first_seen_at`.
- **`sort_by=ip` casts to `INET`, so host sorting is Postgres-only.** `HostRecord.ip` is a plain
  `str` column, and a text sort orders `192.168.0.1`, `.10`, `.2` — visibly wrong in a host
  inventory. `_HOST_SORT_COLUMNS["ip"]` therefore holds `cast(HostRecord.ip, INET)`
  (`sqlalchemy.dialects.postgresql`). SQLite cannot compile it (`UnsupportedCompilationError`), so
  that one path only works against the deployed DB; the other three sort columns are dialect-neutral.
- **`SKIP LOCKED` is Postgres-only.** On other dialects the claim query runs without row locking, so
  concurrent workers are only safe against Postgres (the deployed DB).
- **Findings are hosts' findings** — they reference `ScanHostRecord` (per-scan observation) rows via
  `scan_host_id`; the durable `HostRecord` is resolved separately. See [glossary](/glossary.md).
- **`command_lifecycle.py` stays pure.** No DB or model imports — it is the transition rulebook;
  `commands.py` is what executes it against the database. Since DMI-64 the WS `status` branch does call
  it, via `apply_status`.
- **Transitions are split by owner, because they race differently.** The Pi's `running`/`uploading`/
  `done`/`failed` arrive over a socket and can overtake each other, so they are guarded by the
  monotonic rank; `delivered`/`expired` are written only by the serialized enqueue path, so they keep
  explicit `WHERE status = 'queued'` guards; the sweeper's `failed` has its own staleness predicate.
- **Zero rowcount is a success, not an error.** A duplicate or late `status` frame updates no row and is
  silently ignored (ADR-011 §3 idempotency). Only then does the WS layer check whether the command
  exists *for this agent* — and answers `AgentErrorFrame("unknown command_id")` if not. Cross-agent ids
  read as unknown deliberately, so the frame cannot become an oracle for probing other orgs' ids.
- **Durable delivery commits before the frame send.** `_record_delivery` runs in a threadpool, then
  `deliver` awaits `send_text`. A failed send then sets `failed` / `agent_disconnected` on the
  command and its stub scan, and the router answers `201` with that command — HTTP and persistence
  agree. That differs from the
  pre-record path, which expires `queued` with no `scan_id` and answers `503`. ADR-011 (amendment
  2026-09-14) and the OpenAPI `DeviceOfflineError` description match this.
- **A send failure never waits for a sweep.** Before DMI-171 the command stayed `delivered`: a dead
  transport freed the agent only after the disconnect grace, and a non-transport exception (for
  example a bug raising `ValueError`) left the socket registered and the agent answering
  `409 device_busy` until it disconnected. `deliver` now fails the command in the same request,
  whatever the exception.
- **Activity append failure is logged, not gating.** `append_scan_activity` in `activity.py` wraps
  the insert in a savepoint; on `SQLAlchemyError` it logs `logger.exception("Failed to append scan
  activity")` and continues. The API process has no `logging.basicConfig` ([api](/backend/api.md)),
  so that record goes to stderr via Python's last-resort handler (Railway `api` service logs locally),
  not the worker's formatted stream.
- **Early `running` no longer races an undelivered row.** Because the stub commits before the frame
  goes out, a prompt `running` frame finds `scan_id IS NOT NULL` and can apply normally; the old
  post-send commit window that dropped those frames is gone.
- **No lifecycle state lives in process memory.** Three writers touch a command row — the HTTP enqueue
  path, the WS frame path and the sweeper — sharing no session and no transaction. The row is the only
  truth, which is what makes a Railway restart survivable on a single replica.
- **Staleness is written, not derived.** Deriving it at serialisation time would make
  `GET /commands/{id}` say `failed` while `GET /scans` still said `processing`. The sweeper has two
  callers: the worker (timeliness for every reader, ~5s) and enqueue (scoped to one agent, so a dead
  worker cannot permanently wedge "Scan now" behind the unique index).
- **Staleness has two independent reasons.** Disconnect stale (`connected_at IS NULL AND last_seen_at <
  now - grace`) fails in-flight scans with `agent_disconnected` and expires undelivered commands with
  `device_offline`. Duration stale (`scan_id IS NOT NULL` and `delivered_at` past the per-mode budget from
  `command_max_duration_by_mode()`) fails in-flight scans with the backend-owned `scan_timeout` even when
  the Pi is still connected — so a wedged `running` row cannot block the next enqueue. Queued commands with
  no `scan_id` are never duration-swept. The two reasons are separate `UPDATE`s; disconnect runs first, so
  when both apply `agent_disconnected` wins. Shipped duration defaults are
  quick 10800, standard 28800, extensive 57600, nspi 21600, max 93600 seconds (see [api](/backend/api.md)).
  `command_disconnect_grace_seconds` (default 900) is a deliberately generous placeholder until DMI-66 pins
  the Pi's reconnect backoff.
- **Revocation now has both push and pull enforcement.** DMI-155 writes `revoked_at` through the
  admin route and closes the current socket immediately. The DMI-97 inbound-frame and delivery
  checks remain the race-safe backstop. Restore only clears the row; the parked Pi reconnects on its
  next hourly attempt.
- **`agent_connections` is process-local; `agents.connected_at` is its durable shadow.** The registry
  lives in the API process, but the sweeper runs in the **worker** — a separate Railway service. So the
  API writes the projection and the worker reads it in SQL. `last_seen_at` alone could not substitute:
  a healthy Pi sends nothing between `running` and `uploading`, so long silence is normal — the
  `connected_at IS NULL` guard is what excludes it.
- **A `scans` row means durable delivery committed, not that the Pi read the frame.** The CHECK
  `(scan_id IS NOT NULL OR status IN ('queued', 'expired'))` still holds: only `queued` and
  `expired` may carry a null `scan_id`. `_record_delivery` can link a stub before `send_text`
  succeeds, so a command whose send failed still has a (now `failed`) scan row — the HTTP caller
  still gets `201`. Nothing infers failure from a null `scan_id` alone — `command.status`
  is the signal. (The check originally omitted `queued` and had to be widened; see `plan.md` D1.)

# Citations

[1] [docs/adr/ADR-003-backend-stack.md](../../../docs/adr/ADR-003-backend-stack.md)
[2] [docs/adr/ADR-005-security-model.md](../../../docs/adr/ADR-005-security-model.md)
[3] [specs/013-backend-app-shell-rebuild](../../../specs/013-backend-app-shell-rebuild/TRUTH.md)
[4] [docs/adr/ADR-011-pi-command-channel.md](../../../docs/adr/ADR-011-pi-command-channel.md)
[5] [specs/016-command-channel-data-model](../../../specs/016-command-channel-data-model/TRUTH.md)
[6] [specs/018-agent-ws-command-channel](../../../specs/018-agent-ws-command-channel/TRUTH.md)
[7] [specs/021-scan-list-and-finding-filters](../../../specs/021-scan-list-and-finding-filters/TRUTH.md)
[8] [specs/022-command-enqueue-delivery](../../../specs/022-command-enqueue-delivery/plan.md)
[9] [docs/research/ws-session-lifetime.md](../../../docs/research/ws-session-lifetime.md)
[10] [specs/029-account-removal-api](../../../specs/029-account-removal-api/TRUTH.md)
[11] [specs/030-users-invites-admin-api](../../../specs/030-users-invites-admin-api/TRUTH.md)
[12] [specs/031-agents-read-surface-target-subnet](../../../specs/031-agents-read-surface-target-subnet/TRUTH.md)
[13] [specs/048-parked-channel-recovery](../../../specs/048-parked-channel-recovery/TRUTH.md)
