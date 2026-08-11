---
type: Module
title: Backend services — persistence, host identity, read, enrichment, risk
description: The backend business logic for ingest/persistence, member administration, account removal, org-scoped reads, enrichment/risk, and command lifecycle/delivery.
resource: backend/src/api/services/persistence.py
tags: [backend, services, persistence, ingest, read, enrichment, worker, risk, command-channel, presence, tenancy]
timestamp: 2026-08-11T00:00:00Z
---

# Backend services — persistence, host identity, read, enrichment, risk

## Purpose

`services/` is where the backend actually does its work. `persistence.py` writes an ingested
`ScanIngestRequest` into the [tables](/backend/models.md), resolves host identity, and enqueues
enrichment jobs; since DMI-63 it also owns the **authorisation and lifecycle rules** for ingest via
`ingest_scan`. `hosts.py` resolves each scan's `ScanHostRecord`s to durable `HostRecord`s. `read.py` answers
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
`users.py` owns account removal plus member listing and role changes. `org_lock.py` supplies the
transaction-scoped per-org advisory lock that serializes admin-reducing role changes.
The auth services (`auth.py`, `tokens.py`, `passwords.py`, `mailer.py`) are documented in
[auth](/backend/auth.md).

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `ScanOwnershipError` / `ScanClosedError` | The two ingest refusals, mapped by the router to `403` / `400`. | `backend/src/api/services/persistence.py:27`, `:31` |
| `ingest_scan()` | The ingest gate. Three cases on `session.get(ScanRecord, scan_id)`: **A** unknown id → `persist_scan(command=None)`, creating an unrequested scan complete; **B** already `completed` → verify `agent_id`/`org_id` match (else `ScanOwnershipError`) and return it untouched, so a late progress report is a no-op; **C** placeholder → `command_for_scan`, reject a missing/foreign command with `ScanOwnershipError` and a terminal one with `ScanClosedError`, else fill it. | `backend/src/api/services/persistence.py:35` |
| `persist_scan()` | Keyword signature `(session, scan, *, org_id, agent_id, command, now)`. Fills the requested placeholder or inserts an unrequested scan (`scan_mode`, `status`), persists each host→port (writing `ServiceRecord` + `CPERecord`s) building `scan_host_index`/`port_index`, upserts each agent finding, calls `upsert_hosts_for_scan`, then enqueues enrichment jobs — all in **one transaction with a single commit point**. | `backend/src/api/services/persistence.py:78` |
| `upsert_finding()` | Dedups on `finding_dedupe_key`. New → insert (initial confidence `probable` if `cve_id` else `tentative`) + `refresh_risk_snapshot`. Existing → merge references/source-labels, take `_max_severity`/`_max_confidence`, prefer the higher cvss, re-run risk. | `backend/src/api/services/persistence.py:161` |
| `finding_dedupe_key()` | `ip|protocol|port|(cve_id or lowercased title)`. | `backend/src/api/services/persistence.py:244` |
| `_persist_scan_host()` | Inserts one `ScanHostRecord` (`ip`/`mac`/`hostname`/`vendor`) for the scan. | `backend/src/api/services/persistence.py:262` |
| `_enqueue_enrichment_jobs()` | One `nvd_cpe` job per `(port, CPE)`; per finding with a `cve_id` → `nvd_cve` + `kev_cve` + `epss_cve`, dedup via a `seen` set. | `backend/src/api/services/persistence.py:302` |
| `command_for_scan()` | Looks up the `Command` a `scan_id` belongs to, or `None`. Used by `ingest_scan` for the Case C ownership check. | `backend/src/api/services/commands.py:99` |
| `LastAdminError` | Refuses a self-delete or role change that would leave the org without an admin; routers map it to `409 last_admin`. | `backend/src/api/services/users.py:12` |
| `count_org_admins()` | Counts admin rows in one org. Role change calls it only after taking the org advisory lock. | `backend/src/api/services/users.py:16` |
| `list_org_members()` | Returns one org's users ordered by `last_seen_at DESC NULLS LAST`, then `id` for deterministic ties. | `backend/src/api/services/users.py:24` |
| `change_member_role()` | Takes the org-admin advisory lock, performs an org-scoped lookup, protects the final admin, writes the role, and commits. Unknown/foreign target returns `None`. | `backend/src/api/services/users.py:32` |
| `delete_self()` | Hard-deletes the caller unless they are their org's only admin. | `backend/src/api/services/users.py:53` |
| `delete_member()` | Org-scoped hard delete; unknown and foreign identifiers both return `False`. | `backend/src/api/services/users.py:60` |
| `ORG_ADMIN_LOCK_NAMESPACE` / `lock_org_admins()` | Namespace `8818`; executes two-key `pg_advisory_xact_lock(namespace, hashtext(org_id))`, released automatically on commit or rollback. | `backend/src/api/services/org_lock.py:8` |
| `identity_key()` | `mac:<MAC upper>` if a MAC is present, else `ip:<ip>` — the durable-identity key. | `backend/src/api/services/hosts.py:17` |
| `upsert_hosts_for_scan()` | For every `ScanHostRecord` in the scan: looks up a `HostRecord` by `(org_id, identity_key)`; creates one on first sight, else updates it **only if this scan is the newest seen so far** (extends `first_seen_at`, and on newest overwrites the ip/mac/hostname/vendor snapshot + `open_ports_count`/`highest_severity`); sets `scan_host.host_id`. | `backend/src/api/services/hosts.py:23` |
| `DEFAULT_PAGE` / `DEFAULT_PER_PAGE` | `1` / `20` — the paging defaults `list_hosts()` falls back to, imported by `read_hosts` so the route and the service cannot drift apart. `list_scans`/`list_findings` still inline theirs. | `backend/src/api/services/read.py:35` |
| `list_hosts()` | Paginated `HostRecord` list ordered by `last_seen_at desc` with a `HostRecord.id` tie-breaker for stable paging → `HostListResponse`. Requires keyword-only `org_id`; **both** the `count()` and the page query are scoped. | `backend/src/api/services/read.py:47` |
| `get_host_detail()` | One host's latest `ScanHostRecord` (for current ports) + full scan history (ordered by `ScanRecord.timestamp desc`) → `HostDetailResponse`. Requires `org_id`; the two inline `ScanRecord` queries are scoped too, so a foreign org's scan cannot surface through a host's detail. | `backend/src/api/services/read.py:73` |
| `get_scan_detail()` | One scan's hosts (as `ScanHostView`, `host_id` required) + findings (host_id resolved via outer join) → `ScanDetailResponse`. Requires `org_id`. | `backend/src/api/services/read.py:128` |
| `list_scans()` | Paginated `ScanRecord` list with per-scan `host_count`/`finding_count`/`highest_severity` aggregates (four-query strategy, no N+1) → `ScanListResponse`. Optional `status` filter; `sort_by`/`sort_order` with `scan_id` tie-breaker. Requires keyword-only `org_id`. | `backend/src/api/services/read.py:176` |
| `list_findings()` | Paginated `FindingRecord` list, optionally filtered by `host_id`, `severity`, `scan_id` → `FindingListResponse`. Ordered by `FindingRecord.id` for stable paging. Requires `org_id`; joins `ScanRecord` on `scan_id` **before** the `host_id` branch so the count and page queries share the org predicate. | `backend/src/api/services/read.py:245` |
| `run_worker_loop()` | Reads poll interval + batch size from `Settings`, loops forever calling `run_worker_once()`, sleeps `poll_interval` when idle or after a logged exception. | `backend/src/api/services/worker.py:13` |
| `run_worker_once()` | Opens a session via `get_session()`, calls `sweep_stale_commands` **globally** (every agent) before delegating to `process_pending_enrichment_jobs`, and returns the enrichment count so idle-sleep behaviour is unchanged. | `backend/src/api/services/worker.py:34` |
| `claim_pending_enrichment_jobs()` | Selects `pending` jobs by `created_at,id`; on Postgres uses `SELECT ... FOR UPDATE SKIP LOCKED`; flips them to `running`, bumps `attempts`, commits. | `backend/src/api/services/enrichment.py:22` |
| `process_claimed_enrichment_job()` | Dispatches by `job_type` to `_process_cpe/cve/kev/epss_job`; success → `completed`; exception → rollback + `failed` with `last_error`. | `backend/src/api/services/enrichment.py:52` |
| `_process_cpe_job()` | NVD-by-CPE → one new finding per match (source `nvd_enrichment`, confidence `probable`) via `upsert_finding`, resolving the `ScanHostRecord` (variable still named `device` locally) via `port_record.scan_host_id`. | `backend/src/api/services/enrichment.py:115` |
| `_process_cve_job()` | NVD-by-CVE → **upgrades** the existing finding to `confirmed`, refreshes cvss/severity/references, adds the `nvd` label + evidence, re-runs risk. | `backend/src/api/services/enrichment.py:167` |
| `_process_kev_job()` / `_process_epss_job()` | Fetch + `upsert_kev_record`/`upsert_epss_record`, tag the finding with the `kev`/`epss` label + evidence, re-run risk. | `backend/src/api/services/enrichment.py:199` |
| `NvdClient` + `parse_nvd_matches()` | `query_by_cpe`/`query_by_cve` with a `NvdCacheRecord` DB cache (12h TTL), sends the `apiKey` header when set; parser prefers CVSS V31→V30→V2, `_severity_from_cvss` (≥9 critical, ≥7 high, ≥4 medium, else low). | `backend/src/api/services/nvd.py:13` |
| `KevClient` + `parse_kev_record()` + `upsert_kev_record()` | Fetches the full CISA KEV JSON feed, scans `vulnerabilities[]` for the CVE (`date_added`, `known_ransomware` from `knownRansomwareCampaignUse`, `required_action`); per-CVE `KevCacheRecord` (24h TTL). | `backend/src/api/services/kev.py:13` |
| `EpssClient` + `parse_epss_record()` + `upsert_epss_record()` | FIRST EPSS query by CVE (`?cve=`), `epss_score` (0–1) + `percentile`; per-CVE `EpssCacheRecord` (24h TTL). | `backend/src/api/services/epss.py:13` |
| `refresh_risk_snapshot()` | Deterministic scorer (see below); upserts one `RiskSnapshotRecord` per finding. | `backend/src/api/services/risk.py:28` |
| `status_rank()` | The monotonic Pi-owned ladder `queued 0 → delivered 1 → running 2 → uploading 3 → done/failed 4`. Replaced the old pairwise `_LEGAL_EDGES` map so a transition is order-independent and idempotent. | `backend/src/api/services/command_lifecycle.py:45` |
| `is_terminal()` | True for exactly `done`/`failed`/`expired`. Shared by the busy check and the sweeper. | `backend/src/api/services/command_lifecycle.py:41` |
| `next_status()` | The transition guard for the **backend-owned** edges. Pi-owned targets go through the rank; `delivered`/`expired` keep explicit guards, because rank alone would permit `delivered → expired` and break the "expired means it never reached the Pi" invariant. Illegal edges raise `InvalidCommandTransition`. | `backend/src/api/services/command_lifecycle.py:49` |
| `scan_status_for()` | Pure projection of a command status → Scan status (`queued`/`delivered`→`pending`, `running`→`accepted`, `uploading`→`processing`, `done`→`completed`, `failed`/`expired`→`failed`). Kept separate from `next_status` so the read path can reuse it without a transition. | `backend/src/api/services/command_lifecycle.py:63` |
| `InvalidCommandTransition` | Custom domain exception (not `ValueError`); message names `current` and `target`. | `backend/src/api/services/command_lifecycle.py:34` |
| `enqueue()` | Inserts one `queued` `Command` (`org_id`/`agent_id`/`scan_mode`/`subnet`/`created_at`) and commits. Writes **no** `scan_id` — the stub scan is created only once delivery succeeds. | `backend/src/api/services/commands.py:35` |
| `active_command_for()` | The busy check: first `Command` for the agent in any of the four non-terminal statuses (`queued`/`delivered`/`running`/`uploading`), not just running/uploading — otherwise a stuck `queued` would let a second job onto the Pi. | `backend/src/api/services/commands.py:81` |
| `apply_status()` | One atomic conditional `UPDATE ... WHERE id AND agent_id AND rank(status) < rank(:next) AND scan_id IS NOT NULL RETURNING scan_id` — never read-validate-write. The `scan_id` predicate keeps a Pi frame that overtakes delivery from advancing an undelivered command (which the CHECK would reject outright). Backfills `started_at`/`delivered_at`/`completed_at` via `COALESCE`, persists `error_code` on `failed`, then mirrors `scan_status_for(status)` onto the linked scan. Returns `False` on zero rowcount (duplicate, late, or lost-race frame). | `backend/src/api/services/commands.py:89` |
| `sweep_stale_commands()` | Flips stale non-terminal commands: `queued → expired` (never reached the Pi), everything else → `failed`, mirroring each linked scan. Pure-SQL predicate over the presence projection — `connected_at IS NULL AND last_seen_at < now - grace` — so a **connected** Pi is never failed however long its scan runs. Optional `agent_id` narrows it to one agent. | `backend/src/api/services/commands.py:137` |
| `deliver()` | `async`. No registered socket → expire the command and raise `DeviceOfflineError` immediately (retrying a dict lookup is a no-op). Otherwise send the `AgentCommandFrame`, retrying `_DELIVERY_RETRIES` times on a throwing `send_text`; on success insert **and flush** the stub `ScanRecord` first, then `UPDATE` the command to `delivered` with `delivered_at` + `scan_id`. A zero rowcount on that `UPDATE` means the row left `queued` during the `await`, so it rolls back (discarding the flushed scan) and raises offline. | `backend/src/api/services/commands.py:201` |
| `DeviceOfflineError` | Raised by `deliver` on both offline paths; the router maps it to `503 device_offline`. | `backend/src/api/services/commands.py:20` |
| `mark_connected()` / `mark_disconnected()` / `reconcile_all()` | The durable presence projection: set `agents.connected_at` + touch `last_seen_at` on connect, clear it on disconnect, and `UPDATE agents SET connected_at = NULL` at API startup to recover from a hard crash where the `finally` never ran. Each has an `async_*` wrapper that runs the sync body in a threadpool. | `backend/src/api/services/agent_presence.py:29` |
| `touch_agent_last_seen()` | Bumps `agents.last_seen_at`. Moved here from `agent_ws.py` — same concern as the rest of presence. | `backend/src/api/services/agent_presence.py:21` |
| `register()` / `unregister()` / `set_hello()` / `touch()` / `is_online()` / `get_socket()` / `last_seen_at()` / `get_hello()` | In-process WebSocket connection registry — one live socket per `agent_id`, identity-aware unregister/hello/touch (reconnect race fix), displaced sockets closed with `4000`/`replaced`. Deliberately unchanged by DMI-64: it stays a pure in-memory registry with no I/O. | `backend/src/api/services/agent_connections.py` |
| `run_agent_channel()` / `handle_agent_frame()` / `_apply_status_frame()` / `send_error()` | WS receive loop (`iter_text()`). Takes a session **factory**, not a session: each frame opens its own `Session` inside a `run_in_threadpool` call, so no DB session or pool slot is held across the long-lived socket. `hello` touches presence; `status` now calls `apply_status`. Malformed frames get an `AgentErrorFrame` reply without closing the socket. | `backend/src/api/services/agent_ws.py:127` |

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
- The worker entry [`worker_main.py`](/backend/api.md) calls `run_worker_loop`; the loop's cadence
  and batch size come from `Settings` in [config](/backend/api.md), as does
  `command_disconnect_grace_seconds` for the sweep.
