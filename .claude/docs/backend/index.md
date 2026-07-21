# Backend

The cloud half of Dmitri — a FastAPI ingest/persistence API and a CVE-enrichment worker over a
Supabase-managed Postgres. **Planned / not yet wired:** only `GET /api/v1/health` is served today;
`persist_scan` and the worker are exercised directly by tests.

## Overview & entry points

* [Backend — API + enrichment worker](./overview.md) — The FastAPI ingest/persistence backend and the CVE-enrichment worker — working code that nothing calls yet.
* [Backend entry points & config](./api.md) — The FastAPI app (health-only), the worker process entry, settings, and the DB engine/session.

## Data model

* [Backend ORM models](./models.md) — The SQLModel tables — scan persistence, enrichment/cache, risk snapshots, and dormant identity.
* [Backend wire schemas](./schemas.md) — The Pydantic ingest input (ScanResult) and the read/output projections (Persisted*).

## Services

* [Backend services — persistence, worker, enrichment, risk](./services.md) — The real work — persist_scan, the worker loop, the NVD/KEV/EPSS clients, and the explainable risk scorer.

## Migrations

* [Backend database migrations](./migrations.md) — The Alembic env and two revisions that own the schema, plus Supabase RLS hardening and the dmitri_runtime role.
