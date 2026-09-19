---
type: Migration
title: Backend database migrations
description: The Alembic env and revisions through AI chat scopes, usage telemetry, and analysis coverage columns. Head is `20260919_31`.
resource: backend/alembic/env.py
tags: [backend, alembic, migrations, rls, supabase, database]
timestamp: 2026-09-13T20:00:00Z
---

# Backend database migrations

## Purpose

**Alembic owns the schema.** The application never calls `create_all`; every table, index,
constraint, and grant is created by a migration. `alembic/env.py` targets the same
`SQLModel.metadata` the [ORM models](/backend/models.md) register on. The revision history builds the
scan/enrichment schema, the identity schema, the read-path/host-identity schema (spec
015): `scan_mode`/`status` on `scans`, the `devices`→`scan_hosts` rename, the durable `hosts` table,
and the `findings.finding_id` UUID — then the auth session tables (spec 016, DMI-60) and the
command-channel schema (spec 016, DMI-59): the `agents` and `commands` tables, later reshaped for
delivery by `20260731_13` (spec 022, DMI-64) — then the device-auth
schema (spec 017, DMI-61): `agent_nonces`, globally-unique user emails, and the `agents` secret
columns replaced by a plaintext `public_key`. Each DDL-only step is followed by Supabase
Row-Level-Security hardening and grants to a dedicated `dmitri_runtime` login role where it touches a
new table. Merge revisions join the activity, OS-inventory, and machine-inventory heads; industrial
observations land as `20260912_22`; `20260912_23` merges those heads; `20260912_24` adds
`ai_scan_analyses`; `20260912_25` adds enrichment retry columns; `20260912_26` adds AI retry columns;
`20260917_27`–`29` add writing-skill version, analysis coverage, and `ai_chat_messages`;
`20260918_30` adds chat `scope_type`/`scope_id`; `20260919_31` adds `ai_usage`. Head is `20260919_31`.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `target_metadata` | `persistence.SQLModel.metadata` — `env.py` imports `command`, `identity`, `persistence` from `api.models`, which transitively imports `session` too (the package `__init__.py` imports all four), so all tables register on the shared metadata before autogenerate. | `backend/alembic/env.py:16` |
| `_migration_url()` | Requires a **separate** `DATABASE_URL_DIRECT` env var (the runtime pooler runs in transaction mode and cannot run DDL); normalized via `normalize_postgres_url`. | `backend/alembic/env.py:19` |
| `run_migrations_online()` | Builds a `NullPool` engine from the direct URL and runs migrations. | `backend/alembic/env.py:42` |
| `upgrade()` (rev `20260715_01`) | Creates the 14 application tables (`scans`, `artifacts`, `devices`, `ports`, `services`, `cpes`, `findings`, `enrichment_jobs`, `nvd_cache`, `kev_records`, `epss_records`, `kev_cache`, `epss_cache`, `risk_snapshots`) with their indexes/constraints. `artifacts` is later dropped by `20260804_14`, so at head this baseline's table list is one short of the live schema — `test_migrations.py` carries a `dropped_tables` allowance for exactly that. | `backend/alembic/versions/20260715_01_baseline.py:64` |
| RLS + role hardening (baseline) | `ENABLE ROW LEVEL SECURITY` on every app table; `REVOKE ALL` from `anon`/`authenticated`; `CREATE ROLE dmitri_runtime` (`LOGIN`, `BYPASSRLS`, `NOSUPERUSER`) granted only `SELECT/INSERT/UPDATE` + sequence usage. The role statement is an `IF NOT EXISTS (SELECT 1 FROM pg_roles …) … ELSE ALTER ROLE … LOGIN BYPASSRLS` block, so a pre-existing role **converges** instead of being left as found; the downgrade's `DROP ROLE` swallows `dependent_objects_still_exist` — see the role notes below. | `backend/alembic/versions/20260715_01_baseline.py:293` |
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
| `upgrade()` (rev `20260727_12`, `finding_severity_domain`) | Adds check `ck_findings_severity` on `findings.severity` (`IN ('low','medium','high','critical')`); `upgrade()` guards for out-of-domain rows before applying. No RLS change — constraint only. | `backend/alembic/versions/20260727_12_finding_severity_domain.py` |
| `upgrade()` (rev `20260731_13`, `command_delivery`) | Makes `commands.scan_id` **nullable** (guarded by a pre-flight query for rows that would violate the new check), adds `ck_commands_scan_id_or_expired` — `scan_id IS NOT NULL OR status IN ('queued', 'expired')` — adds the partial unique index `uq_commands_active_agent ON commands (agent_id) WHERE status IN ('queued','delivered','running','uploading')`, and adds nullable `agents.connected_at`. `downgrade()` refuses to run while any null `scan_id` remains. | `backend/alembic/versions/20260731_13_command_delivery.py` |
| `upgrade()` (rev `20260804_14`, `scan_ingest_rework`) | Adds nullable `scans.agent_id` (FK → `agents.id`, **no backfill** — pre-existing rows stay `NULL`) and drops the `artifacts` table, which takes its owned identity sequence `artifacts_id_seq` with it. `downgrade()` recreates `artifacts` exactly as the baseline declared it, including `ix_artifacts_scan_id` and the FK → `scans`, then drops only `scans.agent_id`. Existing scan rows survive a full up→down→up round trip. | `backend/alembic/versions/20260804_14_scan_ingest_rework.py` |

