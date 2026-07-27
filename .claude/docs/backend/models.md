---
type: Module
title: Backend ORM models
description: The SQLModel tables — scan persistence, host identity, enrichment/cache, risk snapshots, user identity, auth session tokens, and the command channel with its agent public keys and replay nonces.
resource: backend/src/api/models/persistence.py
tags: [backend, models, sqlmodel, orm, schema]
timestamp: 2026-07-27T00:00:00Z
---

# Backend ORM models

## Purpose

`models/` defines every persisted table as a `SQLModel` class (`table=True`). Four modules —
`persistence.py` (the scan/enrichment domain), `identity.py` (orgs/users/invites), `session.py`
(refresh/reset tokens), and `command.py` (the command channel: `agents`/`commands`) — register their
tables on one shared `SQLModel.metadata`, which is the object [Alembic](/backend/migrations.md)
targets. The models are the query mapping; they **do not** create tables (`create_all` is never
called). `models/__init__.py` imports all four modules so their tables are registered;
`identity.py`, `session.py`, and `command.py` import `utc_now` from `persistence.py`, so import
order is irrelevant.

## Key classes / functions — `persistence.py`

| Model → table | Notable columns / constraints | Ref |
|---------------|------------------------------|-----|
| `utc_now()` | Timezone-aware `default_factory` shared by every model. | `backend/src/api/models/persistence.py:12` |
| `ScanRecord` → `scans` | PK `scan_id` (UUID); nullable `org_id` FK → `orgs`; `subnet`, `scan_mode`, `status` (default `completed`), JSON `metadata_json`. | `backend/src/api/models/persistence.py:16` |
| `ArtifactRecord` → `artifacts` | `kind`, `path`, `stage`, optional `host_ip`; FK → `scans`. | `backend/src/api/models/persistence.py:29` |
| `ScanHostRecord` → `scan_hosts` | A **per-scan host observation**; unique `(scan_id, ip)`; `mac`, `hostname`, `vendor`; `host_id` FK → `hosts` (nullable until identity resolution runs). | `backend/src/api/models/persistence.py:40` |
| `HostRecord` → `hosts` | The **durable cross-scan host identity**; PK `id` (UUID); `org_id`, `identity_key` (unique with `org_id`, `NULLS NOT DISTINCT`); `ip`/`mac`/`hostname`/`vendor` snapshot from the latest scan; `open_ports_count`, `highest_severity`; `first_seen_at`/`last_seen_at`. | `backend/src/api/models/persistence.py:54` |
| `PortRecord` → `ports` | Unique `(scan_host_id, port, protocol)`; `state`. | `backend/src/api/models/persistence.py:77` |
| `ServiceRecord` → `services` | Unique `port_id` (one service per port); `name`, `version`. | `backend/src/api/models/persistence.py:89` |
| `CPERecord` → `cpes` | Unique `(port_id, cpe)`. | `backend/src/api/models/persistence.py:99` |
| `FindingRecord` → `findings` | Unique `(scan_id, dedupe_key)`; `finding_id` (UUID, `default_factory=uuid4`, unique+indexed — a stable public identifier separate from the integer PK); `cve_id`, `cvss_score`, `severity`, `confidence` (default `tentative`), title/description/recommendation/evidence, JSON `references_json` + `source_labels_json`, `dedupe_key`; FKs scan_host/port/scan. | `backend/src/api/models/persistence.py:108` |
| `EnrichmentJobRecord` → `enrichment_jobs` | `job_type` (`nvd_cpe`/`nvd_cve`/`kev_cve`/`epss_cve`), `target_value`, `status` (default `pending`), `attempts`, `last_error`; FKs scan/port/finding. | `backend/src/api/models/persistence.py:140` |
| `NvdCacheRecord` → `nvd_cache` | Unique `query_key`, `query_kind`/`query_value`, `response_json`, `expires_at`. | `backend/src/api/models/persistence.py:157` |
| `KevRecord` / `EpssRecord` | Normalized per-CVE results (PK `cve_id`): KEV `date_added`/`known_ransomware`/`required_action`; EPSS `epss_score`/`percentile`/`scored_at`. | `backend/src/api/models/persistence.py:169` |
| `KevCacheRecord` / `EpssCacheRecord` | Raw cached upstream payloads per CVE with `expires_at` TTL. | `backend/src/api/models/persistence.py:193` |
| `RiskSnapshotRecord` → `risk_snapshots` | Unique `finding_id`; `confidence`, `exploitability`, `risk_score`, `rationale`. | `backend/src/api/models/persistence.py:211` |

