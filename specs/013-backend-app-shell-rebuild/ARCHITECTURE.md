# ARCHITECTURE — Backend app shell rebuild (DMI-56)

> Backend-layer feature. Nothing under `hardware-agent/` changes; the TUI/`ScanRunner`
> integration rule does not apply (no orchestrator/runner parameter changes). The equivalent
> discipline here: the backend has **two entry points** — the FastAPI app (`api.main`) and the
> worker process (`api.worker_main` → `api.services.worker`) — and both consume the settings
> model and the session stack. Every change to `core/config.py` or `db/session.py` must be
> verified against **both** entry points before this feature is complete.

## System context

The backend sits after the Pi agent in the product pipeline: Pi scan → `POST /scans` ingest →
persistence (`services/persistence.py`) → enrichment jobs → worker (KEV/EPSS/NVD) → risk
scoring → read APIs (future). Decision B8 (`docs/roadmap/BACKEND.md` § Reuse) keeps that
engine (`services/`) and discards the app shell. This feature builds the replacement shell:

- **FastAPI app** — minimal skeleton, health route with a real DB round-trip, no business
  routes, no auth, no schema creation at boot. Replaces the 371-line `main.py` monolith.
- **Alembic** — sole owner of the schema. Baseline migration captures the existing model tree's
  table/column shape **as-is** (no `devices`→`hosts` rename, no `org_id` — those are DMI-58 /
  the ingest issue), then enables RLS and closes Supabase Data API role access on every table.
  `init_db()` / `create_all()` removed everywhere.
- **Settings** — env-only, Postgres-only (SQLite default removed), pooler/direct URL split.

**DB-access style (decided, human-approved): sync everywhere.** Sync SQLModel `Session` +
psycopg3 for API routes, worker, and the kept engine. No asyncpg, no async sessions.
Backed by `docs/research/sync-vs-async-db-stack.md`.
**Supersedes/conflicts:** ADR-009's "Driver assíncrono: asyncpg" section is superseded by
this decision (the ADR is not edited here). ADR-009's "psycopg2 as Alembic dev dependency"
line is likewise superseded — psycopg3 serves both runtime and Alembic.

Deployment target: hosted `nspi` (Supabase `us-east-1` + Railway, `docs/cloud/README.md`).
The existing API and worker Railway definitions are wired to the real DMI-56 entry points;
no other Railway or AWS configuration changes in this feature (scope fence). Amendment
(human-approved 2026-07-16): setting the `worker` service's missing Railway `rootDirectory`
to `/backend`, mirroring the `api` service, is in-scope Task 8 wiring — without it the
worker's build context cannot resolve the entry point its definition names.

`HUMAN_INFRA_REQUIRED`: confirming the hosted `nspi` database reports Postgres major 17,
applying the baseline migration to it (direct-5432 credentials), assigning a generated
password to the migration-created `dmitri_runtime` login, and replacing Railway's runtime
URLs with that login are human steps, not agent steps. The hosted DB is empty until this
feature (`docs/cloud/supabase/SETUP.md`), so migration apply is a plain `alembic upgrade
head` — no stamping of pre-existing tables.
The high-entropy runtime password is generated locally and assigned through psql's interactive
`\password dmitri_runtime` prompt—never an `ALTER ROLE ... PASSWORD '...'` SQL literal. The
operator URL-encodes it when constructing the restricted pooler URL and stores that URL as a
sealed Railway `DATABASE_URL`; the password never appears in a migration, command example,
test, shell/SQL history, or tracked file. The direct administrative URL stays in the operator's
gitignored local `.env` and is exported only for an Alembic command. It is never defined,
shared, or referenced in either Railway service. Local test Postgres (for the
migration/health tests) is also human-provided; tests skip cleanly without it.
Pre-flight before the hosted apply: verify the connected role can create a `BYPASSRLS` role —
Supabase's `postgres` is **not** a superuser, and PG16+ allows `CREATE ROLE ... BYPASSRLS`
only from a superuser or a role that itself holds `BYPASSRLS` (check
`SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user`); Supabase's `supautils`
extension has historically gated this role DDL. The local test container runs as a true
superuser, so this failure mode is invisible to tests. Fallback if the hosted create is
refused: replace `BYPASSRLS` with explicit permissive policies for `dmitri_runtime` on the 14
tables (needs no special attribute) — a spec amendment, not an improvised change.
The same pre-flight confirms `dmitri_runtime` is absent. An existing role is unexpected drift
and blocks migration; the baseline never adopts a role it did not create.
Hosted rollback is also a human operation: stop both Railway services, wait for their pooled
database sessions to drain, export the locally held `DATABASE_URL_DIRECT`, run `alembic
downgrade base`, unset the variable, then
verify that the 14 tables and `dmitri_runtime` are absent. API and worker remain stopped until
a compatible schema is applied; they must never run while their tables and login are being
dropped.

## Data model / contracts

### Connection targets (ADR-009 / B4+B5, binding)

