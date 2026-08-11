---
type: Package Overview
title: Backend — API + enrichment worker
description: The FastAPI backend — read, auth, user/invite administration, command-channel and ingest routes wired — plus the CVE-enrichment worker.
resource: backend/src/api
tags: [backend, fastapi, worker, persistence, enrichment, read, auth]
timestamp: 2026-08-11T00:00:00Z
---

# Backend — API + enrichment worker

> **Read path + auth + identity administration + command channel + ingest all wired.**
> `api/main.py` registers the org-scoped data reads, auth/session routes, member and pending-invite
> administration, account removal, command enqueue/read/WebSocket, and signed scan ingest.
> **Both ends of the command/ingest link exist** since DMI-66: the Pi daemon dials the socket,
> executes the headless scan, and uploads results. What remains is physical and operational — a
> provisioned Pi, service-manager packaging, key provisioning, and clock synchronization — so the
> path is exercised with signed requests and fake sockets rather than real hardware.
> `docs/architecture/ARCHITECTURE.md` describes the target state.

## Purpose

The backend is the cloud half of Dmitri: it receives a normalized scan result from a Pi
[agent](/hardware-agent/overview.md), persists the hosts/ports/services/CVEs it found, resolves each
host to a durable cross-scan identity, and then enriches every CVE against three public feeds —
**NVD**, **CISA KEV**, and **FIRST EPSS** — to produce an explainable, deterministic risk score per
finding. Read access to that data is now served over HTTP. It is two Python processes sharing one
Postgres database: a FastAPI **API** service and a long-running enrichment **worker**.

## Layout

| Area | Doc | What lives there |
|------|-----|------------------|
| Entry points & config | [api](/backend/api.md) | `main.py`, `worker_main.py`, `core/config.py`, `db/session.py`. |
| Routers | [routers](/backend/routers.md) | Data reads, auth/identity administration, scan ingest, and command HTTP/WS routes. |
| ORM / tables | [models](/backend/models.md) | Scan/enrichment, identity/activity, session, and command-channel SQLModel tables. |
| Wire schemas | [schemas](/backend/schemas.md) | Ingest/read/command shapes plus profile, member, auth, and invite models. |
| Business logic | [services](/backend/services.md) | Ingest/persistence, member administration, reads, enrichment/risk, and command lifecycle. |
| Auth subsystem | [auth](/backend/auth.md) | Sessions/passwords, activity stamps, invite lifecycle, role gates, and CORS. |
| Database schema | [migrations](/backend/migrations.md) | Alembic env + sixteen revisions with RLS and runtime grants. |

## Two processes, one database

Deployed as two Railway services (per `docs/adr/ADR-007`), both importing the `api` package
(`backend/src/api`):

- **API** — `uvicorn api.main:app`. Serves data reads, auth and identity administration, the
  command channel, and scan ingest.
- **Worker** — `python -m api.worker_main` (also the `backend-worker` console script). Polls
  `enrichment_jobs` forever and calls the upstream feeds.

The database is a **Supabase-managed Postgres 17** instance. The app **never creates tables** —
[Alembic owns the schema](/backend/migrations.md); the ORM metadata exists only to be the migration
target and to map queries.

## Data flow (the intended pipeline)

1. An agent `POST`s a `ScanIngestRequest` to `POST /api/v1/scans`, authenticated by `require_agent`
   and validated by [`schemas/scan.py`](/backend/schemas.md); [`ingest_scan`](/backend/services.md)
   then decides whether this fills a requested placeholder, creates an unrequested scan, or is a
   duplicate/foreign/late submission to refuse.
2. [`persist_scan`](/backend/services.md) writes, synchronously, `scan → scan_hosts → ports →
   services → cpes → findings`, computes an **initial risk snapshot** per finding, calls
   `upsert_hosts_for_scan` to resolve each `scan_host` to a durable `host`, and enqueues
   `enrichment_jobs` (one `nvd_cpe` per observed CPE; `nvd_cve` + `kev_cve` + `epss_cve` per finding
   that carries a CVE).
3. The separate [worker](/backend/services.md) claims job batches (`FOR UPDATE SKIP LOCKED` on
   Postgres), queries NVD/KEV/EPSS (all **DB-cached**), and applies results: CPE hits create new
   findings; a CVE hit **promotes confidence** (`probable → confirmed`), attaches KEV/EPSS data and
   source labels, and re-runs the [risk scorer](/backend/services.md).
4. Every finding ends with an explainable `risk_score` row in `risk_snapshots`.
5. **Wired:** [`GET /hosts`, `/hosts/{id}`, `/scans/{id}`, `/findings`](/backend/routers.md) read that
   persisted state back out over HTTP.

## Notes / gotchas

- **Per-scan observation vs durable identity.** Persisted hosts are `ScanHostRecord` (table
  `scan_hosts`, formerly `DeviceRecord`/`devices`) — one row per host per scan. The durable,
  cross-scan identity is `HostRecord` (table `hosts`), resolved by `upsert_hosts_for_scan`. See
  [glossary](/glossary.md) and [models](/backend/models.md).
- **Contract divergence resolved.** The OpenAPI `ScanIngestRequest` and the implemented
  `schemas/scan.py` (and example JSON) now both use `scan_mode`. Resolved by spec 015 /
  [ADR-013](../../../docs/adr/ADR-013-ingest-host-vocabulary-unification.md); see
  [contracts](/contracts.md).
- **Identity is wired.** Auth/session/password routes, invite create/accept/lookup/list/revoke,
  self profile/removal, and member list/role/remove routes all run over the identity tables.

# Citations

[1] [docs/adr/ADR-003-backend-stack.md](../../../docs/adr/ADR-003-backend-stack.md)
[2] [docs/adr/ADR-009-database-stack.md](../../../docs/adr/ADR-009-database-stack.md)
[3] [docs/adr/ADR-005-security-model.md](../../../docs/adr/ADR-005-security-model.md)
[4] [specs/013-backend-app-shell-rebuild](../../../specs/013-backend-app-shell-rebuild/TRUTH.md)
[5] [docs/adr/ADR-013-ingest-host-vocabulary-unification.md](../../../docs/adr/ADR-013-ingest-host-vocabulary-unification.md)
[6] [docs/adr/ADR-014-host-identity-resolution.md](../../../docs/adr/ADR-014-host-identity-resolution.md)
[7] [specs/015-read-path](../../../specs/015-read-path/TRUTH.md)

[8] [specs/030-users-invites-admin-api](../../../specs/030-users-invites-admin-api/TRUTH.md)