- `commands.py` backs the two command [routers](/backend/routers.md) (`POST /agents/{agent_id}/commands`,
  `GET /commands/{command_id}`), is called by `agent_ws.py` for inbound `status` frames, and is swept by
  `worker.py` — three entry points, one module.
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
- **The `await` in `deliver` is the one window where another writer can move the row.** Two things can
  happen in it, and both resolve to the same silent-loser rule. A Pi frame can overtake the
  `delivered` commit — it finds `scan_id` still null and is dropped, because advancing an undelivered
  command would violate the CHECK; the Pi's later `uploading`/`done` frames apply normally. Or the
  sweeper can expire the command after the socket dropped — the post-send `UPDATE` then matches
  nothing, so `deliver` rolls back and raises offline rather than committing a stub scan against an
  `expired` command. Note this makes D9's claim that the rank alone resolves the early-`running` race
  inaccurate: the rank permits it, the CHECK forbids it, and the guard is what reconciles them.
- **No lifecycle state lives in process memory.** Three writers touch a command row — the HTTP enqueue
  path, the WS frame path and the sweeper — sharing no session and no transaction. The row is the only
  truth, which is what makes a Railway restart survivable on a single replica.
- **Staleness is written, not derived.** Deriving it at serialisation time would make
  `GET /commands/{id}` say `failed` while `GET /scans` still said `processing`. The sweeper has two
  callers: the worker (timeliness for every reader, ~5s) and enqueue (scoped to one agent, so a dead
  worker cannot permanently wedge "Scan now" behind the unique index).
- **Staleness keys on connection loss, not elapsed time.** A Pi's own worst-case runtime is 35–130 min
  depending on scan mode; a single duration timeout would have to be sized for `max` and would wedge an
  agent for hours after a dead `quick` scan. `command_disconnect_grace_seconds` (default 900) is a
  deliberately generous placeholder until DMI-66 pins the Pi's reconnect backoff.
- **`agent_connections` is process-local; `agents.connected_at` is its durable shadow.** The registry
  lives in the API process, but the sweeper runs in the **worker** — a separate Railway service. So the
  API writes the projection and the worker reads it in SQL. `last_seen_at` alone could not substitute:
  a healthy Pi sends nothing between `running` and `uploading`, so long silence is normal — the
  `connected_at IS NULL` guard is what excludes it.
- **A `scans` row means a Pi accepted work.** `CHECK (scan_id IS NOT NULL OR status IN ('queued',
  'expired'))` makes that provable rather than conventional: the two pre-delivery statuses may carry a
  null `scan_id`, nothing else may. Nothing infers failure from the null — `command.status` is the
  signal. (The check originally omitted `queued` and had to be widened; see `plan.md` D1.)

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
