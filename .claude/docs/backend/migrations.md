---
type: Migration
title: Backend database migrations
description: The Alembic env and two revisions that own the schema, plus Supabase RLS hardening and the dmitri_runtime role.
resource: backend/alembic/env.py
tags: [backend, alembic, migrations, rls, supabase, database]
timestamp: 2026-07-21T00:00:00Z
---

# Backend database migrations

## Purpose

**Alembic owns the schema.** The application never calls `create_all`; every table, index,
constraint, and grant is created by a migration. `alembic/env.py` targets the same
`SQLModel.metadata` the [ORM models](/backend/models.md) register on, and the two revisions build the
scan/enrichment schema and then the identity schema — each followed by Supabase Row-Level-Security
hardening and grants to a dedicated `dmitri_runtime` login role.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `target_metadata` | `persistence.SQLModel.metadata` — importing `api.models.persistence` pulls in the shared metadata (identity tables register via the models package). | `backend/alembic/env.py:16` |
| `_migration_url()` | Requires a **separate** `DATABASE_URL_DIRECT` env var (the runtime pooler runs in transaction mode and cannot run DDL); normalized via `normalize_postgres_url`. | `backend/alembic/env.py:19` |
| `run_migrations_online()` | Builds a `NullPool` engine from the direct URL and runs migrations. | `backend/alembic/env.py:42` |
| `upgrade()` (rev `20260715_01`) | Creates the 14 application tables (`scans`, `artifacts`, `devices`, `ports`, `services`, `cpes`, `findings`, `enrichment_jobs`, `nvd_cache`, `kev_records`, `epss_records`, `kev_cache`, `epss_cache`, `risk_snapshots`) with their indexes/constraints. | `backend/alembic/versions/20260715_01_baseline.py:64` |
| RLS + role hardening (baseline) | `ENABLE ROW LEVEL SECURITY` on every app table; `REVOKE ALL` from `anon`/`authenticated`; `CREATE ROLE dmitri_runtime` (`LOGIN`, `BYPASSRLS`, `NOSUPERUSER`) granted only `SELECT/INSERT/UPDATE` + sequence usage. | `backend/alembic/versions/20260715_01_baseline.py:293` |
| `upgrade()` (rev `20260716_02`) | Adds `orgs`/`users`/`invites` (role checks + case-insensitive email unique index), a nullable `org_id` FK on `scans`, and extends RLS/revoke/grant to the identity tables. | `backend/alembic/versions/20260716_02_identity_schema.py:35` |

## How it connects

- The tables created here are mapped by the [ORM models](/backend/models.md); drift between the two
  is what Alembic autogenerate would catch.
- `_migration_url` reuses `normalize_postgres_url` from [config](/backend/api.md).
- The `dmitri_runtime` role is the principal the running API/worker connect as — its grant set
  (`SELECT/INSERT/UPDATE`, no `DELETE`) bounds what [services](/backend/services.md) can do.

## Notes / gotchas

- **Two URLs.** Runtime connects via the pooled `DATABASE_URL` (see [config](/backend/api.md));
  migrations need `DATABASE_URL_DIRECT` (a direct, non-pooled connection) or `env.py` raises.
- **`BYPASSRLS` but not superuser.** `dmitri_runtime` bypasses the RLS policies (the app is the trust
  boundary) while `anon`/`authenticated` — Supabase's PostgREST roles — are fully revoked, so the
  tables are unreachable through Supabase's auto-generated API.
- **No `DELETE` grant.** The runtime role cannot delete rows; persistence is append/update-only.
- `alembic.ini` sets `prepend_sys_path = src` so `import api...` resolves during migrations.

# Citations

[1] [docs/adr/ADR-009-database-stack.md](../../../docs/adr/ADR-009-database-stack.md)
[2] [docs/adr/ADR-005-security-model.md](../../../docs/adr/ADR-005-security-model.md)
[3] [specs/013-backend-app-shell-rebuild](../../../specs/013-backend-app-shell-rebuild/TRUTH.md)