| `upgrade()` (rev `20260808_15`, `user_delete_cascade`) | Drops and recreates exactly two FKs — `refresh_tokens_user_id_fkey` and `password_reset_tokens_user_id_fkey` — with `ondelete="CASCADE"`, and grants `DELETE ON public.users` to `dmitri_runtime`. Without it `DELETE FROM users` raised `ForeignKeyViolation` for any user with a live session, and the runtime role had no `DELETE` on `users` at all. `downgrade()` revokes the grant and recreates both FKs without `ondelete`. The child tables need **no** `DELETE` grant: the cascade runs through the referential-integrity trigger, which is not subject to the caller's privileges on the referencing table. | `backend/alembic/versions/20260808_15_user_delete_cascade.py` |
| `upgrade()` (rev `20260810_16`, `user_activity_and_invite_revoke`) | Adds nullable `TIMESTAMPTZ` `users.last_login_at` and `users.last_seen_at`, and grants `DELETE ON public.invites` to `dmitri_runtime` so pending invitations can be revoked. Downgrade revokes that grant before dropping both columns. | `backend/alembic/versions/20260810_16_user_activity_and_invite_revoke.py:12` |
| `upgrade()` (rev `20260811_17`, `agents_target_subnet`) | Adds one nullable, unindexed `agents.target_subnet` (`sa.String`) — the network an admin chose for a Pi. No grant statement: `agents` already grants `SELECT, INSERT, UPDATE` to `dmitri_runtime` from `20260723_07`, so `RUNTIME_GRANTS_BY_TABLE` is unchanged. `downgrade()` is a single `drop_column`. | `backend/alembic/versions/20260811_17_agents_target_subnet.py` |
| `upgrade()` (rev `20260904_18`, `scan_box_and_duration`) | Scan list/detail box attribution and duration columns used by the scan UI (spec 043). Head before the Home activity feed. | `backend/alembic/versions/20260904_18_scan_box_and_duration.py` |
| `upgrade()` (rev `20260905_19`, `home_activity_feed`) | Creates `activity` (int PK, `org_id`, `kind` CHECK, `occurred_at`, nullable `actor_user_id` with no FK, nullable `subject_id`, JSONB `payload`). Partial unique index `uq_activity_org_kind_subject` on guarded kinds. Paging index `(org_id, occurred_at DESC, id DESC)`. RLS plus `SELECT, INSERT` for `dmitri_runtime` (no UPDATE/DELETE). | `backend/alembic/versions/20260905_19_home_activity_feed.py` |
| `upgrade()` (rev `20260907_20`, `machine_inventory_depth`) | Adds nullable `hosts.machine_type` (CHECK of the nine literals plus NULL) and `hosts.vulnerability_count` (NOT NULL default 0). Creates empty `host_ports` and `host_findings` with unique constraints, indexes, RLS, and `SELECT/INSERT/UPDATE/DELETE` for `dmitri_runtime`. **No backfill.** Vocabulary is spelled literally in the revision, not imported. | `backend/alembic/versions/20260907_20_machine_inventory_depth.py` |
| `upgrade()` (rev `20260908_19`, `operating_system_inventory`) | Adds nullable JSON `operating_system_json` to `scan_hosts` and `hosts`. Parent is `20260903_18`, so it forks from the `20260904_18` → `20260905_19` → `20260907_20` line. | `backend/alembic/versions/20260908_19_operating_system_inventory.py` |
| `upgrade()` (rev `20260912_21`, `merge_inventory_and_os`) | Empty merge revision with `down_revision = ("20260907_20", "20260908_19")`, so Alembic has one `head` again. No schema change. Stepping back to either parent leaves two rows in `alembic_version`; `tests/conftest.py::_migrate` reads `get_current_heads()` for that reason. | `backend/alembic/versions/20260912_21_merge_inventory_and_os.py` |
| `upgrade()` (rev `20260912_22`, `industrial_observations`) | Creates `industrial_services` and `modbus_units`; adds `findings.modbus_unit_id` and `orgs.ot_digest_key`; RLS and `dmitri_runtime` grants. Parent is `20260912_20`. Renumbered from this branch's original `20260912_21` so it does not collide with main's inventory merge. | `backend/alembic/versions/20260912_22_industrial_observations.py` |
| `upgrade()` (rev `20260912_23`, `merge_industrial_and_inventory`) | Empty merge of `20260912_21` (inventory+OS) and `20260912_22` (industrial observations). | `backend/alembic/versions/20260912_23_merge_industrial_and_inventory.py` |
| `upgrade()` (rev `20260912_24`, `ai_scan_analyses`) | Creates `ai_scan_analyses` (unique `scan_id`, RLS + runtime grants). Parent `20260912_23`. | `backend/alembic/versions/20260912_24_ai_scan_analyses.py` |
| `upgrade()` (rev `20260912_25`, `enrichment_retries`) | Enrichment job retry columns. | `backend/alembic/versions/20260912_25_enrichment_retries.py` |
| `upgrade()` (rev `20260912_26`, `ai_scan_analysis_retries`) | Adds indexed `ai_scan_analyses.next_attempt_at`; renames `last_error_code` to `last_error`, so both job tables share the `claim_jobs` columns. Current head. | `backend/alembic/versions/20260912_26_ai_scan_analysis_retries.py` |

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
- **Roles are cluster-scoped; migrations are database-scoped.** That mismatch is why the baseline's
  `CREATE ROLE dmitri_runtime` is guarded and its `DROP ROLE` tolerates
  `dependent_objects_still_exist`: once the role exists from one database in the cluster, migrating a
  sibling database (typically `dmitri_test` next to the dev `postgres`) would otherwise raise
  `DuplicateObject` — and a downgrade cannot drop a role still holding privileges elsewhere. Before
  this guard landed the entire DB test suite silently skipped, which is how a delivery-path FK bug
  reached review unnoticed. The exception handler catches **only** `2BP01`, never `WHEN OTHERS`.
