---
type: Module
title: Backend ORM models
description: The SQLModel tables for scan persistence, host identity, enrichment/risk, user identity and activity, auth sessions, and the command channel.
resource: backend/src/api/models/persistence.py
tags: [backend, models, sqlmodel, orm, schema]
timestamp: 2026-09-20T00:00:00Z
---

# Backend ORM models

## Purpose

`models/` defines every persisted table as a `SQLModel` class (`table=True`). Five modules —
`persistence.py` (the scan/enrichment domain), `identity.py` (orgs/users/invites), `session.py`
(refresh/reset tokens), `command.py` (the command channel: `agents`/`commands`), and `activity.py`
(the Home activity log) — register their
tables on one shared `SQLModel.metadata`, which is the object [Alembic](/backend/migrations.md)
targets. The models are the query mapping; they **do not** create tables (`create_all` is never
called). `models/__init__.py` imports all five modules so their tables are registered;
`identity.py`, `session.py`, and `command.py` import `utc_now` from `persistence.py`, so import
order is irrelevant.

## Key classes / functions — `persistence.py`

| Model → table | Notable columns / constraints | Ref |
|---------------|------------------------------|-----|
| `utc_now()` | Timezone-aware `default_factory` shared by every model. | `backend/src/api/models/persistence.py:18` |
| `ScanRecord` → `scans` | Per-scan header including nullable `assessment_policy_version`; null means the stored scan predates assessment. | `backend/src/api/models/persistence.py:38` |
| `ScanHostRecord` → `scan_hosts` | A **per-scan host observation**; unique `(scan_id, ip)`; original observations plus nullable assessment `machine_type` and `device_profile_json`; `host_id` resolves durable identity. | `backend/src/api/models/persistence.py:53` |
| `HostRecord` → `hosts` | Durable cross-scan identity. Its latest accepted profile projection is `machine_type`, nullable `device_profile_json`, and nullable `device_profile_policy_version`; older scans do not overwrite it. | `backend/src/api/models/persistence.py:77` |
| `PortRecord` → `ports` | Unique `(scan_host_id, port, protocol)`; `state`. Per-scan evidence — not the durable service list. | `backend/src/api/models/persistence.py:84` |
| `HostPortRecord` → `host_ports` | Durable open-port life on a machine: `host_id` FK, `port`/`protocol`/`service`, optional `version`, `first_seen_at`/`last_seen_at`; unique `(host_id, port, protocol)`. No `state`, no `closed_at`. | `backend/src/api/models/persistence.py:96` |
| `ServiceRecord` → `services` | Unique `port_id` (one service per port); `name`, `version`. | `backend/src/api/models/persistence.py:92` |
| `CPERecord` → `cpes` | Unique `(port_id, cpe)`. | `backend/src/api/models/persistence.py:102` |
| `ExposureRecord` → `exposures` | Immutable per-scan endpoint assessment linked to `scan`, `scan_host`, and the exact `port`; stores role, attention, confidence, reason, and bounded evidence JSON. Unique `(scan_id, scan_host_id, port_id)`. | `backend/src/api/models/persistence.py:156` |
| `IndustrialServiceRecord` → `industrial_services` | Unique `(scan_host_id, protocol, port)`; JSONB evidence; `write_requests_sent`. | `backend/src/api/models/persistence.py` |
| `ModbusUnitRecord` → `modbus_units` | Unique `(industrial_service_id, unit_id)`; JSONB identification, sources, address ranges (digest, no values). | `backend/src/api/models/persistence.py` |
| `FindingRecord` → `findings` | Unique `(scan_id, dedupe_key)`; nullable `modbus_unit_id` FK → `modbus_units`; check `ck_findings_severity` on `severity`, spelled from `SEVERITY_ORDER` in [`core/severity.py`](/backend/api.md) so the constraint and the domain cannot drift (`low`/`medium`/`high`/`critical`); `finding_id` (UUID, `default_factory=uuid4`, unique+indexed — a stable public identifier separate from the integer PK); `cve_id`, `cvss_score`, `severity`, `confidence` (default `tentative`), title/description/recommendation/evidence, JSON `references_json` + `source_labels_json`, `dedupe_key`; FKs scan_host/port/scan. | `backend/src/api/models/persistence.py:129` |
| `HostFindingRecord` → `host_findings` | Durable problem life: `host_id` FK, `dedupe_key`, `first_seen_at`/`last_seen_at`, nullable `fixed_at`; unique `(host_id, dedupe_key)`. Org is reached through `hosts`. | `backend/src/api/models/persistence.py:164` |
| `EnrichmentJobRecord` → `enrichment_jobs` | `job_type` (`nvd_cpe`/`nvd_cve`/`kev_cve`/`epss_cve`), `target_value`, `status` (default `pending`), `attempts`, `last_error`; FKs scan/port/finding. | `backend/src/api/models/persistence.py:176` |
| `NvdCacheRecord` → `nvd_cache` | Unique `query_key`, `query_kind`/`query_value`, `response_json`, `expires_at`. | `backend/src/api/models/persistence.py:163` |
| `KevRecord` / `EpssRecord` | Normalized per-CVE results (PK `cve_id`): KEV `date_added`/`known_ransomware`/`required_action`; EPSS `epss_score`/`percentile`/`scored_at`. | `backend/src/api/models/persistence.py:175`, `:187` |
| `KevCacheRecord` / `EpssCacheRecord` | Raw cached upstream payloads per CVE with `expires_at` TTL. | `backend/src/api/models/persistence.py:199`, `:208` |
| `RiskSnapshotRecord` → `risk_snapshots` | Unique `finding_id`; `confidence`, `exploitability`, `risk_score`, `rationale`. | `backend/src/api/models/persistence.py:217` |
| `AIScanAnalysisRecord` → `ai_scan_analyses` | `language` column (default `en`); unique `(scan_id, language)` as `uq_ai_scan_analyses_scan_language`; status check; completed requires `analysis_json`; coverage and writing-skill version columns. See [ai](/backend/ai.md). | `backend/src/api/models/persistence.py:360` |
| `AIUsageRecord` → `ai_usage` | Provider operation metadata (tokens, latency, status); no prompt/response text. | `backend/src/api/models/persistence.py:47` |
| `AIChatMessageRecord` → `ai_chat_messages` | Per-user Q&A; `scope_type` + `scope_id` thread key; capped in service layer. | `backend/src/api/models/persistence.py:404` |