| Context | Env var | Target | Engine args |
|---------|---------|--------|-------------|
| API + worker runtime | `DATABASE_URL` | `dmitri_runtime.<project-ref>` on the Supabase pooler **6543** (transaction mode), `?sslmode=require` in the URL | `pool_pre_ping=True`, `connect_args={"prepare_threshold": None, "connect_timeout": 10}` |
| Alembic migrations | `DATABASE_URL_DIRECT` | Direct **5432**, `?sslmode=require` (Supabase direct is IPv6-only by default — from an IPv4-only network use the **session pooler on 5432**, per `docs/cloud/supabase/SETUP.md`; never 6543) | plain engine; env.py fails with a clear error if unset |
| Tests | `DATABASE_URL_TEST` | Dedicated disposable Postgres 17 database named exactly `dmitri_test`, direct — e.g. `postgresql+psycopg://postgres:test@localhost:5432/dmitri_test` (the `dmitri-test-pg` Docker container) | DB-touching tests skip when unset; refuse any other database name before migration or cleanup |

`prepare_threshold=None` is mandatory: transaction-mode PgBouncer/Supavisor does not support
prepared statements (research §3). `sslmode=require` travels **in the URL** per ADR-009, not
in code. ADR-009's suggested `connect_args={"timeout": 10}` is an asyncpg kwarg; the psycopg3
equivalent is `connect_timeout` — use that.

### Database roles and privileges

- In hosted configuration, `postgres` is migration/administration only and appears only in
  `DATABASE_URL_DIRECT`; the disposable test database may use its local `postgres` owner.
- The baseline creates `dmitri_runtime LOGIN PASSWORD NULL BYPASSRLS` with no object ownership,
  `SUPERUSER`, `CREATEDB`, `CREATEROLE`, or `REPLICATION`. `BYPASSRLS` is deliberate: this
  trusted backend connection performs system-level work while user/org authorization remains
  in later API features; the role is still unable to bypass ordinary object privileges.
- The baseline grants `CONNECT` on the application database, `USAGE` on `public`,
  `SELECT`/`INSERT`/`UPDATE` on the 14 application tables, and `USAGE`/`SELECT` on their
  sequences. It grants no `DELETE`, `TRUNCATE`, `REFERENCES`, `TRIGGER`, schema `CREATE`, or
  access to Supabase system schemas. Future migrations explicitly grant only the privileges
  required for each new object; there is no broad default-privileges grant.
- The revision contains no password. After `alembic upgrade head`, a human assigns a generated
  password through the interactive `\password dmitri_runtime` prompt, URL-encodes it for the
  pooler DSN, and changes the sealed shared Railway `DATABASE_URL` to the
  `dmitri_runtime.<project-ref>` login for both API and worker. Documentation must not show a
  password-bearing `ALTER ROLE` statement. Railway receives no administrative/direct
  credential.
- Downgrade revokes the grants and drops `dmitri_runtime` after dropping the application
  tables, leaving no feature-owned role behind. On hosted infrastructure it runs only after
  the API and worker are stopped and their pooled sessions have drained.

### Settings model (`api.core.config.Settings`)

| Field | Alias | Default | Notes |
|-------|-------|---------|-------|
| `database_url: SecretStr` | `DATABASE_URL` | **required, no default** | Credential-redacting Postgres-only value; accepts `postgres://`, `postgresql://`, `postgresql+psycopg://`, and transitional `postgresql+asyncpg://`; rejects every other dialect before engine construction |
| `kev_api_base_url`, `kev_cache_ttl_hours` | unchanged | unchanged | carried over |
| `epss_api_base_url`, `epss_cache_ttl_hours` | unchanged | unchanged | carried over |
| `nvd_api_base_url`, `nvd_cache_ttl_hours` | unchanged | unchanged | carried over |
| `nvd_api_key: SecretStr \| None` | `NVD_API_KEY` | `None` | Existing optional credential; redacted in settings and unwrapped only when constructing the NVD request header |
| `enrichment_poll_interval_seconds`, `enrichment_batch_size` | unchanged | unchanged | carried over (worker needs them) |

`DATABASE_URL_DIRECT` is **not** a Settings field: only Alembic consumes it, and env.py reads
it from `os.environ` directly (decided in refine-specs) so migration-only contexts never
need `DATABASE_URL` set. When running migrations, export it in the shell (a `.env` line is
not picked up by Alembic), run the command, then unset it. It must not exist in the Railway
API or worker environment.

Dropped: `cors_origins` and the CORS middleware — there are no browser-facing routes in this
shell; CORS returns with the first business routes. `get_settings()` stays `lru_cache`d;
`SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)` prevents
Pydantic from reproducing invalid credential-bearing inputs. `SecretStr` keeps settings
`repr`/serialization redacted; only `get_engine()` calls `get_secret_value()` at the engine
boundary. No code logs the extracted value.
`JWT_SECRET` and `AGENT_HMAC_SECRET` are not reserved as unused placeholders: neither
authentication mechanism exists in this feature, so their consuming features introduce and
validate those settings when they land.
The retained NVD client calls `get_secret_value()` only at its HTTP-header boundary. It never
stores, logs, or formats the extracted API key; query/cache behavior is otherwise unchanged.

