---
type: Package Overview
title: Backend — API + enrichment worker
description: The FastAPI backend — its read path and auth are wired — and the CVE-enrichment worker.
resource: backend/src/api
tags: [backend, fastapi, worker, persistence, enrichment, read, auth]
timestamp: 2026-07-24T00:00:00Z
---

# Backend — API + enrichment worker

> **Read path + auth + invites wired; ingest still not.** `api/main.py` registers
> `GET /api/v1/health`, the three [read routers](/backend/routers.md) (`GET /hosts`,
> `/hosts/{host_id}`, `/scans/{scan_id}`, `/findings`) — spec 015, now gated by `require_user` and
> org-scoped — the [auth routes](/backend/auth.md) (spec 016), and the invite routes (spec 017).
> The ingest route (`POST /api/v1/scans`) still exists only in the [contracts](/contracts.md)
> OpenAPI surface; `persist_scan` and the worker are still exercised **directly by tests**, not
> through the API — the agent→backend upload link does not exist yet, and the
> [device gate](/backend/device-auth.md) built for it is mounted on no route.
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
| Entry points & config | [api](/backend/api.md) | `main.py` (health + read routers), `worker_main.py`, `core/config.py`, `db/session.py`. |
| Routers | [routers](/backend/routers.md) | `routers/hosts.py`, `routers/scans.py`, `routers/findings.py` — the wired HTTP surface. |
| ORM / tables | [models](/backend/models.md) | `models/persistence.py` + `models/identity.py` — SQLModel tables on the metadata Alembic owns. |
| Wire schemas | [schemas](/backend/schemas.md) | `schemas/scan.py` (ingest input), `schemas/read.py` (wired read responses), `schemas/persistence.py` (legacy read projections). |
| Business logic | [services](/backend/services.md) | `persist_scan`, `upsert_hosts_for_scan`, the read-path queries, the worker loop, NVD/KEV/EPSS clients, and the risk scorer. |
| Auth subsystem | [auth](/backend/auth.md) | Login/refresh/logout + password change/reset, JWT + refresh families, argon2 password policy, `require_user`, and the request-id/CORS middleware. |
| Database schema | [migrations](/backend/migrations.md) | Alembic env + seven revisions, including Supabase RLS hardening and the `dmitri_runtime` role. |

## Two processes, one database

Deployed as two Railway services (per `docs/adr/ADR-007`), both importing the `api` package
(`backend/src/api`):

- **API** — `uvicorn api.main:app`. Serves `GET /api/v1/health` and the read path.
- **Worker** — `python -m api.worker_main` (also the `backend-worker` console script). Polls
  `enrichment_jobs` forever and calls the upstream feeds.

The database is a **Supabase-managed Postgres 17** instance. The app **never creates tables** —
[Alembic owns the schema](/backend/migrations.md); the ORM metadata exists only to be the migration
target and to map queries.

## Data flow (the intended pipeline)

1. An agent `POST`s a `ScanResult`, validated by [`schemas/scan.py`](/backend/schemas.md). *(Route
   not wired — tests call `persist_scan` directly.)*
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
- **Auth is now wired.** The [auth routes](/backend/auth.md) (login/refresh/logout + password
  change/reset) run in `main.py` over the `users` table + refresh/reset session tokens (spec 016).
  `orgs`/`invites` remain dormant — no invite endpoints run yet.

# Citations

[1] [docs/adr/ADR-003-backend-stack.md](../../../docs/adr/ADR-003-backend-stack.md)
[2] [docs/adr/ADR-009-database-stack.md](../../../docs/adr/ADR-009-database-stack.md)
[3] [docs/adr/ADR-005-security-model.md](../../../docs/adr/ADR-005-security-model.md)
[4] [specs/013-backend-app-shell-rebuild](../../../specs/013-backend-app-shell-rebuild/TRUTH.md)
[5] [docs/adr/ADR-013-ingest-host-vocabulary-unification.md](../../../docs/adr/ADR-013-ingest-host-vocabulary-unification.md)
[6] [docs/adr/ADR-014-host-identity-resolution.md](../../../docs/adr/ADR-014-host-identity-resolution.md)
[7] [specs/015-read-path](../../../specs/015-read-path/TRUTH.md)