`ArtifactRecord` → `artifacts` was **deleted in DMI-63** (migration `20260804_14` drops the table).
The agent never wrote artifacts, so the table was dead weight; the reverse migration recreates it.

## Key classes / functions — `identity.py`

| Model → table | Notable columns / constraints | Ref |
|---------------|------------------------------|-----|
| `Org` → `orgs` | UUID PK, `name`, nullable `ot_digest_key` (never on read APIs). | `backend/src/api/models/identity.py` |
| `User` → `users` | Global case-insensitive unique index `ix_users_email` on `lower(email)`; `role` check `admin`/`viewer`; password fields; nullable, unindexed `last_login_at` and `last_seen_at`; `created_at`. | `backend/src/api/models/identity.py:25` |
| `Invite` → `invites` | Unique `token_hash`; `role` check; `expires_at`, `consumed_at`. | `backend/src/api/models/identity.py:45` |

## Key classes / functions — `session.py`

| Model → table | Notable columns / constraints | Ref |
|---------------|------------------------------|-----|
| `RefreshToken` → `refresh_tokens` | UUID PK; `user_id` FK → `users` **`ON DELETE CASCADE`**; `family_id` (indexed); `token_hash` (unique+indexed); `family_expires_at`; nullable `rotated_at`/`revoked_at`; `created_at`. Backs the rotating refresh-token family — see [auth](/backend/auth.md). | `backend/src/api/models/session.py:11` |
| `PasswordResetToken` → `password_reset_tokens` | UUID PK; `user_id` FK → `users` **`ON DELETE CASCADE`**; `token_hash` (unique+indexed); `expires_at`; nullable `consumed_at`; `created_at`. Single-use reset token. | `backend/src/api/models/session.py:24` |

## Key classes / functions — `command.py`