## Key classes / functions — `identity.py`

| Model → table | Notable columns / constraints | Ref |
|---------------|------------------------------|-----|
| `Org` → `orgs` | UUID PK, `name`. | `backend/src/api/models/identity.py:14` |
| `User` → `users` | Case-insensitive unique index `ix_users_email` on `lower(email)` — **global, not per-org**, since migration `20260724_10`; `role` check `admin`/`viewer`; `password_hash`, `password_changed_at`. | `backend/src/api/models/identity.py:22` |
| `Invite` → `invites` | Unique `token_hash`; `role` check; `expires_at`, `consumed_at`. | `backend/src/api/models/identity.py:38` |

## Key classes / functions — `session.py`

| Model → table | Notable columns / constraints | Ref |
|---------------|------------------------------|-----|
| `RefreshToken` → `refresh_tokens` | UUID PK; `user_id` FK → `users`; `family_id` (indexed); `token_hash` (unique+indexed); `family_expires_at`; nullable `rotated_at`/`revoked_at`; `created_at`. Backs the rotating refresh-token family — see [auth](/backend/auth.md). | `backend/src/api/models/session.py:11` |
| `PasswordResetToken` → `password_reset_tokens` | UUID PK; `user_id` FK → `users`; `token_hash` (unique+indexed); `expires_at`; nullable `consumed_at`; `created_at`. Single-use reset token. | `backend/src/api/models/session.py:24` |

## Key classes / functions — `command.py`

| Model → table | Notable columns / constraints | Ref |
|---------------|------------------------------|-----|
| `Agent` → `agents` | The Pi appliance; UUID PK (equals the Pi's `X-Device-Id`); `org_id` FK → `orgs` (indexed); `display_name`; `public_key` (`LargeBinary`) — the device's 32 raw Ed25519 public-key bytes, stored **in the clear**; soft-tombstone `revoked_at`; informational `last_seen_at`. No secret, hash, or `online` column: since DMI-61 the backend holds nothing that could impersonate a device. | `backend/src/api/models/command.py:12` |
| `AgentNonce` → `agent_nonces` | One row per accepted device request: `agent_id` FK → `agents`, `nonce`, `expires_at`. `UniqueConstraint("agent_id", "nonce")` **is** the replay detector; `expires_at` is indexed for pruning. No `agent_id`-only index. | `backend/src/api/models/command.py` |
| `Command` → `commands` | The audit record of one "Scan now"; UUID PK; `org_id` + `agent_id` FKs (indexed); `scan_id` FK → `scans` **NOT NULL + unique** (1:1 Command→Scan); `scan_mode`/`subnet` request-of-record; unconstrained `status` (guarded by [`command_lifecycle`](/backend/services.md), no ENUM/CHECK); nullable `error_code`; exactly four timestamps `created_at`/`delivered_at`/`started_at`/`completed_at` (no `uploading_at`). | `backend/src/api/models/command.py:26` |

## How it connects

- [`persist_scan` and the enrichment services](/backend/services.md) read and write these records;
  [`upsert_hosts_for_scan`](/backend/services.md) resolves each `ScanHostRecord` to a `HostRecord`.
- The wire-facing [schemas](/backend/schemas.md) are the input (`ScanResult`) and output
  (`Persisted*` / [`read.py`](/backend/schemas.md)) projections of these tables; they are separate
  Pydantic models, not the ORM rows.
- Every table here is created — with its RLS policies and grants — by
  [migrations](/backend/migrations.md).

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
- **Command channel is still schema-only (DMI-59).** `Agent`/`Command` land the tables and the
  lifecycle rulebook that later epic issues (WS endpoint DMI-62, ingest DMI-63, enqueue/delivery
  DMI-64) build on; no delivery logic runs yet. A `Command`'s `status` is the source of truth; the
  linked `Scan`'s status is a pure projection (see [`command_lifecycle`](/backend/services.md)).
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