Both process entry points validate configuration before doing work. `api.main` resolves
`get_settings()` while constructing the application, and the worker resolves it before the
poll loop. This is validation only: neither path opens a database connection or creates
schema at startup. Missing/invalid `DATABASE_URL` therefore prevents process startup; a valid
Postgres URL whose server is unavailable still permits API construction and is reported by
the health route as the specified 503.

### Session stack (`api.db.session`)

- `get_engine()` — `lru_cache`d sync engine, `create_engine(url, pool_pre_ping=True,
  connect_args={"prepare_threshold": None, "connect_timeout": 10})`. URL normalization keeps
  mapping `postgres://` / `postgresql://` / `postgresql+asyncpg://` →
  `postgresql+psycopg://`; an explicit `postgresql+psycopg://` is unchanged. The sqlite
  `_connect_args` branch is removed. Validation lives in `Settings`; normalization is repeated
  defensively at the engine seam and never converts a non-Postgres dialect. The raw
  `SecretStr` value exists only as a local used directly for engine construction and is never
  included in exceptions raised by shell code.
- `get_session()` and `reset_db_state()` — kept unchanged in signature; the engine (worker,
  enrichment, persistence) depends on `get_session()` and must keep working as-is.
- `init_db()` — **deleted**. No caller may recreate it.

### Health route contract (the only route surface)

| Method/path | OK | Failure |
|-------------|----|---------|
| `GET /api/v1/health` | `200` `{"status": "ok", "version": "0.1.0"}` after `session.execute(text("SELECT 1"))` returns — matches the contract's `HealthResponse` (`additionalProperties: false`; no extra fields) | DB error (`sqlalchemy.exc.SQLAlchemyError`) → `503` with the contract's `ErrorResponse` envelope: `{"error": {"code": "database_unreachable", "message": "Database connection failed.", "details": {}}}` |

The DB round-trip proof is behavioral: 200 is only ever returned after `SELECT 1` succeeds.
The 503 message is **static** — never echo the driver exception (unauthenticated route;
psycopg/SQLAlchemy error strings can leak host/DSN detail). `0.1.0` is the backend package
release version from `backend/pyproject.toml`: `api.main` obtains it with
`importlib.metadata.version("backend-api")`, passes the same value to FastAPI's `version`,
and returns `app.version` from health. There is no second hard-coded application version.
Sync `def` route (FastAPI threadpool — research §1), session via `Depends(get_session)`.
A static `{"status": "ok"}` without the round-trip is an acceptance failure (TRUTH.md).
Railway's configured health path is updated to the contracted `/api/v1/health`; the
uncontracted root alias is removed. FastAPI app: `title="Dmitri Backend"`,
`version=APP_VERSION` (the package-derived value above), **no lifespan hook** (there is nothing to do at startup once schema
creation is gone), no middleware, `docs_url=None`, `redoc_url=None`, and `openapi_url=None`.
The checked-in `contracts/openapi/openapi.yaml` is the only API contract; FastAPI must not
publish a second generated contract. DMI-56 intentionally implements only the contracted
GET path and body/error shapes: the contract's end-state CORS preflight, CORS headers, and
`X-Request-Id` remain assigned to the future middleware feature recorded in
`open-questions/to-define.md`; their absence is not a DMI-56 acceptance failure.
Route-surface tests assert that `/docs`, `/redoc`, `/openapi.json`, and representative
discarded business paths return 404.

### Alembic

- `alembic.ini` under `backend/`, `script_location = alembic`, no URL in the file.
- `env.py` imports `api.models.persistence` and targets `SQLModel.metadata`; reads
  `DATABASE_URL_DIRECT` from `os.environ` directly (never via `Settings` — migration-only
  contexts must not require `DATABASE_URL`), accepts the same four Postgres prefixes,
  normalizes them to `postgresql+psycopg://`, and raises a clear error naming the env var when
  unset or non-Postgres. The error never contains any part of the supplied value. Never falls
  back to `DATABASE_URL` (pooled 6543 cannot run DDL).
- `script.py.mako` adds `import sqlmodel` so autogenerated revisions referencing
  `sqlmodel.sql.sqltypes.AutoString` import cleanly.
- Baseline revision (`down_revision = None`): creates the existing 14 tables exactly as the
  model tree defines them — `scans`, `artifacts`, `devices`, `ports`, `services`, `cpes`,
  `findings`, `enrichment_jobs`, `nvd_cache`, `kev_records`, `epss_records`, `kev_cache`,
  `epss_cache`, `risk_snapshots` — including the unique constraints and indexes in
  `models/persistence.py`. For each table, the same revision executes `ENABLE ROW LEVEL
  SECURITY` and revokes all privileges on the application tables and their sequences from
  `anon` and `authenticated`; it creates no policies and does not use `FORCE ROW LEVEL
  SECURITY`. The dedicated `dmitri_runtime` role
  has `BYPASSRLS` but only the explicit object privileges listed above. These protections are
  migration DDL and do not rely on Supabase dashboard defaults. `downgrade()` drops all 14
  tables and the feature-owned runtime role. No renames, no `org_id`.
