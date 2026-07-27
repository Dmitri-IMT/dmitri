---
type: Migration
title: Backend database migrations
description: The Alembic env and eleven revisions that own the schema — baseline through the command channel, auth session tokens, agent nonces, global user-email uniqueness, and agent public keys — plus Supabase RLS hardening and the dmitri_runtime role.
resource: backend/alembic/env.py
tags: [backend, alembic, migrations, rls, supabase, database]
timestamp: 2026-07-27T00:00:00Z
---

# Backend database migrations

## Purpose

**Alembic owns the schema.** The application never calls `create_all`; every table, index,
constraint, and grant is created by a migration. `alembic/env.py` targets the same
`SQLModel.metadata` the [ORM models](/backend/models.md) register on. Eleven chained revisions build the
scan/enrichment schema, the identity schema, the read-path/host-identity schema (spec
015): `scan_mode`/`status` on `scans`, the `devices`→`scan_hosts` rename, the durable `hosts` table,
and the `findings.finding_id` UUID — then the auth session tables (spec 016, DMI-60) and the
command-channel schema (spec 016, DMI-59): the `agents` and `commands` tables — then the device-auth
schema (spec 017, DMI-61): `agent_nonces`, globally-unique user emails, and the `agents` secret
columns replaced by a plaintext `public_key`. Each DDL-only step is followed by Supabase
Row-Level-Security hardening and grants to a dedicated `dmitri_runtime` login role where it touches a
new table.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `target_metadata` | `persistence.SQLModel.metadata` — `env.py` imports `command`, `identity`, `persistence` from `api.models`, which transitively imports `session` too (the package `__init__.py` imports all four), so all tables register on the shared metadata before autogenerate. | `backend/alembic/env.py:16` |
| `_migration_url()` | Requires a **separate** `DATABASE_URL_DIRECT` env var (the runtime pooler runs in transaction mode and cannot run DDL); normalized via `normalize_postgres_url`. | `backend/alembic/env.py:19` |
| `run_migrations_online()` | Builds a `NullPool` engine from the direct URL and runs migrations. | `backend/alembic/env.py:42` |
| `upgrade()` (rev `20260715_01`) | Creates the 14 application tables (`scans`, `artifacts`, `devices`, `ports`, `services`, `cpes`, `findings`, `enrichment_jobs`, `nvd_cache`, `kev_records`, `epss_records`, `kev_cache`, `epss_cache`, `risk_snapshots`) with their indexes/constraints. | `backend/alembic/versions/20260715_01_baseline.py:64` |
| RLS + role hardening (baseline) | `ENABLE ROW LEVEL SECURITY` on every app table; `REVOKE ALL` from `anon`/`authenticated`; `CREATE ROLE dmitri_runtime` (`LOGIN`, `BYPASSRLS`, `NOSUPERUSER`) granted only `SELECT/INSERT/UPDATE` + sequence usage. | `backend/alembic/versions/20260715_01_baseline.py:293` |
| `upgrade()` (rev `20260716_02`) | Adds `orgs`/`users`/`invites` (role checks + case-insensitive email unique index), a nullable `org_id` FK on `scans`, and extends RLS/revoke/grant to the identity tables. | `backend/alembic/versions/20260716_02_identity_schema.py:35` |
| `upgrade()` (rev `20260722_03`, `scan_mode_status`) | Drops `scans.target_mode`/`scans.scan_profile`, adds `scans.scan_mode` (not null) and `scans.status` (not null, server default `completed`). | `backend/alembic/versions/20260722_03_scan_mode_status.py:13` |
| `upgrade()` (rev `20260722_04`, `scan_host_rename`) | Renames table `devices`→`scan_hosts` (and its id sequence), renames `ports.device_id`/`findings.device_id`→`scan_host_id`. | `backend/alembic/versions/20260722_04_scan_host_rename.py:11` |
| `upgrade()` (rev `20260722_05`, `host_identity`) | Creates the `hosts` table (`identity_key`, ip/mac/hostname/vendor, `open_ports_count`, `highest_severity`, `first_seen_at`/`last_seen_at`) with a `(org_id, identity_key)` unique index (`NULLS NOT DISTINCT`); adds nullable `scan_hosts.host_id` FK → `hosts`; RLS + revoke + `dmitri_runtime` grant on `hosts`. | `backend/alembic/versions/20260722_05_host_identity.py:13` |
| `upgrade()` (rev `20260722_06`, `finding_uuid`) | Adds `findings.finding_id` (UUID, nullable), backfills via `gen_random_uuid()`, sets `NOT NULL`, then a unique index. | `backend/alembic/versions/20260722_06_finding_uuid.py:12` |
| `upgrade()` (rev `20260723_07`, `command_channel`) | Creates `agents` (encrypted-secret columns `secret_ciphertext`/`secret_nonce`/`secret_key_version`, `revoked_at`, `last_seen_at`), then `commands` (agent FK, `scan_id` FK **UNIQUE** via `uq_commands_scan_id`, VARCHAR `status`, four timestamps); indexes `ix_agents_org_id`/`ix_commands_org_id`/`ix_commands_agent_id`; RLS + revoke + `dmitri_runtime` grant on both. Downgrade revokes then drops `commands`→`agents`. | `backend/alembic/versions/20260723_07_command_channel.py` |
| `upgrade()` (rev `20260722_07`, `auth_sessions`) | Creates `refresh_tokens` (`user_id` FK → `users`, `family_id` indexed, unique `token_hash`, `family_expires_at`, `rotated_at`/`revoked_at`) and `password_reset_tokens` (`user_id` FK, unique `token_hash`, `expires_at`, `consumed_at`); RLS + revoke + `dmitri_runtime` grant on both. Backs [auth](/backend/auth.md). Chained **after** `command_channel` (both were cut as `_07` independently; this revision's `down_revision` points at `20260723_07` to keep a single head). | `backend/alembic/versions/20260722_07_auth_sessions.py:35` |
| `upgrade()` (rev `20260724_08`, `timestamptz`) | Converts every naive `TIMESTAMP` column written via `utc_now()` (across `enrichment_jobs`, `epss_cache`/`epss_records`, `findings`, `hosts`, `invites`, `kev_cache`/`kev_records`, `nvd_cache`, `orgs`, `ports`, `risk_snapshots`, `scan_hosts`, `scans`, `users`) to `TIMESTAMPTZ` via `AT TIME ZONE 'UTC'` — fixes naive/aware datetime comparison errors that broke refresh-token and password-reset expiry checks. Pure reinterpretation, no data change. | `backend/alembic/versions/20260724_08_timestamptz.py` |
| `upgrade()` (rev `20260724_09`, `agent_nonces`) | Creates `agent_nonces` (`agent_id` FK → `agents`, `nonce`, `expires_at`) with `uq_agent_nonces_agent_id_nonce` and `ix_agent_nonces_expires_at` — and deliberately **no** separate `agent_id` index. RLS + revoke + a grant of exactly `SELECT, INSERT, DELETE` to `dmitri_runtime`. Backs [device auth](/backend/device-auth.md). | `backend/alembic/versions/20260724_09_agent_nonces.py` |
| `upgrade()` (rev `20260724_10`, `users_email_global_unique`) | Drops `ix_users_org_email` and creates `ix_users_email` — a unique index on `lower(email)` with **no** `org_id` component, making user emails globally unique. Unguarded on purpose: a genuine cross-org duplicate must fail loudly. Exact-inverse downgrade. | `backend/alembic/versions/20260724_10_users_email_global_unique.py` |
| `upgrade()` (rev `20260724_11`, `agents_public_key`) | Drops `agents.secret_ciphertext`/`secret_nonce`/`secret_key_version` and adds `public_key` (`LargeBinary`, NOT NULL, no server default — the table is empty). The `agents` security fence is untouched. `downgrade()` restores the three columns exactly as `20260723_07` declared them and documents that it is knowingly lossy if rows exist. | `backend/alembic/versions/20260724_11_agents_public_key.py` |

## How it connects

- The tables created here are mapped by the [ORM models](/backend/models.md); drift between the two
  is what Alembic autogenerate would catch.
- `_migration_url` reuses `normalize_postgres_url` from [config](/backend/api.md).
- The `dmitri_runtime` role is the principal the running API/worker and the
  [management commands](/backend/management.md) connect as — its grant set bounds what
  [services](/backend/services.md) can do.

## Notes / gotchas

- **Two URLs.** Runtime connects via the pooled `DATABASE_URL` (see [config](/backend/api.md));
  migrations need `DATABASE_URL_DIRECT` (a direct, non-pooled connection) or `env.py` raises.
- **`BYPASSRLS` but not superuser.** `dmitri_runtime` bypasses the RLS policies (the app is the trust
  boundary) while `anon`/`authenticated` — Supabase's PostgREST roles — are fully revoked, so the
  tables are unreachable through Supabase's auto-generated API.
- **No `DELETE` grant — except on `agent_nonces`.** Every other table grants `dmitri_runtime` only
  `SELECT/INSERT/UPDATE`, so persistence is append/update-only. `agent_nonces` inverts that: it is
  granted `SELECT/INSERT/DELETE` and **withheld** `UPDATE`, because a nonce is written once, never
  mutated, and must be prunable once expired. `test_migrations.py`'s privilege loop is therefore
  table-aware (`RUNTIME_GRANTS_BY_TABLE`) rather than asserting one grant set for everything.
- `alembic.ini` sets `prepend_sys_path = src` so `import api...` resolves during migrations.

# Citations

[1] [docs/adr/ADR-009-database-stack.md](../../../docs/adr/ADR-009-database-stack.md)
[2] [docs/adr/ADR-005-security-model.md](../../../docs/adr/ADR-005-security-model.md)
[3] [specs/013-backend-app-shell-rebuild](../../../specs/013-backend-app-shell-rebuild/TRUTH.md)
[4] [docs/adr/ADR-013-ingest-host-vocabulary-unification.md](../../../docs/adr/ADR-013-ingest-host-vocabulary-unification.md)
[5] [docs/adr/ADR-014-host-identity-resolution.md](../../../docs/adr/ADR-014-host-identity-resolution.md)
[6] [specs/015-read-path](../../../specs/015-read-path/TRUTH.md)
