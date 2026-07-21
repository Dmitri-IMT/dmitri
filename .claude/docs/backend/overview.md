---
type: Package Overview
title: Backend — API + enrichment worker
description: The FastAPI ingest/persistence backend and the CVE-enrichment worker — working code that nothing calls yet.
resource: backend/src/api
tags: [backend, fastapi, worker, persistence, enrichment]
timestamp: 2026-07-21T00:00:00Z
---

# Backend — API + enrichment worker

> **Planned / not yet wired.** This backend is working, tested code, but **nothing calls it over
> HTTP today.** `api/main.py` registers **only** `GET /api/v1/health`; the ingest and read routes
> exist in the [contracts](/contracts.md) OpenAPI surface but are **not** wired into FastAPI. The
> real persistence and enrichment logic (`persist_scan`, the worker) is exercised **directly by
> tests**, not through the API. The agent→backend upload link does not exist yet. Treat everything
> below as the shape the code *has*, not a live pipeline. `docs/architecture/ARCHITECTURE.md`
> describes the target state.

## Purpose

The backend is the cloud half of Dmitri: it receives a normalized scan result from a Pi
[agent](/hardware-agent/overview.md), persists the hosts/ports/services/CVEs it found, and then
enriches every CVE against three public feeds — **NVD**, **CISA KEV**, and **FIRST EPSS** — to
produce an explainable, deterministic risk score per finding. It is two Python processes sharing one
Postgres database: a FastAPI **API** service and a long-running enrichment **worker**.

## Layout

| Area | Doc | What lives there |
|------|-----|------------------|
| Entry points & config | [api](/backend/api.md) | `main.py` (health only), `worker_main.py`, `core/config.py`, `db/session.py`. |
| ORM / tables | [models](/backend/models.md) | `models/persistence.py` + `models/identity.py` — SQLModel tables on the metadata Alembic owns. |
| Wire schemas | [schemas](/backend/schemas.md) | `schemas/scan.py` (ingest input) + `schemas/persistence.py` (read projections). |
| Business logic | [services](/backend/services.md) | `persist_scan`, the worker loop, NVD/KEV/EPSS clients, and the risk scorer. |
| Database schema | [migrations](/backend/migrations.md) | Alembic env + two revisions, including Supabase RLS hardening and the `dmitri_runtime` role. |

## Two processes, one database

Deployed as two Railway services (per `docs/adr/ADR-007`), both importing the `api` package
(`backend/src/api`):

- **API** — `uvicorn api.main:app`. Serves `GET /api/v1/health` (a real `SELECT 1` round-trip).
- **Worker** — `python -m api.worker_main` (also the `backend-worker` console script). Polls
  `enrichment_jobs` forever and calls the upstream feeds.

The database is a **Supabase-managed Postgres 17** instance. The app **never creates tables** —
[Alembic owns the schema](/backend/migrations.md); the ORM metadata exists only to be the migration
target and to map queries.

## Data flow (the intended pipeline)

1. An agent `POST`s a `ScanResult`, validated by [`schemas/scan.py`](/backend/schemas.md). *(Route
   not wired — tests call `persist_scan` directly.)*
2. [`persist_scan`](/backend/services.md) writes, synchronously, `scan → devices → ports → services →
   cpes → findings`, computes an **initial risk snapshot** per finding, and enqueues
   `enrichment_jobs` (one `nvd_cpe` per observed CPE; `nvd_cve` + `kev_cve` + `epss_cve` per finding
   that carries a CVE).
3. The separate [worker](/backend/services.md) claims job batches (`FOR UPDATE SKIP LOCKED` on
   Postgres), queries NVD/KEV/EPSS (all **DB-cached**), and applies results: CPE hits create new
   findings; a CVE hit **promotes confidence** (`probable → confirmed`), attaches KEV/EPSS data and
   source labels, and re-runs the [risk scorer](/backend/services.md).
4. Every finding ends with an explainable `risk_score` row in `risk_snapshots`.

## Notes / gotchas

- **Persisted hosts are `DeviceRecord`** (table `devices`) — the frozen ingest word. Everywhere else
  the domain term is *host*; see [glossary](/glossary.md).
- **Contract divergence.** The OpenAPI `ScanIngestRequest` uses `scan_mode`, while the implemented
  `schemas/scan.py` (and the example JSON) use `target_mode` + `scan_profile`. Reference
  [contracts](/contracts.md); do not reconcile here.
- **Identity is dormant.** `orgs`/`users`/`invites` tables and models exist to back the OpenAPI
  auth/invite surface, but no auth code runs — `main.py` has no such routes.

# Citations

[1] [docs/adr/ADR-003-backend-stack.md](../../../docs/adr/ADR-003-backend-stack.md)
[2] [docs/adr/ADR-009-database-stack.md](../../../docs/adr/ADR-009-database-stack.md)
[3] [docs/adr/ADR-005-security-model.md](../../../docs/adr/ADR-005-security-model.md)
[4] [specs/013-backend-app-shell-rebuild](../../../specs/013-backend-app-shell-rebuild/TRUTH.md)
