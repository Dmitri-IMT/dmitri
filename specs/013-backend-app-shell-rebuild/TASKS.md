# Tasks — Backend app shell rebuild (DMI-56, spec 013)

10 tasks. **Execution resumed after approval of the Task 1 structural re-evaluation.**

Parallel tracks: database/migration foundation (#1–#3), checked-in HTTP contract (#4),
runtime API and configuration (#5–#7), then deployment/operator alignment (#8–#9) and
the authoritative CI gate (#10).

## CLI tooling

- **Supabase CLI (local stack)** provides the Postgres 17 test database for the
  DB-backed criteria in tasks #2–#7. `supabase start` (config in `supabase/config.toml`,
  `major_version = 17`) exposes an admin connection at
  `postgresql://postgres:postgres@127.0.0.1:54322/postgres`. Create the test database
  once (`CREATE DATABASE dmitri_test`) and export
  `DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:54322/dmitri_test`.
  The local cluster ships real `anon`/`authenticated` roles, so it also rehearses the
  baseline migration's guarded revokes and Task 9's hosted Supabase guidance.
  Alembic is the sole schema owner: never use `supabase db push`, `supabase db reset`,
  or `supabase migration` against this schema.
- **Railway CLI** verifies tasks #8–#9. The repo is linked to project `Dmitri`,
  environment `nspi` (services `api`, `worker`). Deploy with
  `railway up --detach --service <api|worker>`, confirm terminal status with
  `railway deployment list --json`, inspect with `railway logs --service <name>`, and
  manage variables with `railway variable set` / `railway variable list --json`.
  `DATABASE_URL_DIRECT` must never be set on any Railway service.
- **CI (Task #10) uses neither CLI**: it provisions its own disposable Postgres 17
  service container exactly as specified.

---

## Task 1: Install and configure the Alembic migration environment
- **Description**: Establish the credential-free Alembic environment and backend dependency set per `ARCHITECTURE.md` §§ Alembic and New files and naming. Alembic must consume only `DATABASE_URL_DIRECT`, normalize every accepted Postgres prefix to psycopg, and never fall back to the pooled runtime target; remove asyncpg and the obsolete smoke-test console command while retaining the worker command and release version.
- **Dependencies**: —
- **Target Files**: [`backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/pyproject.toml`, `backend/uv.lock`, `backend/tests/test_migrations.py`]
- **Success Criteria**:
  - `alembic.ini` uses `script_location = alembic` and contains no connection URL or credential; the revision template imports `sqlmodel`.
  - `env.py` targets `SQLModel.metadata`, imports the persistence models, requires `DATABASE_URL_DIRECT`, accepts the four specified Postgres prefixes, normalizes them to psycopg, and never reads or falls back to `DATABASE_URL`.
  - Missing or non-Postgres migration configuration produces a static, redacted error naming `DATABASE_URL_DIRECT` without reproducing a password or complete supplied URL.
  - `alembic>=1.13` is installed, `asyncpg` and `backend-smoke-test` are absent, `psycopg[binary]` and `backend-worker` remain, the package version remains `0.1.0`, and `uv.lock` is regenerated and frozen-sync compatible.
  - Task 1 owns only the non-database Alembic configuration/template/dependency coverage in `test_migrations.py`; it does not own `test_ingest_scan.py` or the shared scan example.
  - Inside `backend/`, `uv run pytest tests/test_migrations.py`, `uv run ruff check .`, `uv sync --frozen --extra dev`, and `uv lock --check` pass. The complete backend suite becomes a mandatory task gate at Task 3, which owns the known ingest compatibility failure.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Create the reversible, access-closed baseline migration
- **Description**: Implement the single baseline revision per `ARCHITECTURE.md` §§ Database roles and privileges and Alembic. Reproduce the existing 14-table model shape without renames or `org_id`, make migration DDL the sole schema/security owner, and provision the feature-owned restricted runtime role without embedding a password.
- **Dependencies**: Task 1
- **Target Files**: [`backend/alembic/versions/<rev>_baseline.py`, `backend/tests/test_migrations.py`]
- **Success Criteria**:
  - Upgrade creates exactly `scans`, `artifacts`, `devices`, `ports`, `services`, `cpes`, `findings`, `enrichment_jobs`, `nvd_cache`, `kev_records`, `epss_records`, `kev_cache`, `epss_cache`, and `risk_snapshots`, including the model tree's existing constraints and indexes.
  - Every application table has RLS enabled without `FORCE ROW LEVEL SECURITY` or policies, and guarded revokes remove all table and sequence privileges from existing `anon` and `authenticated` roles.
  - Upgrade creates `dmitri_runtime LOGIN PASSWORD NULL BYPASSRLS`, fails rather than adopts a pre-existing role, grants only CONNECT, public-schema USAGE, table SELECT/INSERT/UPDATE, and sequence USAGE/SELECT, and grants no ownership or administrative/destructive capability.
  - Downgrade drops all 14 application tables, revokes remaining database/schema grants, and drops `dmitri_runtime`; no password, environment branch, or hosted credential appears in the revision.
  - Task 2 may add baseline-focused coverage to `test_migrations.py`; the database-backed round-trip/security expansion remains Task 3-owned.
  - `uv run pytest tests/test_migrations.py` and `uv run ruff check .` pass inside `backend/`. Task 2 may not mask, deselect, or expand the five known Task 3-owned ingest failures.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: Replace the SQLite harness with guarded Postgres migration and engine coverage
- **Description**: Build the Postgres 17 test harness and migration/security coverage per `ARCHITECTURE.md` § Testing expectations, and convert the retained engine tests away from deleted business routes and `init_db()`. This task proves the baseline, the constrained runtime role, destructive-test isolation, and unchanged enrichment/scoring behavior described in `TRUTH.md`. The harness must run against any Postgres 17 `dmitri_test` database — both the Supabase CLI local stack (see CLI tooling above, where real `anon`/`authenticated` roles pre-exist) and a bare Postgres 17 container (CI, where they don't).
- **Dependencies**: Task 2
- **Target Files**: [`backend/tests/conftest.py`, `backend/tests/test_migrations.py`, `backend/tests/test_ingest_scan.py`, `contracts/examples/scan_result.example.json`]
- **Success Criteria**:
  - Without `DATABASE_URL_TEST`, DB-touching tests skip through the shared mechanism while non-DB tests run; with it, both the URL database and `current_database()` must equal `dmitri_test` before any migration, role DDL, truncation, or cleanup.
  - The session harness uses Alembic upgrade/downgrade rather than `create_all`, creates `anon`/`authenticated` stand-ins only when the cluster lacks them and later drops only the stand-ins it created (pre-existing roles on a Supabase-local cluster are reused and never dropped), truncates between tests, and exposes separate administrative and `SET ROLE dmitri_runtime` sessions.
  - Migration tests prove the complete up/down round trip, all 14 tables and RLS settings, closed `anon`/`authenticated` access, exact runtime-role attributes and grants, pre-existing-role collision behavior, and role removal on downgrade.
  - Behavioral privilege tests under `dmitri_runtime` allow required reads/writes and sequence-backed inserts while rejecting schema/object creation, alteration, DELETE/TRUNCATE, and assumption of Supabase API roles.
  - Alembic URL tests cover all accepted prefixes, psycopg normalization, no runtime-URL fallback, and redacted unset/invalid-target errors without a database round trip.
  - `test_ingest_scan.py` calls `persist_scan(session, scan)` directly through the restricted fixture, removes only the two discarded route tests, and keeps persistence, worker, cache, enrichment, and scoring behavior covered on Postgres.
  - `test_ingest_scan.py` no longer imports `api.main` or `init_db`; its surviving tests exercise `persist_scan` and the worker without calling any route handler, so the Task 5 shell replacement and Task 6 `init_db` deletion cannot break this file.
  - The shared scan example replaces legacy `scan_mode` with `target_mode: "subnet"` and `scan_profile: "lan"`, validates through the existing `ScanResult`, and otherwise preserves its scenario; no schema default, validation monkeypatch, or unrelated contract change is introduced.
  - `uv run pytest` and `uv run ruff check .` pass inside `backend/`; a complete database-backed run has no database-test skips.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: Align the checked-in health contract with the shell release
- **Description**: Apply only the health response patch specified by `ARCHITECTURE.md` § OpenAPI contract. The checked-in contract remains authoritative while CORS preflight and request-id/CORS headers remain deferred as recorded in `open-questions/to-define.md`.
- **Dependencies**: —
- **Target Files**: [`contracts/openapi/openapi.yaml`]
- **Success Criteria**:
  - The existing health 200 example uses backend release `0.1.0` while `HealthResponse` remains exactly `{status, version}` with no schema-shape change.
  - A named `DatabaseUnavailableError` response follows the existing error-component pattern and contains the specified static `database_unreachable` envelope.
  - `GET /api/v1/health` references the new 503 component; no other paths, schemas, CORS behavior, or headers change.
  - `hardware-agent/tests/test_contract_models.py` (the checked-in contract's validation test) passes against the patched `openapi.yaml`; because this task changes no backend file, the unrelated backend suite is not its task gate.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 5: Replace the discarded web shell with the database-backed health application
- **Description**: Fully replace the monolithic application with the minimal FastAPI shell per `ARCHITECTURE.md` § Health route contract and the `TRUTH.md` boot, health, no-schema-on-boot, health-only-surface, and obsolete-shell criteria. Delete the empty router placeholder and standalone scorer smoke harness; do not introduce business routes, middleware, generated documentation, or startup schema work.
- **Dependencies**: Tasks 3, 4
- **Target Files**: [`backend/src/api/main.py`, `backend/tests/test_health.py`, `backend/src/api/routers/__init__.py`, `backend/src/api/smoke_test.py`]
- **Success Criteria**:
  - App construction resolves settings but opens no DB connection, creates no schema, has no lifespan hook or middleware, disables `/docs`, `/redoc`, and `/openapi.json`, and derives both `app.version` and the health version from installed `backend-api` metadata (`0.1.0`).
  - `GET /api/v1/health` returns exactly `{"status": "ok", "version": app.version}` only after `SELECT 1` succeeds through `Depends(get_session)`.
  - SQLAlchemy database failure returns 503 with the static contracted envelope and exposes no raw exception, connection target, or credential detail; this failure test never skips.
  - Registered/reachable application routes contain only canonical GET health; `/`, generated-doc paths, representative discarded business paths return 404, and the deliberately deferred health OPTIONS request returns 405.
  - The routers placeholder directory and `api.smoke_test` source are absent, `api.smoke_test` is not importable, and no replacement business-route smoke harness is introduced.
  - New shell code follows `ARCHITECTURE.md` § Style rule: record access uses explicit `select()` statements, with no implicit lazy-load patterns introduced.
  - `uv run pytest` and `uv run ruff check .` pass inside `backend/`; database-backed health success uses the restricted runtime fixture.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6: Cut runtime configuration and sessions over to env-only psycopg
- **Description**: Implement the settings, session, metadata-anchor cleanup, and NVD secret boundary specified by `ARCHITECTURE.md` §§ Settings model and Session stack. This is the runtime cutover for both process entry points: no SQLite/default database, async session, schema-on-boot, unused auth setting, or secret-bearing representation may remain.
- **Dependencies**: Task 5
- **Target Files**: [`backend/src/api/core/config.py`, `backend/src/api/db/session.py`, `backend/src/api/models/persistence.py`, `backend/src/api/services/nvd.py`, `backend/tests/test_settings.py`, `backend/tests/test_db_session.py`]
- **Success Criteria**:
  - `DATABASE_URL` is a required `SecretStr`; only the four specified Postgres prefixes validate, carried enrichment settings keep their aliases/defaults, `NVD_API_KEY` is optional `SecretStr`, and CORS/JWT/HMAC settings are absent.
  - Settings use `hide_input_in_errors=True`; representations, serialization, invalid-input errors, health/startup errors, and logs reveal neither complete URLs/passwords nor the NVD key.
  - The NVD client unwraps the optional key only when constructing the outbound `apiKey` header, with query/cache behavior otherwise unchanged and focused test coverage proving both delivery and secrecy.
  - `get_engine()` defensively normalizes accepted URLs to `postgresql+psycopg`, uses `pool_pre_ping=True` and `prepare_threshold=None`/`connect_timeout=10`, and rejects non-Postgres input before engine construction.
  - `get_session()` and `reset_db_state()` retain their signatures; `init_db`, the SQLite branch, `create_all`, and `SQLModelMetadataAnchor` are absent.
  - New shell code follows `ARCHITECTURE.md` § Style rule: record access uses explicit `select()` statements, with no implicit lazy-load patterns or ORM relationships introduced.
  - Settings and API construction fail before engine construction for missing/invalid configuration, while a syntactically valid unreachable Postgres URL constructs the app without connecting.
  - `uv run pytest` and `uv run ruff check .` pass inside `backend/` under the testing conditions available for this task.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 7: Verify the worker entry point on the new settings and session stack
- **Description**: Add the second-entry-point coverage mandated by `ARCHITECTURE.md` for `api.worker_main` → `api.services.worker`. Verify the existing worker code without redesigning its loop or claiming the deferred shutdown/recovery behavior in `open-questions/to-define.md`.
- **Dependencies**: Task 6
- **Target Files**: [`backend/tests/test_worker_startup.py`, `backend/src/api/worker_main.py`, `backend/src/api/services/worker.py`]
- **Success Criteria**:
  - Missing or invalid runtime configuration prevents worker startup before the poll loop or engine construction; startup validation does not open a connection or create schema.
  - Against the migrated empty database through the restricted-session seam, `run_worker_once()` returns 0 without error.
  - `worker_main.main` is importable and wired to the existing `run_worker_loop`; the worker remains a separately runnable process and neither verify-only source file changes unless the tests expose a spec violation.
  - Coverage makes no assertion about cooperative SIGTERM shutdown or interrupted-job recovery, which remain deferred.
  - `uv run pytest` and `uv run ruff check .` pass inside `backend/`; the database-backed worker case has no skip when `DATABASE_URL_TEST` is provided.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 8: Wire the existing Railway services to the real shell entry points
- **Description**: Resolve only the two existing Railway service definitions as allowed by `ARCHITECTURE.md` §§ System context and Constraints. The API must use its real Uvicorn entry point and contracted probe, while the worker retains its separate real process command; do not add infrastructure or administrative credentials. Verify the wiring with the Railway CLI against the linked `Dmitri`/`nspi` services per the CLI tooling section.
- **Dependencies**: Task 7
- **Target Files**: [`backend/railway.api.toml`, `backend/railway.worker.toml`]
- **Success Criteria**:
  - Both `PLACEHOLDER_DMI56` markers are absent.
  - The API starts through the real Uvicorn `api.main` application with its existing bind and Railway probes `/api/v1/health`.
  - The worker starts with `python -m api.worker_main` and remains independently runnable.
  - Neither service definition references `DATABASE_URL_DIRECT`, embeds credentials, adds new hosted infrastructure, or expands deployment scope.
  - Railway CLI verification: `railway up --detach --service <api|worker>` is run for each service and `railway deployment list --json` is polled to a terminal state; the API deployment's health probe targets `/api/v1/health` and each service starts through its real command per `railway logs`. A deployment failure is acceptable only when `railway logs` traces it to runtime configuration that Task 9 provisions, not to the service definitions.
  - Backend tests and lint pass after the wiring change.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 9: Align the operator environment and setup guidance with the shipped shell
- **Description**: Update the five operator/traceability artifacts required by `ARCHITECTURE.md` § Operational documentation and environment template and the `TRUTH.md` operator-guidance criteria. Document migration-first psycopg setup, restricted runtime access, interactive password provisioning, quiescent hosted rollback, the health-only surface, and the real service commands without reviving deferred functionality. Documented command flows must be executed, not transcribed from memory: apply the Railway variables with the Railway CLI and rehearse the Supabase migration/rollback sequence against the local `supabase start` stack per the CLI tooling section.
- **Dependencies**: Task 8
- **Target Files**: [`backend/.env.example`, `backend/README.md`, `docs/cloud/supabase/SETUP.md`, `docs/cloud/railway/SETUP.md`, `requisitos.md`]
- **Success Criteria**:
  - The environment template and backend README use the exact shipped settings, psycopg URLs, `DATABASE_URL_DIRECT` migration flow, dedicated runtime-role contract, migration-first startup, health-only route, and real API/worker commands.
  - Supabase guidance covers the PG17/BYPASSRLS pre-flight, absent-role check, `alembic upgrade head`, interactive `\password dmitri_runtime`, URL encoding, sealed runtime URL, and stop/drain/downgrade/verify rollback sequence without a password-bearing SQL/history example.
  - Railway guidance gives only the restricted pooled `DATABASE_URL` to API/worker, excludes and forbids `DATABASE_URL_DIRECT`, seals an optional NVD key, uses the real commands and `/api/v1/health`, and requires both services stopped before rollback.
  - `requisitos.md` defers RF-010 to the authenticated-ingest owner, binds RF-013 to Alembic round-trip tests, and points general backend verification to `backend/tests/` rather than the deleted smoke harness.
  - Active guidance contains none of the stale migration-variable, asyncpg, SQLite-fallback, placeholder, root-health-probe, discarded-route, deleted-harness, premature JWT/HMAC, or password-bearing `ALTER ROLE` instructions enumerated in `ARCHITECTURE.md`.
  - CLI execution evidence: the pooled `DATABASE_URL` (and optional sealed NVD key) is set on both services with `railway variable set` and confirmed with `railway variable list --json` showing no `DATABASE_URL_DIRECT`; the documented Supabase migration and stop/drain/downgrade/verify rollback sequence has been rehearsed once against the local `supabase start` stack.
  - Documentation checks, backend tests, and backend lint pass.
- **Status**: COMPLETED
- **Review Rejections**: 0 (review waived by operator — documentation-only task)

## Task 10: Add the authoritative Postgres-backed backend CI gate
- **Description**: Add the backend job specified by `ARCHITECTURE.md` § Testing expectations and the `TRUTH.md` backend-CI and quality-gate criteria. CI must make the complete Postgres-backed result authoritative rather than accepting a locally skipped database suite.
- **Dependencies**: Task 7
- **Target Files**: [`.github/workflows/ci.yml`]
- **Success Criteria**:
  - The job provisions disposable Postgres 17 with a database named exactly `dmitri_test`, exports `DATABASE_URL_TEST`, installs uv, and runs `uv sync --frozen --extra dev` from `backend/`.
  - CI exercises Alembic up/down and the full backend pytest suite, fails on any database-test skip, and then runs `uv run ruff check .`.
  - The job uses the checked-in `backend/uv.lock`, carries no hosted/admin secret, and a connection, migration, test, skip-policy, frozen-sync, or lint failure fails the job.
  - The complete CI job passes and supplies the feature-level approval evidence required by `TRUTH.md`; local `uv run pytest` and `uv run ruff check .` also pass under their documented conditions.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Dependency graph

```text
#1 ──→ #2 ──→ #3 ──┐
                    ├──→ #5 ──→ #6 ──→ #7 ──┬──→ #8 ──→ #9
#4 ─────────────────┘                         └──→ #10
```

## Status

Human gate: Task 1 remains `BLOCKED_STRUCTURAL` with four rejections until the operator
explicitly approves `STRUCTURAL_REEVAL.md`. On approval only, the orchestrator resets Task 1
to `IN_PROGRESS`, resets `Review Rejections` to 0, and spawns a fresh Task 1 coder from step 1
under the amended focused gate. No rejected coder is resumed. Task 3 is the first owner allowed
to change the stale scan example and the first task required to restore the complete backend
suite to green.

| # | Task | Status |
|---|------|--------|
| 1 | Install and configure the Alembic migration environment | COMPLETED |
| 2 | Create the reversible, access-closed baseline migration | COMPLETED |
| 3 | Replace the SQLite harness with guarded Postgres migration and engine coverage | COMPLETED |
| 4 | Align the checked-in health contract with the shell release | COMPLETED |
| 5 | Replace the discarded web shell with the database-backed health application | COMPLETED |
| 6 | Cut runtime configuration and sessions over to env-only psycopg | COMPLETED |
| 7 | Verify the worker entry point on the new settings and session stack | COMPLETED |
| 8 | Wire the existing Railway services to the real shell entry points | COMPLETED |
| 9 | Align the operator environment and setup guidance with the shipped shell | COMPLETED |
| 10 | Add the authoritative Postgres-backed backend CI gate | COMPLETED |