- **The DB tests only run when `DATABASE_URL_TEST` is set**, and it must name a database literally
  called `dmitri_test` (`backend/tests/conftest.py:44`, asserted again at connect time). Unset, ~249
  tests skip rather than fail.
- **Never seed via an ORM model at a pinned old revision.** A test that calls `_migrate(engine, "<old
  rev>")` and then inserts through `ScanRecord`/`FindingRecord` breaks the moment a *later* migration
  adds a column, because the model always tracks head — `20260804_14`'s `scans.agent_id` broke
  `test_finding_severity_migration.py` exactly this way (`UndefinedColumn`). Seed with explicit
  `sa.text()` INSERTs naming only the columns that exist at that revision; `test_scan_ingest_migration.py`
  and the sibling tests in `test_migrations.py` are the pattern to copy.
- **`BYPASSRLS` but not superuser.** `dmitri_runtime` bypasses the RLS policies (the app is the trust
  boundary) while `anon`/`authenticated` — Supabase's PostgREST roles — are fully revoked, so the
  tables are unreachable through Supabase's auto-generated API.
- **`BYPASSRLS` is load-bearing, and the guard converges it.** RLS is `ENABLE`d on every application
  table and there is **no `CREATE POLICY` anywhere in the repo** — so a role without `BYPASSRLS` is
  denied every read and write by default, not merely scoped. The existence guard above therefore has
  an `ELSE ALTER ROLE dmitri_runtime WITH LOGIN BYPASSRLS`: checking only existence let a
  pre-existing role keep whatever attributes it had, so migrations reported success against a
  database the app could not write to. Fixed 2026-08-03; pinned by
  `test_live_migration_tolerates_preexisting_runtime_role`, which creates the role bare and asserts
  `rolbypassrls` after migrating to head. The `ALTER` names **only** `LOGIN` and `BYPASSRLS` —
  naming `NOSUPERUSER`, even to clear it, requires the executing role to be `SUPERUSER`, which the
  migration runner is not under Supabase. Consequence: the `NO*` hardening applies on creation only,
  so a pre-existing role holding e.g. `CREATEROLE` is not de-escalated here.