| Model → table | Notable columns / constraints | Ref |
|---------------|------------------------------|-----|
| `Agent` → `agents` | The Pi appliance; UUID PK (equals the Pi's `X-Device-Id`); `org_id` FK → `orgs` (indexed); `display_name`; `public_key` (`LargeBinary`) — the device's 32 raw Ed25519 public-key bytes, stored **in the clear**; soft-tombstone `revoked_at`; informational `last_seen_at`; nullable `connected_at` — the durable projection of the in-memory socket registry, written by the API and read in SQL by the worker's sweeper; nullable, unindexed `target_subnet` (DMI-78) — the network an admin **chose** for this Pi, `null` until one is picked. No secret or hash column: since DMI-61 the backend holds nothing that could impersonate a device, and "online" is `connected_at IS NOT NULL` rather than a separate flag. | `backend/src/api/models/command.py:12` |
| `AgentNonce` → `agent_nonces` | One row per accepted device request: `agent_id` FK → `agents`, `nonce`, `expires_at`. `UniqueConstraint("agent_id", "nonce")` **is** the replay detector; `expires_at` is indexed for pruning. No `agent_id`-only index. | `backend/src/api/models/command.py` |
| `Command` → `commands` | The audit record of one "Scan now"; UUID PK; `org_id` + `agent_id` FKs (indexed); `scan_id` FK → `scans` **nullable + unique** (1:1 Command→Scan, written only once delivery succeeds) under `CHECK (scan_id IS NOT NULL OR status IN ('queued', 'expired'))`; `scan_mode`/`subnet` request-of-record; unconstrained `status` (guarded by [`command_lifecycle`](/backend/services.md), no ENUM/CHECK); nullable `error_code`; exactly four timestamps `created_at`/`delivered_at`/`started_at`/`completed_at` (no `uploading_at`). A partial unique index on `agent_id` over the four non-terminal statuses enforces one active command per Pi. | `backend/src/api/models/command.py:26` |

## Key classes / functions — `activity.py`

| Model → table | Notable columns / constraints | Ref |
|---------------|------------------------------|-----|
| `ActivityRecord` → `activity` | Int autoincrement PK (paging tiebreaker). `org_id` FK. `kind` CHECK of nine literals. `occurred_at` is the API clock. Nullable `actor_user_id` with **no FK** so rows survive user delete. JSONB `payload`. | `backend/src/api/models/activity.py:30` |

## How it connects

- [`ingest_scan`/`persist_scan` and the enrichment services](/backend/services.md) read and write
  these records; [`upsert_hosts_for_scan`](/backend/services.md) resolves each `ScanHostRecord` to a
  `HostRecord`; [`reconcile_scan_inventory`](/backend/services.md) then writes `host_ports` /
  `host_findings` / `machine_type` / `vulnerability_count`.
- The wire-facing [schemas](/backend/schemas.md) are the input (`ScanIngestRequest`) and output
  (`Persisted*` / [`read.py`](/backend/schemas.md)) projections of these tables; they are separate
  Pydantic models, not the ORM rows.
- `ScanRecord.agent_id` and `Command.agent_id` both point at `agents`, and `ingest_scan` compares
  them: a submission is accepted only when the signing device owns the scan's command.
- Every table here is created — with its RLS policies and grants — by
  [migrations](/backend/migrations.md).
- [`services/auth.py`](/backend/auth.md) stamps the two user activity columns, while
  [`services/users.py`](/backend/services.md) lists members and changes roles.

## Notes / gotchas

- **`scan_hosts` vs `hosts`.** `ScanHostRecord` (table `scan_hosts`, formerly `DeviceRecord`/`devices`)
  is a **per-scan observation** — one row per host seen in one scan, scoped by `(scan_id, ip)`.
  `HostRecord` (table `hosts`) is the **durable cross-scan identity** — one row per real machine,
  keyed by `identity_key` (MAC if present, else IP) and updated across scans via
  `upsert_hosts_for_scan`. See [ADR-014](../../../docs/adr/ADR-014-host-identity-resolution.md) and
  [glossary](/glossary.md).
- **Auth is now wired, and so are invites.** `User` + the `session.py` tokens back the live auth
  routes (spec 016, DMI-60); `Invite` is live too as of spec 017 / DMI-61 — see
  [auth](/backend/auth.md). `Org` is written by [`backend-bootstrap-org`](/backend/management.md),
  not by any route.
- **User emails are globally unique, not per-org.** Migration `20260724_10` replaced the
  `(org_id, lower(email))` index with `lower(email)` alone, so one address maps to at most one user
  across the whole system. This is why `create_invite` and `accept_invite` use *different* duplicate
  scopes — see the invites note in [auth](/backend/auth.md).
- **User activity is two nullable facts.** `last_login_at` means password login or invite
  acceptance; `last_seen_at` also advances on refresh. Neither column is indexed, and only
  `last_seen_at` is published on the member list.
- **The command channel and ingest are wired end to end.** A `Command`'s `status` is the source of
  truth; the linked `Scan` status is a projection, and every writer mirrors both in one transaction
  so `GET /commands/{id}` and `GET /scans` cannot disagree.
- **A null `scan_id` is a consequence, never a marker.** It means the command has not been delivered
  (`queued`) or never will be (`expired`) — the DB CHECK makes that equivalence provable. Do not infer
  failure from it; read `status`.
- **`agents` stores the chosen network, never the reported ones.** `target_subnet` is a human
  decision and persists; the Pi's `available_subnets` and its `online` state are read from the
  in-memory registry on every request and have no column — see
  [services](/backend/services.md). `connected_at` is the one connection-state column, and the
  sweeper depends on it.
- **`agents` no longer stores a device secret.** DMI-59's `secret_ciphertext`/`secret_nonce`/
  `secret_key_version` columns were dropped in `20260724_11` in favour of a plaintext `public_key`,
  per ADR-005 as amended — which is why ADR-015 (secret encryption at rest) was retired rather than
  implemented. See [device auth](/backend/device-auth.md).
- JSON columns (`metadata_json`, `references_json`, `source_labels_json`, cache `*_json`, `raw_json`)
  use SQLAlchemy `JSON` via explicit `sa_column`.

# Citations

[1] [docs/adr/ADR-009-database-stack.md](../../../docs/adr/ADR-009-database-stack.md)
[2] [docs/adr/ADR-003-backend-stack.md](../../../docs/adr/ADR-003-backend-stack.md)
[3] [docs/adr/ADR-014-host-identity-resolution.md](../../../docs/adr/ADR-014-host-identity-resolution.md)
[4] [specs/015-read-path](../../../specs/015-read-path/TRUTH.md)
[5] [docs/adr/ADR-011-pi-command-channel.md](../../../docs/adr/ADR-011-pi-command-channel.md)
[6] [docs/adr/ADR-015-agent-secret-storage-at-rest.md](../../../docs/adr/ADR-015-agent-secret-storage-at-rest.md)
[7] [specs/016-command-channel-data-model](../../../specs/016-command-channel-data-model/TRUTH.md)
