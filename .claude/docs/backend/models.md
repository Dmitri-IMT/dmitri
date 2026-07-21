---
type: Module
title: Backend ORM models
description: The SQLModel tables — scan persistence, enrichment/cache, risk snapshots, and dormant identity.
resource: backend/src/api/models/persistence.py
tags: [backend, models, sqlmodel, orm, schema]
timestamp: 2026-07-21T00:00:00Z
---

# Backend ORM models

## Purpose

`models/` defines every persisted table as a `SQLModel` class (`table=True`). Two modules —
`persistence.py` (the scan/enrichment domain) and `identity.py` (orgs/users/invites) — register
their tables on one shared `SQLModel.metadata`, which is the object [Alembic](/backend/migrations.md)
targets. The models are the query mapping; they **do not** create tables (`create_all` is never
called). `models/__init__.py` imports both modules so their tables are registered; `identity.py`
imports `utc_now` from `persistence.py`, so import order is irrelevant.

## Key classes / functions — `persistence.py`

| Model → table | Notable columns / constraints | Ref |
|---------------|------------------------------|-----|
| `utc_now()` | Timezone-aware `default_factory` shared by every model. | `backend/src/api/models/persistence.py:12` |
| `ScanRecord` → `scans` | PK `scan_id` (UUID); nullable `org_id` FK → `orgs`; `subnet`, `target_mode`, `scan_profile`, JSON `metadata_json`. | `backend/src/api/models/persistence.py:16` |
| `ArtifactRecord` → `artifacts` | `kind`, `path`, `stage`, optional `host_ip`; FK → `scans`. | `backend/src/api/models/persistence.py:29` |
| `DeviceRecord` → `devices` | A persisted **host**; unique `(scan_id, ip)`; `mac`, `hostname`, `vendor`. | `backend/src/api/models/persistence.py:40` |
| `PortRecord` → `ports` | Unique `(device_id, port, protocol)`; `state`. | `backend/src/api/models/persistence.py:53` |
| `ServiceRecord` → `services` | Unique `port_id` (one service per port); `name`, `version`. | `backend/src/api/models/persistence.py:65` |
| `CPERecord` → `cpes` | Unique `(port_id, cpe)`. | `backend/src/api/models/persistence.py:75` |
| `FindingRecord` → `findings` | Unique `(scan_id, dedupe_key)`; `cve_id`, `cvss_score`, `severity`, `confidence` (default `tentative`), title/description/recommendation/evidence, JSON `references_json` + `source_labels_json`, `dedupe_key`; FKs device/port/scan. | `backend/src/api/models/persistence.py:84` |
| `EnrichmentJobRecord` → `enrichment_jobs` | `job_type` (`nvd_cpe`/`nvd_cve`/`kev_cve`/`epss_cve`), `target_value`, `status` (default `pending`), `attempts`, `last_error`; FKs scan/port/finding. | `backend/src/api/models/persistence.py:113` |
| `NvdCacheRecord` → `nvd_cache` | Unique `query_key`, `query_kind`/`query_value`, `response_json`, `expires_at`. | `backend/src/api/models/persistence.py:130` |
| `KevRecord` / `EpssRecord` | Normalized per-CVE results (PK `cve_id`): KEV `date_added`/`known_ransomware`/`required_action`; EPSS `epss_score`/`percentile`/`scored_at`. | `backend/src/api/models/persistence.py:142` |
| `KevCacheRecord` / `EpssCacheRecord` | Raw cached upstream payloads per CVE with `expires_at` TTL. | `backend/src/api/models/persistence.py:166` |
| `RiskSnapshotRecord` → `risk_snapshots` | Unique `finding_id`; `confidence`, `exploitability`, `risk_score`, `rationale`. | `backend/src/api/models/persistence.py:184` |

## Key classes / functions — `identity.py`

| Model → table | Notable columns / constraints | Ref |
|---------------|------------------------------|-----|
| `Org` → `orgs` | UUID PK, `name`. | `backend/src/api/models/identity.py:14` |
| `User` → `users` | Case-insensitive unique index `(org_id, lower(email))`; `role` check `admin`/`viewer`; `password_hash`, `password_changed_at`. | `backend/src/api/models/identity.py:22` |
| `Invite` → `invites` | Unique `token_hash`; `role` check; `expires_at`, `consumed_at`. | `backend/src/api/models/identity.py:38` |

## How it connects

- [`persist_scan` and the enrichment services](/backend/services.md) read and write these records.
- The wire-facing [schemas](/backend/schemas.md) are the input (`ScanResult`) and output
  (`Persisted*`) projections of these tables; they are separate Pydantic models, not the ORM rows.
- Every table here is created — with its RLS policies and grants — by
  [migrations](/backend/migrations.md).

## Notes / gotchas

- **`DeviceRecord` is a host.** The class/table keep the frozen ingest word `device`; the domain term
  is *host* (see [glossary](/glossary.md)).
- **Identity is dormant.** `Org`/`User`/`Invite` back the OpenAPI auth/invite endpoints but nothing in
  the running app (`api/main.py`) uses them yet.
- JSON columns (`metadata_json`, `references_json`, `source_labels_json`, cache `*_json`, `raw_json`)
  use SQLAlchemy `JSON` via explicit `sa_column`.

# Citations

[1] [docs/adr/ADR-009-database-stack.md](../../../docs/adr/ADR-009-database-stack.md)
[2] [docs/adr/ADR-003-backend-stack.md](../../../docs/adr/ADR-003-backend-stack.md)
