---
type: Infrastructure
title: Supabase (managed Postgres)
description: How Dmitri uses Supabase purely as arms-length managed Postgres 17 — not its Auth, Data API, or client SDK.
resource: supabase/config.toml
tags: [infra, supabase, postgres, database]
timestamp: 2026-07-21T00:00:00Z
---

# Supabase (managed Postgres)

## Purpose

Dmitri uses **Supabase as managed Postgres, and nothing else**. The backend connects
straight to the database over psycopg3 — it does not use the Supabase client SDK, Supabase
Auth, the auto-generated Data (PostgREST) API, Realtime, Storage, or Edge Functions. The only
Supabase artifact committed to the repo is `supabase/config.toml`, which configures the
*local* development stack that `supabase start` brings up (project id `dmitri`, Postgres 17 on
port 54322). The hosted `nspi` project is a plain Postgres 17 instance reached via the pooler.
Schema ownership lives entirely in `backend/alembic/`; there are no Supabase migrations or edge
functions under `supabase/` (only `config.toml` plus CLI temp/branch metadata in `.temp/` and
`.branches/`). The posture is deliberately arms-length and defensive: treat the surrounding
Supabase platform as attack surface Dmitri does not want, and let Alembic lock the database
down.

## Key files / settings

| Setting / artifact | Value | Reference |
|--------------------|-------|-----------|
| Project id | `dmitri` | `supabase/config.toml:5` |
| Postgres major version | `17` | `supabase/config.toml:42` |
| Local DB port | `54322` | `supabase/config.toml:34` |
| Local pooler | `enabled = false`, transaction mode, port 54329 | `supabase/config.toml:44-54` |
| Data API schemas | `public`, `graphql_public` (auto-expose left off) | `supabase/config.toml:7-24` |
| Auth / Realtime / Storage | `enabled = true` **locally only** — unused by the backend | `supabase/config.toml:87`, `155`, `115` |
| Local admin DSN | `postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres` | `install.sh:11`, `install.ps1:13` |
| Local DB container | `supabase_db_dmitri` | `install.sh:12`, `install.ps1:14` |
| Runtime connection (`DATABASE_URL`) | Pooled 6543 (transaction), `dmitri_runtime` login, `?sslmode=require`, prepared statements disabled | `backend/.env.example` |
| Migration connection (`DATABASE_URL_DIRECT`) | Direct/session 5432, `postgres` admin login — required by Alembic, never falls back to `DATABASE_URL` | `backend/alembic/env.py:19-27` |

**Arms-length / defensive posture (enforced by the Alembic baseline, summarized here):**

- The baseline migration enables RLS (without policies) on every application table, revokes
  `anon`/`authenticated` privileges, and provisions its own `dmitri_runtime LOGIN` role that
  the app connects as — never the administrative `postgres` login. Detail lives in
  [migrations](/backend/migrations.md).
- **Migrations vs runtime split.** `backend/alembic/env.py` reads *only*
  `DATABASE_URL_DIRECT` (`env.py:19-27`) — a direct/session connection on 5432 where DDL runs
  in a stable session. Runtime uses the pooled `DATABASE_URL` on 6543 with psycopg
  `prepare_threshold=None` (pooler-safe: transaction-mode pooling reassigns physical backends
  mid-session, which breaks server-side prepared statements).
- The backend implements its **own** identity tables (orgs/users/invites) plus JWT /
  refresh-cookie auth in the API contract rather than delegating to Supabase Auth. See
  [api](/backend/api.md).
- No Supabase-native branching or CLI-driven migrations run our schema — provisioning is
  manual and Alembic-driven.

## How it connects

- **Schema owner:** [migrations](/backend/migrations.md) — Alembic is the sole source of
  truth for the schema, the RLS lockdown, and the `dmitri_runtime` role.
- **Runtime consumers:** the [backend](/backend/overview.md) API + worker connect over
  psycopg3 using the pooled `DATABASE_URL`; the health route round-trips `SELECT 1` through it.
- **Deploy topology:** the hosted Supabase project pairs with the two Railway services — see
  [deployment](./deployment.md).
- **System context / build status:** [overview](/overview.md). Only the hardware agent runs
  today; the backend (and therefore its live use of hosted Supabase) is coded, not yet wired.

## Notes / gotchas

- **`config.toml` describes the *local* stack only.** Auth/Realtime/Storage being `enabled`
  there does not mean Dmitri uses them — they come up with `supabase start` for local dev but
  the app ignores them. The hosted project should have its Data API **disabled** and automatic
  RLS **enabled** as a dashboard backstop (the migration is the real enforcement).
- **Direct 5432 is IPv6-only** on Supabase (`db.<ref>.supabase.co`). On an IPv4-only network
  use the Session pooler on 5432 for `DATABASE_URL_DIRECT`.
- **`?sslmode=require`** must be appended to both URLs — psycopg3 reads it from the URL string,
  not from `connect_args`.
- **Free-tier auto-pause** (7 days idle) turns a paused DB into a dead API; add a weekly
  keep-alive or upgrade before real scan data accumulates.
- The local `install.sh`/`install.ps1` flow also recreates a scratch `dmitri_test` database in
  the same container for isolated backend tests, and runs Alembic against the local admin DSN
  with `DATABASE_URL_DIRECT` set in the shell only.

# Citations

- [ADR-009 — database stack](../../docs/adr/ADR-009-database-stack.md)
- [docs/cloud/README.md](../../docs/cloud/README.md)
- [docs/cloud/supabase/SETUP.md](../../docs/cloud/supabase/SETUP.md)
- [docs/cloud/railway/SETUP.md](../../docs/cloud/railway/SETUP.md)