- **Portability of role DDL (one revision, every environment).** `anon` and `authenticated`
  exist only on Supabase; the revokes are wrapped in `DO` blocks guarded by
  `EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ...)` so the same revision runs unmodified
  on vanilla Postgres. The revokes execute **after** the `CREATE TABLE`s within the same
  `upgrade()` — Supabase default privileges auto-grant those roles on tables `postgres`
  creates. `dmitri_runtime` is created unconditionally; if that cluster-wide role already
  exists, migration fails clearly rather than adopting it. Because the feature therefore owns
  the role, `downgrade()` revokes its remaining database/schema grants and drops it
  unconditionally after the application tables. No environment flags or split revisions.
- `models/persistence.py` loses only `SQLModelMetadataAnchor` (its sole purpose was
  `init_db()`'s import); every column definition is untouched.

### OpenAPI contract

**One response/error patch to `contracts/openapi/openapi.yaml`** (decided in refine-specs):
the health endpoint can honestly fail, and the contract must say so. Change the existing
health `200` example's `version` from `1.0.0` to the backend release `0.1.0`, and add a named response
component `DatabaseUnavailableError` (503, `ErrorResponse` schema, example
`{"error": {"code": "database_unreachable", "message": "Database connection failed.",
"details": {}}}`) following the existing `DeviceOfflineError` pattern, and reference it as
`'503'` under `GET /api/v1/health`. **No existing shape changes** — only the stale version
example changes; `HealthResponse` stays
`{status, version}` exactly as audited in DMI-53; the implementation conforms to it.
Everything else is unchanged: this shell exposes only the health GET route; the B7 route surface
lands in later issues. Schema ownership moves to Alembic; the baseline equals the existing
tables, so no consumer-visible data change occurs. (The contracted CORS preflight and
`X-Request-Id`/CORS headers on health are end-state contract features that land with the
CORS/middleware work in later issues, not this shell; this deferral was reconfirmed during
grill-me on 2026-07-15.)

### Operational documentation and environment template

The checked-in operator path is part of the shell contract and changes in the same feature:

- `backend/.env.example` uses psycopg for local and hosted Postgres, names
  `DATABASE_URL_DIRECT`, shows `dmitri_runtime.<project-ref>` for hosted runtime traffic, and
  uses the exact settings aliases from `Settings`. It contains sample-value placeholders
  only, never a usable password, and does not advertise unused JWT/HMAC settings.
- `backend/README.md` describes migration-first startup, required Postgres configuration, the
  health-only HTTP surface, and the real API/worker commands. It removes SQLite fallback,
  discarded business routes, and the deleted smoke-test workflow from active instructions.
- `docs/cloud/supabase/SETUP.md` is updated from asyncpg/administrative runtime access to the
  decided psycopg stack, `DATABASE_URL_DIRECT`, the `dmitri_runtime` provisioning sequence,
  interactive `\password` + URL-encoding sequence, `prepare_threshold=None`, the gitignored
  local `.env` + temporary shell-export migration flow, and the
  stop/drain/downgrade/verify rollback sequence.
- `docs/cloud/railway/SETUP.md` shows the resolved start commands, `/api/v1/health`, the
  dedicated runtime-role URL, the psycopg pooler configuration, and the requirement to stop
  both services before hosted downgrade. It explicitly removes `DATABASE_URL_DIRECT` from
  Railway shared/service variables: only the sealed restricted `DATABASE_URL` is shared with
  API and worker. If `NVD_API_KEY` is configured, it is sealed as well. Its active DMI-56 setup
  does not ask operators to provision JWT/HMAC configuration before those features exist.
- `requisitos.md` stops naming `smoke_test.py` as backend verification: RF-010 points to the
  future authenticated-ingest integration test that owns that out-of-scope route, RF-013
  points to this feature's Alembic schema round-trip, and the general validation guidance
  points to `backend/tests/`.

Verification is an exact stale-guidance search across those five files: no active occurrence
of `MIGRATION_DATABASE_URL`, `postgresql+asyncpg`, SQLite fallback language,
`PLACEHOLDER_DMI56`, `/health` as the Railway probe, or the discarded business-route list.
No active `requisitos.md` verification reference may name `backend/src/api/smoke_test.py` or
the deleted backend harness. The environment template and active Railway setup must not name
`JWT_SECRET`, `AGENT_HMAC_SECRET`, "JWT secret", or "HMAC pepper" as DMI-56 configuration.
No active operator instruction may embed a password in `ALTER ROLE` SQL; it must direct the
operator to the interactive psql prompt.
Historical/conflict prose elsewhere is not rewritten by this feature.

### Style rule (future-proofing hedge, binding on new shell code)

Relationship/record access in new shell code must be explicit and eager — explicit `select()`
per collection, no reliance on implicit lazy loads — so a later async port stays cheap
(research §6, `MissingGreenlet`). The current models define no ORM relationships (FK columns
plus explicit queries), which already satisfies this; do not introduce lazy patterns. This is
a style/testing expectation only — the kept engine is **not** redesigned.

## New files and naming (mandatory)

| # | Action | Path | Purpose |
|---|--------|------|---------|
| 1 | create | `backend/alembic.ini` | Alembic config; `script_location = alembic`, no credentials |
| 2 | create | `backend/alembic/env.py` | Imports `api.models.persistence`, targets `SQLModel.metadata`, connects via `DATABASE_URL_DIRECT` only |
| 3 | create | `backend/alembic/script.py.mako` | Revision template with `import sqlmodel` |
| 4 | create | `backend/alembic/versions/<rev>_baseline.py` | Baseline migration: the 14 existing table shapes as-is; RLS and closed Data API grants; dedicated least-privilege runtime role and grants; reversible |
| 5 | create/modify | `backend/tests/test_migrations.py` | Staged ownership: Task 1 creates non-DB Alembic config/template/dependency coverage; Task 2 may add baseline-focused coverage; Task 3 adds the upgrade-head / downgrade-base and privilege round-trip against `DATABASE_URL_TEST` |
| 6 | create | `backend/tests/test_health.py` | Health 200 with live round-trip; 503 when DB unreachable; health-only route surface and disabled generated docs/OpenAPI |
| 7 | create | `backend/tests/test_settings.py` | Settings-from-env, SecretStr/error redaction, and fail-fast API entry point: required `DATABASE_URL`, carried fields, absence of unused auth fields, accepted Postgres prefixes, rejection of SQLite/other dialects without DB connection |
| 8 | create | `backend/tests/test_db_session.py` | Engine construction: all accepted prefixes normalize to psycopg, non-Postgres never reaches engine construction, `pool_pre_ping`, `prepare_threshold=None`; `init_db` gone |
| 9 | create | `backend/tests/test_worker_startup.py` | Worker settings fail-fast; `run_worker_once()` returns 0 against a migrated, empty DB; `worker_main.main` wiring without claiming cooperative shutdown coverage |
| 10 | modify | `backend/src/api/core/config.py` | New `Settings` per table above; SQLite default and `cors_origins` removed |
| 11 | modify | `backend/src/api/db/session.py` | Pooler-safe sync engine; delete `init_db()` and the sqlite branch; keep `get_session`/`reset_db_state` |
| 12 | modify | `backend/src/api/main.py` | Full replacement: minimal app + health route; all business routes and `_serialize_*` helpers deleted (readable in git history as reference) |
| 13 | modify | `backend/src/api/models/persistence.py` | Remove `SQLModelMetadataAnchor` only |
| 14 | modify | `backend/pyproject.toml` | Add `alembic>=1.13`; **drop `asyncpg`**; keep `psycopg[binary]`; remove `backend-smoke-test`; keep `backend-worker` |
| 15 | modify | `backend/uv.lock` | Regenerated by `uv lock` after 14 |
| 16 | modify | `backend/tests/conftest.py` | Postgres test harness and `SET ROLE dmitri_runtime` restricted-session fixture (below); sqlite file harness removed |
| 17 | modify | `backend/tests/test_ingest_scan.py` | Engine-intact tests: call `persist_scan(session, scan)` directly; drop the two route-based tests (`test_api_v1_scans_endpoint_accepts_payload`, `test_api_exposes_finding_enrichment_and_risk_summary`) whose routes are discarded; keep worker + cache tests |
| 18 | delete | `backend/src/api/routers/__init__.py` (and the `routers/` dir) | Empty placeholder on B8's discard list; nothing imports it |
| 19 | verify (no change) | `backend/src/api/worker_main.py` | Already free of `init_db`; must start against the new settings/session stack — covered by test 9 |
| 20 | verify (no change) | `backend/src/api/services/worker.py` | Kept poll loop; consumes `get_settings`/`get_session` unchanged |
| 21 | delete | `backend/src/api/smoke_test.py` | B8-discarded standalone harness: depends on absent Compose services and business routes removed by this shell; replacement coverage lives in migration/health/worker/engine tests |
| 22 | modify | `contracts/openapi/openapi.yaml` | Align the health example to backend release `0.1.0`; add `DatabaseUnavailableError` 503 response component + its reference on `GET /api/v1/health`; no existing schema shape touched |
| 23 | modify | `backend/railway.api.toml` | Remove `PLACEHOLDER_DMI56`, retain the real Uvicorn entry point and bind, and change `healthcheckPath` to `/api/v1/health` |
| 24 | modify | `backend/railway.worker.toml` | Remove `PLACEHOLDER_DMI56`; retain `python -m api.worker_main` as the separately runnable worker entry point |
| 25 | modify | `backend/.env.example` | Replace SQLite/asyncpg and obsolete migration-variable examples with the psycopg, `DATABASE_URL_DIRECT`, dedicated-runtime-role contract |
| 26 | modify | `backend/README.md` | Document migration-first Postgres startup, health-only shell, and real API/worker commands; remove discarded-shell instructions |
| 27 | modify | `docs/cloud/supabase/SETUP.md` | Sync Supabase setup to psycopg, `DATABASE_URL_DIRECT`, `dmitri_runtime`, password provisioning, and current pooler args |
| 28 | modify | `docs/cloud/railway/SETUP.md` | Sync Railway setup to resolved commands, canonical health path, dedicated runtime URL, and psycopg pooler args |
| 29 | modify | `requisitos.md` | Replace deleted `smoke_test.py` verification references: defer RF-010 to its ingest integration owner, bind RF-013 to Alembic schema tests, and point general backend verification to `backend/tests/` |
| 30 | modify | `.github/workflows/ci.yml` | Add backend lint/test job with disposable Postgres 17, `DATABASE_URL_TEST`, frozen uv sync from `backend/uv.lock`, migration-backed pytest, and ruff; database-test skips fail the job |
| 31 | modify | `backend/src/api/services/nvd.py` | Unwrap the optional `NVD_API_KEY` `SecretStr` only while constructing the existing outbound request header; no client behavior change |
| 32 | modify | `contracts/examples/scan_result.example.json` | Task 3 only: replace legacy `scan_mode` with schema-valid `target_mode` and `scan_profile` so the retained engine tests exercise the existing contract; no scenario or schema change |

Implementers must not create files outside this table. Entry-point rule: items 10–11 are
consumed by **both** `api.main` and `api.worker_main` — tests 6 and 9 are the proof for each.

## Constraints

- No new hosted infrastructure or secrets by agents. The disposable Postgres 17 service in CI
  is required test infrastructure, not a hosted environment. `HUMAN_INFRA_REQUIRED`: hosted
  `nspi` migration apply, runtime-role password assignment/Railway secret update, and any local
  test Postgres are human-provided.
- Scope fence (binding): no business routes, no auth logic or RLS policies, no command-channel
  tables, no `persist_scan` rework, and no Railway/AWS deploy-config changes beyond the two
  placeholder/health-path edits in items 23–24 plus the human-approved (2026-07-16) setting
  of the `worker` service's `rootDirectory` to `/backend` (System context amendment). Documentation edits are limited to the five
  operator/traceability files in items 25–29 and the decisions enumerated above. Item 32 is a
  compatibility-fixture correction only: replace `scan_mode` with valid `target_mode` and
  `scan_profile` values; do not change `ScanResult`, add defaults, or alter the example's scan
  scenario.
- No resurrection: no SQLite paths, no `create_all`/schema-on-boot, no auth-less business
  routes, and no replacement business-route smoke harness.
- Secrets only in env; `.env` stays gitignored; no credentials in `alembic.ini` or tests.
- Hosted administrative credentials are operator-only: `DATABASE_URL_DIRECT` may be exported
  transiently from the gitignored local `.env` for Alembic, but may not be configured on,
  referenced by, or exposed to either long-running Railway service.
- Destructive DB tests run only against a database whose parsed and server-reported name is
  exactly `dmitri_test`; a differently named target fails closed before schema/role mutation.

## Testing expectations

Quality gates are staged by exact file ownership:

- Task 1: `uv run pytest tests/test_migrations.py`, `uv run ruff check .`,
  `uv sync --frozen --extra dev`, and `uv lock --check` inside `backend/`. Task 1 owns only
  the non-database Alembic configuration/template/dependency coverage in that test module.
- Task 2: `uv run pytest tests/test_migrations.py` and `uv run ruff check .` inside
  `backend/`. Task 2 may add baseline-focused coverage to the same module but does not own the
  ingest compatibility surface.
- Task 3: first mandatory complete-backend gate. It owns the Postgres harness, the database
  expansion of `test_migrations.py`, the retained ingest tests, and the stale shared example.
  `uv run pytest` and `uv run ruff check .` must pass inside `backend/`; with
  `DATABASE_URL_TEST`, the database-backed run has no database-test skips.
- Task 4 changes only the checked-in OpenAPI document and runs its named hardware-agent
  contract test plus lint applicable to changed files; it does not use the unrelated backend
  suite as its task gate.
- Every backend-changing task after Task 3 runs the complete backend pytest suite and Ruff and
  must preserve the green result. Local DB-touching tests may skip only where that task's
  criterion explicitly allows it.
- Feature approval additionally requires the Task 10 CI backend job: Postgres 17 available,
  `DATABASE_URL_TEST` set, the complete backend suite passing with **zero database-test
  skips**, frozen sync, and Ruff passing. A focused or locally skipped run is never sufficient
  feature-approval evidence.

The five known pre-Task-3 ingest failures are tracked compatibility debt, not an allowed final
state. Tasks 1 and 2 may not mask, deselect, or expand them. Task 3 must correct the shared
example and restore the complete suite before Task 5 or any later backend-changing task starts.

**Test DB mechanism.** The current `conftest.py` forces a sqlite file via `DATABASE_URL`;
that harness goes away with the SQLite path. Replacement contract in `conftest.py`:

- `DATABASE_URL_TEST` (direct connection to a disposable local Postgres) selects the test DB.
  Reference local setup: `docker run -d --name dmitri-test-pg -p 5432:5432 -e
  POSTGRES_PASSWORD=test -e POSTGRES_DB=dmitri_test postgres:17`, then
  `DATABASE_URL_TEST=postgresql+psycopg://postgres:test@localhost:5432/dmitri_test`.
  When unset, every DB-touching test is skipped via a shared fixture/marker
  (`pytest.skip("DATABASE_URL_TEST not set")`) — the suite must still pass green without it.
  Before test-module collection, conftest always exports a valid runtime URL: the test URL
  when present, otherwise `postgresql+psycopg://u:p@127.0.0.1:1/x`. This lets the fail-fast
  API module construct without opening a connection. Missing-config tests explicitly delete
  that value and clear settings/module state; it never weakens production validation.
- When set: conftest exports it as **both** `DATABASE_URL` and `DATABASE_URL_DIRECT` (the
  test DB is a direct connection, and env.py refuses to fall back to `DATABASE_URL`, so the
  programmatic `alembic upgrade head` below needs the direct var too), creates `anon` and
  `authenticated` as bare `NOLOGIN` roles if missing — so the migration's guarded revoke
  branch executes locally and the `test_migrations.py` privilege assertions test real
  behavior instead of vacuously passing on absent roles — calls
  `get_engine().dispose()` before every environment switch, then calls `reset_db_state()`, runs
  `alembic upgrade head` once per session (programmatically via `alembic.command.upgrade`
  with `alembic.config.Config(backend/alembic.ini)`), and truncates all
  `SQLModel.metadata.sorted_tables` between tests. Using the migration — not
  `create_all` — to build the test schema is deliberate: it proves the baseline matches the
  model tree on every run.
- Before any migration, truncation, or role DDL, conftest requires both the parsed URL
  database and `SELECT current_database()` to equal exactly `dmitri_test`; mismatch aborts
  the suite rather than skipping. The session fixture records whether it created each
  Supabase stand-in role. At teardown it downgrades to base, then drops only the `anon` and
  `authenticated` roles it created; pre-existing Supabase-style roles are never adopted for
  cleanup or dropped. The disposable CI service is destroyed normally after the job.
- Conftest exposes separate administrative and runtime fixtures. Administrative access is
  limited to migration setup/rollback, catalog assertions, role switching, and truncation.
  The runtime fixture opens an administrative test connection, executes
  `SET ROLE dmitri_runtime`, asserts `current_user = 'dmitri_runtime'`, and yields a Session
  bound to that connection; it resets/closes the connection afterward. No runtime-role
  password is introduced. Health overrides `get_session` with this fixture, worker startup
  monkeypatches its `get_session` seam, and kept-engine tests use the restricted Session
  directly.
- CI provisions Postgres 17 as a job service, points `DATABASE_URL_TEST` at it, installs uv,
  creates/selects its database as `dmitri_test`, runs `uv sync --frozen --extra dev` from
  `backend/`, then runs pytest plus ruff through uv.
  The frozen sync makes `backend/uv.lock` authoritative. The workflow records/checks the
  pytest result so any database-test skip fails the backend job; connection or migration
  failures fail normally. This is the authoritative complete-suite run.

**Per-area:**

- `test_migrations.py` — from head: `downgrade base` leaves no tables except
  `alembic_version`; `upgrade head` recreates all 14 tables (assert via `sqlalchemy.inspect`
  table names), asserts `relrowsecurity` is true for each application table, and asserts both
  `anon` and `authenticated` have no application-table or sequence privileges. It also
  asserts `dmitri_runtime` has
  `LOGIN` + `BYPASSRLS`, lacks administrative role attributes and object ownership, has only
  the enumerated table/sequence/schema privileges, rejects a pre-existing-role collision, and
  disappears on downgrade. It ends at head so ordering with other DB tests is safe. Skips
  without `DATABASE_URL_TEST`.
- Under `SET ROLE dmitri_runtime`, privilege tests prove required SELECT/INSERT/UPDATE and
  sequence-backed inserts succeed, while schema/object creation, table alteration,
  DELETE/TRUNCATE, and `SET ROLE anon` / `SET ROLE authenticated` fail. Catalog inspection is
  supporting evidence, not the sole privilege proof.
- `test_migrations.py` also covers Alembic URL handling without a database round trip where
  possible: all four accepted Postgres prefixes normalize to psycopg; unset and non-Postgres
  `DATABASE_URL_DIRECT` fail with a static error naming that variable but containing neither
  the password nor complete supplied URL; no fallback to `DATABASE_URL` exists.
- `test_health.py` — (a) `TestClient` + the restricted runtime Session override:
  `GET /api/v1/health` returns 200
  with `{"status": "ok", "version": app.version}` and no other keys; `app.version` equals
  `importlib.metadata.version("backend-api")` and is `0.1.0` for this release (needs
  `DATABASE_URL_TEST`); (b) failure case needs **no** Postgres: point the engine at a closed
  localhost port (`postgresql+psycopg://u:p@127.0.0.1:1/x`) via env, disposing the prior
  engine before `reset_db_state()`, and assert 503 with
  `error.code == "database_unreachable"` and a body containing no raw exception text. Restore
  the previous env with the same dispose/reset sequence. This is the "health degrades
  honestly" acceptance row and must never be skipped.
  (c) With the app loaded, `/`, `/docs`, `/redoc`, `/openapi.json`, and representative removed
  business paths return 404; registered application routes contain only the canonical GET
  health route (framework internals are disabled by the explicit FastAPI constructor
  arguments). `OPTIONS /api/v1/health` is not implemented by this feature and returns 405;
  CORS and `X-Request-Id` assertions belong to the deferred middleware feature.
- `test_settings.py` — no DB: missing `DATABASE_URL` raises `ValidationError`; carried fields
  read from env with correct aliases; `jwt_secret` and `agent_hmac_secret` are absent; each
  accepted Postgres prefix passes; SQLite and representative other dialects raise a clear
  `ValidationError`. API construction
  with missing/invalid config fails before `create_engine` is called; a syntactically valid
  unreachable Postgres URL permits app construction without a connection attempt. Settings
  representation/serialization and every invalid-input error redact the full URL, database
  password, and `NVD_API_KEY`. A focused NVD-client test proves the extracted key reaches the
  outbound `apiKey` header while no settings/client representation exposes it.
- `test_db_session.py` — no DB round-trip: all accepted URL forms produce engine drivername
  `postgresql+psycopg`; `pool_pre_ping` is on;
  `connect_args["prepare_threshold"] is None`; non-Postgres input is rejected before
  `create_engine`; `api.db.session` has no `init_db` attribute.
- `test_worker_startup.py` — migrated empty DB through the restricted runtime Session seam:
  `run_worker_once()` returns 0;
  `worker_main.main` is importable and wired to `run_worker_loop` (entry-point coverage for
  the second consumer of the stack). Missing/invalid settings fail before the poll loop or
  engine construction. This test does not claim graceful process shutdown or in-flight job
  recovery. DB polling coverage skips without `DATABASE_URL_TEST`; fail-fast coverage never
  skips.
- `test_ingest_scan.py` (engine intact) — mirror its existing structure, minus routes:
  `persist_scan` + worker enrichment tests keep passing on Postgres through the restricted
  runtime Session unchanged — the TRUTH.md "engine intact" and "runtime role constrained"
  rows. In the same Task 3 change, `contracts/examples/scan_result.example.json` replaces
  legacy `scan_mode` with `target_mode: "subnet"` and `scan_profile: "lan"`; the resulting
  payload must validate through the existing `ScanResult` without schema defaults or test
  monkeypatching.
- Operator-guidance verification — search the five files in items 25–29 for the stale tokens,
  deleted-harness references, and discarded-shell claims listed in the
  operational-documentation section; all must be absent from active guidance.
- Removed smoke harness verification — `api.smoke_test` is not importable,
  `backend/src/api/smoke_test.py` is absent, and `backend-smoke-test` is absent from
  `[project.scripts]`; the targeted migration/health/worker/engine tests are its replacement.

Mirror the existing style of `backend/tests/test_ingest_scan.py` (plain functions,
monkeypatched clients); no comments/docstrings in new code per repo convention.

## Conflicts noted (docs vs decided constraints)

1. **ADR-009 asyncpg section** — superseded by the human-approved sync-everywhere decision;
   ADR left unedited by instruction.
2. **ADR-009 `connect_args={"timeout": 10}`** — asyncpg-specific kwarg; psycopg3 uses
   `connect_timeout`. This doc specifies the psycopg3 form.
3. **B8 "only the KEV/EPSS/NVD URL+TTL fields carry over"** vs the decided settings list,
   which also carries the enrichment poll/batch fields — the decided list wins (the kept
   worker loop reads them).
4. **Existing sqlite test harness** — cannot be "matched" as instructed because the SQLite
   path itself is discarded; replaced by the `DATABASE_URL_TEST` + skip mechanism above.
5. **Checked-in operator/traceability guidance** — currently describes asyncpg,
   `MIGRATION_DATABASE_URL`, the `postgres` runtime login, SQLite fallback, placeholder Railway
   commands, discarded routes, and the deleted smoke harness as verification. Items 25–29
   replace those active instructions with the decisions in this spec.