- **Editing the baseline only reaches databases that migrate from base.** A cluster already past
  `20260715_01` does not re-run it; a misconfigured role there needs a one-off
  `ALTER ROLE dmitri_runtime WITH LOGIN BYPASSRLS` or a follow-up revision.
- **Exceptional runtime grants are table-specific.** `users` and `invites` add `DELETE` to the
  baseline `SELECT/INSERT/UPDATE`; `agent_nonces` instead has `SELECT/INSERT/DELETE` and no
  `UPDATE`, because a nonce is immutable and prunable. Every other table keeps the append/update
  default. `test_migrations.py` therefore uses `RUNTIME_GRANTS_BY_TABLE` rather than one global set.
- `alembic.ini` sets `prepend_sys_path = src` so `import api...` resolves during migrations.
- Head is a single revision. `20260912_20` is an empty merge of `20260905_19` (activity feed) and
  `20260908_19` (OS inventory). `20260912_21` on main is the empty merge of inventory depth and OS.
  Do not rewrite released revisions. `20260912_22` adds `industrial_services`, `modbus_units`,
  `findings.modbus_unit_id`, and `orgs.ot_digest_key`. `20260912_23` merges those two heads.
  `20260912_24` adds `ai_scan_analyses`. `20260912_25` adds enrichment retries. `20260912_26` is the current head (AI retries).
  `test_alembic_single_head.py` fails the suite if a second head appears.

# Citations

[1] [docs/adr/ADR-009-database-stack.md](../../../docs/adr/ADR-009-database-stack.md)
[2] [docs/adr/ADR-005-security-model.md](../../../docs/adr/ADR-005-security-model.md)
[3] [specs/013-backend-app-shell-rebuild](../../../specs/013-backend-app-shell-rebuild/TRUTH.md)
[4] [docs/adr/ADR-013-ingest-host-vocabulary-unification.md](../../../docs/adr/ADR-013-ingest-host-vocabulary-unification.md)
[5] [docs/adr/ADR-014-host-identity-resolution.md](../../../docs/adr/ADR-014-host-identity-resolution.md)
[6] [specs/015-read-path](../../../specs/015-read-path/TRUTH.md)
