# Backend

The cloud half of Dmitri — a FastAPI API and a CVE-enrichment worker over a Supabase-managed
Postgres. **Read path wired, ingest not:** `GET /api/v1/health` plus `/hosts`, `/hosts/{host_id}`,
`/scans/{scan_id}`, `/findings` are served today; `POST /api/v1/scans` (ingest) and auth are still
contract-defined only, and `persist_scan`/the worker are exercised directly by tests.

## Overview & entry points

* [Backend — API + enrichment worker](./overview.md) — The FastAPI backend (read path wired) and the CVE-enrichment worker.
* [Backend entry points & config](./api.md) — The FastAPI app (health + the wired read path), the worker process entry, settings, and the DB engine/session.
* [Backend routers](./routers.md) — The three FastAPI routers that wire the read path — GET /hosts, /hosts/{id}, /scans/{id}, /findings.

## Data model

* [Backend ORM models](./models.md) — The SQLModel tables — scan persistence, host identity, enrichment/cache, risk snapshots, dormant identity, and the command channel.
* [Backend wire schemas](./schemas.md) — The Pydantic ingest input (ScanResult), the legacy read/output projections (Persisted*), and the new read-path response schemas.

## Services

* [Backend services — persistence, host identity, read, enrichment, risk](./services.md) — persist_scan, host-identity upsert, the read-path queries, the worker loop, the NVD/KEV/EPSS clients, the explainable risk scorer, and the command lifecycle rulebook.

## Migrations

* [Backend database migrations](./migrations.md) — The Alembic env and seven revisions that own the schema — baseline through the command channel — plus Supabase RLS hardening and the dmitri_runtime role.
