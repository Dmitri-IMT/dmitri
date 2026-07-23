# POOP log

## Task 1: Schema foundation — model rename + durable host + 3 migrations

### Order Given
Implement Task 1 of `specs/015-read-path/TASKS.md` exactly: in
`backend/src/api/models/persistence.py`, rename `DeviceRecord`→`ScanHostRecord`
(table `devices`→`scan_hosts`), rename `PortRecord.device_id`/`FindingRecord.device_id`
→`scan_host_id`, add `HostRecord` (table `hosts`) with the specified columns and
org-scoped `NULLS NOT DISTINCT` unique constraint, add `ScanHostRecord.host_id` FK, and
replace `ScanRecord.target_mode`/`scan_profile` with `scan_mode`/`status`. Write the
three chained migrations (`20260722_03_scan_mode_status`, `20260722_04_scan_host_rename`,
`20260722_05_host_identity`) with the specified RLS/grants. Update the two existing
migration tests and add `test_host_identity_migration.py`. Scope limited to Task 1's
Target Files only.

### What, How, and Why
- Renamed `DeviceRecord`→`ScanHostRecord` (`devices`→`scan_hosts`), moved
  `PortRecord.device_id`/`FindingRecord.device_id` to `scan_host_id` with FK
  `scan_hosts.id`, per decision 3.
- Added `HostRecord` (table `hosts`) with `id: UUID` (`default_factory=uuid4`) PK,
  nullable `org_id` FK `orgs.id`, `identity_key`, latest-observation attrs, `first_seen_at`/
  `last_seen_at`, timestamps, and `UniqueConstraint("org_id","identity_key",
  postgresql_nulls_not_distinct=True)` per decision 2(a).
- Added `ScanHostRecord.host_id: UUID | None` FK `hosts.id`, indexed.
- Replaced `ScanRecord.target_mode`/`scan_profile` with `scan_mode: str` and
  `status: str = Field(default="completed")` per decision 4.
- Wrote migration 1 (`20260722_03`) as a straight column swap on `scans` (no grant
  changes — column edits don't need new grants).
- Wrote migration 2 (`20260722_04`) as `rename_table` + two `alter_column` renames +
  the cosmetic `devices_id_seq`→`scan_hosts_id_seq` sequence rename, with symmetric
  downgrade. No new grants (rename preserves privileges).
- Wrote migration 3 (`20260722_05`) creating `hosts` (UUID PK, two supporting non-unique
  indexes plus the `NULLS NOT DISTINCT` unique index), adding `scan_hosts.host_id` + FK +
  `ix_scan_hosts_host_id`, and the RLS fence (`ENABLE ROW LEVEL SECURITY`, revoke
  anon/authenticated, `GRANT SELECT, INSERT, UPDATE` only — no sequence/DELETE grant, no
  `CREATE ROLE`), matching the baseline/identity migration style.
- Updated `test_migrations.py`'s runtime-role test (`DeviceRecord`→`ScanHostRecord`,
  `target_mode`/`scan_profile`→`scan_mode`) and `test_identity_migration.py`'s
  `test_scan_accepts_org_scope` (same field swap).
- Discovered `test_migrations.py::test_baseline_matches_model_metadata_and_security_fence`
  also breaks under the rename (it asserts the baseline's table/column shapes are a
  subset of the live model metadata) since the baseline migration still literally
  creates `devices`/`device_id`/`target_mode`/`scan_profile`, which no longer exist
  verbatim in the renamed model. Extended that test's rename-tolerance logic (it
  already tolerated columns added by later migrations) to also tolerate the
  `devices`→`scan_hosts` table rename, the `device_id`→`scan_host_id` column renames on
  `ports`/`findings`, and the `target_mode`/`scan_profile` column drop on `scans`,
  since this file is one of Task 1's named Target Files and must stay green.
- Added `test_host_identity_migration.py` mirroring `test_identity_migration.py`'s
  monkeypatch-`op` harness style, generalised to capture every `alembic.op` method
  used across the three new migrations (`create_table`, `add_column`, `drop_column`,
  `alter_column`, `rename_table`, `create_index`, `drop_index`, `create_foreign_key`,
  `drop_constraint`, `execute`) and assert upgrade/downgrade behaviour plus the RLS/grant
  fence and no-sequence/no-DELETE/no-CREATE-ROLE invariants, plus a model-metadata
  registration test.

### Decisions Made
- Left `services/persistence.py`, `schemas/scan.py`, `schemas/persistence.py`,
  `services/enrichment.py`, and `test_ingest_scan.py` untouched even though they now
  reference removed model names/columns (`DeviceRecord`, `device_id`, `target_mode`,
  `scan_profile`) — those files are explicitly out of Task 1's Target Files and are
  Task 2/3/4's responsibility per the dependency graph; ran `ruff`/`pytest` scoped to
  Task 1's target files rather than the whole `backend/` tree, since the full suite is
  expected to be red until the dependent tasks land.
- Kept migration 2's index-rename step as a no-op (left the underlying
  `scan_id`+`ip` unique-constraint index name alone) per ARCHITECTURE's explicit
  "cosmetic, not required for correctness" carve-out.
- Used two non-unique supporting indexes (`ix_hosts_org_id`, `ix_hosts_identity_key`)
  plus the `NULLS NOT DISTINCT` unique index on `hosts`, matching the "indexed" column
  notes in the `hosts` column table and the explicit `uq_hosts_org_identity`/
  `ix_hosts_org_id` names called out in migration 3's spec.

### Code Changed
- `backend/src/api/models/persistence.py` (modified)
- `backend/alembic/versions/20260722_03_scan_mode_status.py` (created)
- `backend/alembic/versions/20260722_04_scan_host_rename.py` (created)
- `backend/alembic/versions/20260722_05_host_identity.py` (created)
- `backend/tests/test_migrations.py` (modified)
- `backend/tests/test_identity_migration.py` (modified)
- `backend/tests/test_host_identity_migration.py` (created)

## Task 1 — Schema foundation tests (test-writer)

**Order Given**: Add/verify pytest tests for Task 1 (schema foundation: model rename + durable
host + 3 migrations 03/04/05). Target files: `backend/src/api/models/persistence.py`,
`backend/alembic/versions/20260722_0{3,4,5}_*.py`, `backend/tests/test_migrations.py`,
`backend/tests/test_identity_migration.py`, `backend/tests/test_host_identity_migration.py`.
Tests only, no application-code changes; don't touch Tasks 2-4 modules.

**What, How, and Why**: Verified `backend/tests/test_host_identity_migration.py` (already
authored by the coder) against every Success Criteria bullet in TASKS.md Task 1: migration 03
drops `scans.target_mode`/`scan_profile`, adds `scan_mode`/`status` (non-nullable, `status`
server_default) and downgrade restores both old columns; migration 04 renames `devices`→
`scan_hosts`, `ports.device_id`/`findings.device_id`→`scan_host_id`, sequence rename statement,
and downgrade reverses all three; migration 05 creates `hosts`, adds nullable
`scan_hosts.host_id` + FK + `ix_scan_hosts_host_id`, unique index `uq_hosts_org_identity` on
`(org_id, identity_key)` with `postgresql_nulls_not_distinct=True`, RLS enable + correct
`GRANT SELECT, INSERT, UPDATE ON hosts TO dmitri_runtime` with no `SEQUENCE`/`DELETE`/
`CREATE ROLE` statements, and downgrade drops table/column/constraint/index; a model-registration
test asserts `scan_hosts`/`hosts` present, `devices` absent, `scans` has `scan_mode`/`status` and
lacks `target_mode`/`scan_profile`, FK and unique-constraint shape on the ORM metadata. Confirmed
`test_migrations.py` and `test_identity_migration.py` were already updated to the renamed
model/columns by the coder and stay green. Ran `uv run pytest` (16 passed, 7 skipped — DB-bound
tests skip locally without `DATABASE_URL_TEST`, pre-existing/expected) and
`uv run ruff check` (clean) across the three test files.

**Decisions Made**: No new test code was needed — the existing `test_host_identity_migration.py`
already fully covered the Success Criteria using a monkeypatched-`op` harness mirroring
`test_identity_migration.py`'s style (record every `op.*` call, assert upgrade/downgrade shape).
Did not add duplicate coverage. Did not touch `services/persistence.py` or `schemas/*` per
instructions (intentionally broken pending Tasks 2-4). Made no production-code changes.

**Code Changed**: none (verification only). Files inspected/confirmed:
`backend/tests/test_host_identity_migration.py`, `backend/tests/test_migrations.py`,
`backend/tests/test_identity_migration.py`.

## Review — Task 1: Schema foundation (gate)

**Order Given**: Review Task 1 of feature 015-read-path (backend/src/api/models/persistence.py,
the three 20260722 migrations, test_migrations.py, test_identity_migration.py,
test_host_identity_migration.py) against TASKS.md Task 1 and ARCHITECTURE.md decisions 2 & 3 /
migrations section. Run `uv run pytest` + `uv run ruff check` scoped to `backend/`. Tasks 2-4
target files are intentionally broken by this rename and out of scope for rejection.

**What, How, and Why**: Read TASKS.md Task 1 and the ARCHITECTURE.md migrations section (lines
240-400) to get the exact spec: model rename, `HostRecord` shape, `ScanRecord.scan_mode`/
`status`, and the three migrations' upgrade/downgrade contents including RLS/grants. Read the
full diff of `persistence.py` and the three new migration files, comparing column-by-column and
statement-by-statement against ARCHITECTURE.md's Migration 1/2/3 sections. Read both migration
test files to confirm they assert every Success Criterion (drop/add columns with correct
nullability/server_default, table/column renames + sequence rename, `hosts` table shape, FK,
unique index with `NULLS NOT DISTINCT`, RLS enable, exact grant statement, absence of
SEQUENCE/DELETE/CREATE ROLE grants, and model-metadata registration checks for
`devices` absent / `scan_hosts`+`hosts` present / `scans` columns renamed).

Ran `cd backend && uv run ruff check .` — all checks passed (repo-wide, not just touched files).
Ran `cd backend && uv run pytest -q` — collection failed on `tests/test_ingest_scan.py` and
`tests/test_worker_startup.py`, both importing `DeviceRecord` from `api.models.persistence`;
`test_ingest_scan.py` is explicitly pre-authorized broken (Task 2-4 scope), and
`test_worker_startup.py` fails transitively via `services/enrichment.py` (also Task 2-4 scope,
`services/enrichment.py` is a listed Task-4 target file) — both are pre-authorized, not Task 1
regressions. Re-ran with `--ignore=tests/test_ingest_scan.py --ignore=tests/test_worker_startup.py`:
47 passed, 8 skipped (DB-integration tests skip without `DATABASE_URL_TEST`, acceptable), 3 failed
in `tests/test_settings.py` (env-var leakage: `DID NOT RAISE ValidationError` /
`nvd_api_key` not None). Verified via `git stash` that these 3 `test_settings.py` failures are
pre-existing on the base commit (same 3 failures, same messages) — unrelated to Task 1's changes,
caused by ambient shell env vars (`DATABASE_URL`, `NVD_API_KEY`) leaking into the test process.
All of Task 1's own target files (models/persistence.py, the 3 migrations, the 3 migration test
files) pass fully with no failures attributable to this task.

**Decisions Made**: APPROVE. `HostRecord`, `ScanHostRecord.host_id`, `ScanRecord.scan_mode`/
`status`, and the `PortRecord`/`FindingRecord` `scan_host_id` renames in `persistence.py` match
ARCHITECTURE.md exactly, including the `UniqueConstraint("org_id","identity_key",
postgresql_nulls_not_distinct=True)`. All three migrations match their spec sections line-for-line:
Migration 1 drops/adds the right columns with the right nullability/server_default and correctly
reversible downgrade; Migration 2 renames table/columns/sequence with correct downgrade order;
Migration 3 creates `hosts` with FK/indexes, RLS enable, the DO-block role-existence guard
(mirroring the identity-migration precedent), the exact `GRANT SELECT, INSERT, UPDATE ON hosts TO
dmitri_runtime` with no SEQUENCE/DELETE/CREATE ROLE statements, and downgrade reverses cleanly.
`test_host_identity_migration.py` mirrors `test_identity_migration.py`'s monkeypatched-`op`
harness style and asserts every element of the Success Criteria; `test_migrations.py`'s baseline
shape-comparison test was correctly extended to tolerate the rename/dropped columns rather than
duplicating logic. No unrequested abstractions, no speculative flexibility, no dead code — the
change set is exactly the rename + three migrations the task specified, nothing more. No
`# ponytail:` markers were present in the touched files, so no strip was needed. Files changed
match Task 1's Target Files list exactly (no scope creep into Task 2-4 files). Ruff clean on the
full backend tree; pytest failures are fully attributable to pre-authorized Task 2-4 breakage
(`test_ingest_scan.py`, `test_worker_startup.py`→`services/enrichment.py`) or pre-existing,
unrelated `test_settings.py` env-leakage flakiness confirmed present on the base commit.

**Code Reviewed**: backend/src/api/models/persistence.py,
backend/alembic/versions/20260722_03_scan_mode_status.py,
backend/alembic/versions/20260722_04_scan_host_rename.py,
backend/alembic/versions/20260722_05_host_identity.py,
backend/tests/test_migrations.py, backend/tests/test_identity_migration.py,
backend/tests/test_host_identity_migration.py, backend/alembic/versions/20260716_02_identity_schema.py.

## Task 2: Ingest schema — scan_mode + Device→Host rename

**Order Given** — Implement Task 2 of 015-read-path: in `backend/src/api/schemas/scan.py`
remove `TargetMode`/`ScanProfile` and the `target_mode`/`scan_profile` fields; add
`scan_mode: Literal["quick","standard","extensive","nspi","max"]`; rename `Device`→`Host`,
`ScanResult.devices`→`hosts`, `ScanIngestResponse.devices_received`→`hosts_received`; export
`Host` from `schemas/__init__.py`; update `PersistedScanSummary`/`PersistedScanDetail` in
`schemas/persistence.py` to use `scan_mode` (+`status` on detail); leave `PersistedDevice`
naming as dead code.

**What, How, and Why** — Edited the three target files directly. In `scan.py`, replaced the
`ScanProfile`/`TargetMode` literals with a single `ScanMode` literal, renamed the `Device`
model to `Host`, and updated `ScanResult`/`ScanIngestResponse` field names to match ADR-013's
`host` vocabulary and TRUTH's single `scan_mode` vocabulary. `__init__.py`'s import/`__all__`
updated to export `Host` instead of `Device`. `persistence.py`'s `PersistedScanSummary` swapped
`target_mode`/`scan_profile` for `scan_mode`; `PersistedScanDetail` swapped the same pair for
`scan_mode` + added `status` (per TRUTH: scan detail exposes `scan_mode` and `status` directly,
no translation). `PersistedDevice` left untouched — it's flagged dead code per the task
description, to be handled by whichever later task addresses the persistence-layer rename.

**Decisions Made** — Kept `PersistedDevice`'s internal field/class naming exactly as specified
(explicitly out of this task's scope, flagged dead code, not touched). Did not touch
`api/services/enrichment.py` or `api/services/persistence.py`, which still reference
`Device`/`target_mode`/`scan_profile`/`devices_received` — those are consumers outside Task 2's
Target Files list and are the responsibility of later tasks (the host materialisation /
persistence-service tasks).

**Code Changed**
- Modified: `backend/src/api/schemas/scan.py`
- Modified: `backend/src/api/schemas/__init__.py`
- Modified: `backend/src/api/schemas/persistence.py`

## Task 2 — Tests

**Order Given** — Add/verify pytest tests for Task 2 of `015-read-path` (ingest schema:
scan_mode + Device→Host rename). Cover: `ScanResult` validates a scan_mode+hosts payload;
rejects `target_mode`/`scan_profile` or `devices`; `Host` importable from `api.schemas`;
`Persisted*` views reference `scan_mode`/`status` not dropped columns. Tests only, scoped to
import cleanly standalone (not via `test_ingest_scan.py`, whose collection is still broken
pending Tasks 3-4).

**What, How, and Why** — Created `backend/tests/test_ingest_schema.py`, a standalone module
importing only `api.schemas.Host`, `api.schemas.ScanResult`, and
`api.schemas.persistence.PersistedScanSummary`/`PersistedScanDetail` (no dependency on
`api.services.worker`/`persistence` or other enrichment-era modules), so it collects and runs
independently of the currently-broken `test_ingest_scan.py`. Six tests: (1) `ScanResult`
accepts a `scan_mode` + `hosts` payload and produces `Host` instances; (2) rejects a payload
carrying `target_mode`/`scan_profile`; (3) rejects a payload carrying `devices` instead of
`hosts`; (4) `Host` is importable from `api.schemas` and constructs correctly; (5)
`PersistedScanSummary` exposes `scan_mode`; (6) `PersistedScanDetail` exposes `scan_mode` and
`status`. Ran `uv run pytest tests/test_ingest_schema.py` locally in `backend/` to check current
behavior before finalizing assertions.

**Decisions Made** — Mocking boundary: none needed: these are pure Pydantic schema-validation
tests, no I/O or nmap runner involved (mirrors the "normalization: payload shape and validation
errors" strategy). Skipped exercising `PersistedFinding`/`PersistedArtifact`/etc. — out of Task
2's target files. Left `PersistedDevice` naming untested since the task explicitly flags it as
untouched dead code. **Finding, not fixed**: locally running the two "rejects" tests shows
`ScanResult` currently does NOT reject unknown fields (`target_mode`/`scan_profile`/`devices`)
— `backend/src/api/schemas/scan.py` has no `model_config = ConfigDict(extra="forbid")`, so
extra keys are silently ignored by Pydantic v2's default `extra="ignore"`, and `hosts` still
defaults to `[]` via `default_factory`. This means 2 of the 6 new tests currently FAIL against
Task 2's own stated success criteria ("rejects one carrying target_mode/scan_profile or
devices"). This is a production-code gap, not a test bug — left as-is per "tests only, no app
code" scope; the test file encodes the intended contract for the coder/reviewer to close.

**Code Changed**
- Created: `backend/tests/test_ingest_schema.py`

## Review: Task 2 — Ingest schema (scan_mode + Device→Host rename)

**Order Given**: Review Task 2 of feature 015-read-path as authoritative gate. Verify Success Criteria against TASKS.md Task 2 and ARCHITECTURE.md decisions 1 & 4. Test-engineer flagged possible missing `extra="forbid"` on `ScanResult` allowing silent ignore of `target_mode`/`scan_profile`/`devices` instead of rejection. Run `uv run pytest` and `uv run ruff check` in `backend/`; pre-authorized to ignore Task 3/4 collection breakage (services/persistence.py, services/enrichment.py, test_ingest_scan.py, test_worker_startup.py) and 3 pre-existing test_settings.py env-leak failures.

**What, How, and Why**:
- Read `specs/015-read-path/TASKS.md` Task 2 section and confirmed the exact Success Criteria wording, including the explicit requirement that `ScanResult` "rejects one carrying `target_mode`/`scan_profile` or `devices` (schema no longer accepts them)".
- Read `backend/src/api/schemas/scan.py`, `schemas/__init__.py`, `schemas/persistence.py`, and the new `backend/tests/test_ingest_schema.py`.
- Confirmed `ScanResult` (scan.py) has no `model_config = ConfigDict(extra="forbid")` — it relies on Pydantic's default `extra="ignore"`.
- Reproduced directly via `uv run python -c ...`: a payload with valid `scan_mode`/`hosts` plus extraneous `target_mode`/`scan_profile` fields validates successfully instead of raising, proving the fields are silently dropped, not rejected.
- Ran `uv run pytest tests/test_ingest_schema.py -v` in `backend/`: 4 passed, 2 failed — `test_scan_result_rejects_target_mode_and_scan_profile` and `test_scan_result_rejects_devices_field_without_hosts` both fail with "DID NOT RAISE ValidationError", i.e. the task's own committed tests fail against the task's own implementation.
- Ran `uv run ruff check` on the four changed/added files: all checks passed, no lint issues.
- Did not need to assess the pre-authorized Task 3/4 collection breakage or the pre-existing `test_settings.py` env-leak failures, since the failure found is squarely inside Task 2's own scope and its own new test file.

**Decisions Made**: REJECT. The test-engineer's flag is a real, reproduced failure, not a false positive. `ScanResult` must forbid extra fields (e.g. `model_config = ConfigDict(extra="forbid")`) so that payloads carrying dropped/renamed fields (`target_mode`, `scan_profile`, `devices`) are rejected rather than silently ignored. This is a one-line, clearly-scoped fix directly required by the stated Success Criterion — not a case of ambiguous requirements or overreach — so it is rejected rather than waived. `PersistedDevice` naming was correctly left as-is per the task's own note (flagged, not renamed), so no finding there. `Host` is correctly importable from `api.schemas`, and `PersistedScanSummary`/`PersistedScanDetail` correctly reference `scan_mode`/`status` and no longer reference the dropped `target_mode`/`scan_profile` columns.

**Code Reviewed**:
- backend/src/api/schemas/scan.py
- backend/src/api/schemas/__init__.py
- backend/src/api/schemas/persistence.py
- backend/tests/test_ingest_schema.py

## Task 2 — Fix: ScanResult extra="forbid" rejection

**Order Given** — Fix the REJECTED Task 2 of 015-read-path: close the one gap the reviewer
flagged — `ScanResult` in `backend/src/api/schemas/scan.py` must reject payloads carrying
`target_mode`/`scan_profile`/`devices` instead of silently dropping them, by adding
`model_config = ConfigDict(extra="forbid")`. Minimal fix only, scoped to Task 2's Target Files.

**What, How, and Why** — Added `ConfigDict` to the existing `pydantic` import and set
`model_config = ConfigDict(extra="forbid")` as the first line of `ScanResult` in
`backend/src/api/schemas/scan.py`, exactly as the reviewer specified. This makes Pydantic raise
`ValidationError` on any unexpected key instead of the v2 default `extra="ignore"` silent-drop
behavior, closing the gap between the two failing tests
(`test_scan_result_rejects_target_mode_and_scan_profile`,
`test_scan_result_rejects_devices_field_without_hosts`) and their asserted contract.

**Decisions Made** — Scoped the fix to `ScanResult` only, per the reviewer's explicit framing
("the criterion is about ScanResult rejecting target_mode/scan_profile/devices"). Considered
adding `extra="forbid"` to the nested `Host`/`Port`/`Finding`/`Artifact` models too, but left
them untouched: no failing test or stated Success Criterion covers them, and doing so risks
rejecting legitimate nested-payload fields never specified by this task — an unrequested,
speculative hardening outside Task 2's scope.

**Code Changed**
- Modified: `backend/src/api/schemas/scan.py`

## Task 2 — Re-review after ScanResult extra="forbid" fix (Reviewer)

**Order Given** — Re-review Task 2 of 015-read-path as authoritative gate after the prior
REJECT (ScanResult lacked `extra="forbid"`). Verify all Success Criteria met, run
`uv run pytest` and `uv run ruff check` in `backend/`, with pre-authorized non-failures for
Task 3-4 collection breakage (`services/persistence.py`, `services/enrichment.py`,
`test_ingest_scan.py`, `test_worker_startup.py`) and the 3 pre-existing `test_settings.py`
env-leak failures; `test_ingest_schema.py` must fully pass.

**What, How, and Why** — Read `specs/015-read-path/TASKS.md` Task 2 section and confirmed the
five Success Criteria. Read `backend/src/api/schemas/scan.py`, confirming
`model_config = ConfigDict(extra="forbid")` is present on `ScanResult`, `scan_mode: ScanMode`
and `hosts: list[Host]` exist, and no `target_mode`/`scan_profile`/`devices` fields remain.
Read `backend/src/api/schemas/__init__.py`, confirming `Host` is exported in place of `Device`.
Read `backend/src/api/schemas/persistence.py`, confirming `PersistedScanSummary` and
`PersistedScanDetail` use `scan_mode` (+ `status` on the detail view) and no longer reference
dropped columns; `PersistedDevice` naming intentionally left as-is per the task's own note
(flagged dead code, out of scope). Ran `uv run ruff check` on the three target files: all
checks passed. Ran `uv run pytest tests/test_ingest_schema.py -v`: 6/6 passed, including both
previously-failing rejection tests
(`test_scan_result_rejects_target_mode_and_scan_profile`,
`test_scan_result_rejects_devices_field_without_hosts`) and the persistence-schema tests. Ran
full `uv run pytest --ignore=tests/test_ingest_scan.py --ignore=tests/test_worker_startup.py`:
53 passed, 8 skipped, 3 failed — all three failures are the pre-authorized `test_settings.py`
env-leak failures (`test_missing_database_url_raises`,
`test_carried_fields_default_when_env_unset`,
`test_missing_database_url_fails_before_engine_construction`), unrelated to Task 2. Confirmed
the two ignored collection errors (`test_ingest_scan.py`, `test_worker_startup.py`) are the
pre-authorized Task 3-4 breakage (`DeviceRecord` import from `api.models.persistence`).
Grepped the three target files for `# ponytail:` markers: none found, nothing to strip.

**Decisions Made** — APPROVE. All five Task 2 Success Criteria are met: `ScanResult` validates
a `scan_mode`+`hosts` payload and rejects `target_mode`/`scan_profile`/`devices` payloads via
`extra="forbid"`; `Host` is importable from `api.schemas`; `Persisted*` views reference
`scan_mode`/`status`, not dropped columns; `uv run pytest` and `uv run ruff check` pass in
`backend/` modulo the explicitly pre-authorized non-failures. Target Files match exactly what
TASKS.md specifies. No over-engineering found — the fix was the minimal single-line
`ConfigDict(extra="forbid")` addition the prior review asked for, nothing more.

**Code Reviewed**
- backend/src/api/schemas/scan.py
- backend/src/api/schemas/__init__.py
- backend/src/api/schemas/persistence.py
- backend/tests/test_ingest_schema.py

## Task 3: Host materialisation service

**Order Given** — Implement Task 3 of `015-read-path`: new file
`backend/src/api/services/hosts.py` only, implementing `identity_key(mac, ip)` and
`upsert_hosts_for_scan(session, scan_record, scan)` per ADR-014 and ARCHITECTURE.md decision
2(b), matching `services/persistence.py` style, `uv run ruff check` clean.

**What, How, and Why** — Read `TASKS.md` Task 3, `ARCHITECTURE.md` decision 2 (a/b/c),
`TRUTH.md`'s host-identity section, `ADR-014`, and `models/persistence.py` for the exact
`HostRecord`/`ScanHostRecord`/`PortRecord`/`FindingRecord` field names (already renamed to the
`scan_host_id`/`hosts` vocabulary ahead of Task 4's rewire). Implemented `identity_key` as the
one-line MAC-else-IP rule. Implemented `upsert_hosts_for_scan` following the pseudocode
verbatim: load this scan's `ScanHostRecord`s, resolve/create a `HostRecord` scoped by
`org_id IS NOT DISTINCT FROM` (via SQLAlchemy's `Column.is_not_distinct_from`) + `identity_key`,
keep `first_seen_at` as the min, advance `last_seen_at` and refresh mutable attrs only when
`scan_record.timestamp >= host.last_seen_at`, and assign `sh.host_id = host.id` for every
scan-host regardless of branch. `open_ports_count`/`highest_severity` are computed by two small
helpers querying `PortRecord`/`FindingRecord` by `scan_host_id`, reusing the existing
`state == "open"` and severity-ordering conventions already used in `services/persistence.py`
(`_max_severity`). The `scan: ScanResult` parameter is accepted per the specced signature (Task
4 will pass it) but unused inside this function — the persisted `ScanHostRecord` rows and
`scan_record.timestamp` are sufficient — so it's discarded with `del scan` to make that
explicit rather than leaving a silent unused argument.

**Decisions Made** — Query `ScanHostRecord` rows for this scan from the DB (`scan_id ==
scan_record.scan_id`) rather than deriving them from the `scan` schema argument, since the
schema payload has no ids/host_id slot to write back to — only the persisted ORM rows do. New
`HostRecord`s are `session.flush()`-ed immediately so `host.id` exists before being assigned to
`sh.host_id`. Did not add a migration, router wiring, or call site — out of scope for Task 3,
which is Task 4's job.

**Code Changed**
- backend/src/api/services/hosts.py (created)

## Task 3 test coverage — identity_key unit tests

**Order Given** — Add pytest tests for Task 3 (`backend/src/api/services/hosts.py`), scoped to
the pure DB-free `identity_key(mac, ip)` helper only; `upsert_hosts_for_scan` DB integration
testing is explicitly Task 4's responsibility and was not duplicated here.

**What, How, and Why** — Added `backend/tests/test_hosts_identity_key.py` with three cases:
MAC present (mixed case) → `mac:` prefix, upper-cased; MAC `None` → `ip:` fallback; MAC `""`
(falsy but not `None`) → `ip:` fallback. These three cover the full branch surface of the
one-line `if mac: ... else: ...` implementation — success, explicit absence, and the empty-string
edge case that a naive `is None` check would miss. Mirrors `test_ingest_schema.py` for style
(module-level functions, `from __future__ import annotations`, plain asserts, no fixtures/
classes). Import surface is limited to `api.services.hosts.identity_key`, keeping the module
DB-free per the task's "import-clean" instruction.

**Decisions Made** — No DB/session mocking needed since `identity_key` takes no session
argument. Did not test `upsert_hosts_for_scan` (Task 4's `test_host_materialisation.py` owns
that). Ran `uv run pytest tests/test_hosts_identity_key.py -q` locally — all 3 pass.

**Code Changed**
- backend/tests/test_hosts_identity_key.py (created)

## Review: Task 3 — Host materialisation service

**Order Given**: Review Task 3 (services/hosts.py + test_hosts_identity_key.py) as authoritative gate against TASKS.md Task 3, ARCHITECTURE.md decision 2(b), and ADR-014.

**What, How, and Why**: Read TASKS.md Task 3 section, ARCHITECTURE.md decision 2(a)/(b) (hosts table schema + materialisation algorithm pseudocode), and ADR-014. Read backend/src/api/services/hosts.py and backend/tests/test_hosts_identity_key.py in full, and cross-checked HostRecord model in backend/src/api/models/persistence.py for field parity. Ran `uv run ruff check src/api/services/hosts.py tests/test_hosts_identity_key.py` (passed, no findings) and `uv run pytest tests/test_hosts_identity_key.py -q` (3 passed) in backend/.

**Why**: `identity_key` implementation exactly matches ADR-014/ARCHITECTURE (`mac:{MAC upper}` else `ip:{ip}`), with unit tests covering MAC-present, MAC-None, and MAC-empty-string fallback. `upsert_hosts_for_scan` follows the specced pseudocode line-for-line: resolves host by `org_id IS NOT DISTINCT FROM` + `identity_key`, creates with `first_seen_at=last_seen_at=scan_record.timestamp` on miss, on hit takes `min()` for `first_seen_at` and only advances `last_seen_at`/mutable attrs (ip, mac, hostname, vendor, open_ports_count, highest_severity) when `scan_record.timestamp >= host.last_seen_at`, and always sets `sh.host_id = host.id`. `open_ports_count`/`highest_severity` helpers are minimal, direct, no speculative abstraction. No unrelated files touched; Target Files match exactly. No orchestrator/runner threading applies to this backend-only change. No `# ponytail:` markers present.

**Decisions Made**: APPROVE. Implementation is a faithful, minimal translation of the ADR-014/ARCHITECTURE algorithm; unit tests for `identity_key` are correct and sufficient per the task's scoped success criteria (upsert DB behavior deferred to Task 4 as instructed). Lint and identity-key tests both pass.

**Code Reviewed**:
- backend/src/api/services/hosts.py
- backend/tests/test_hosts_identity_key.py
- backend/src/api/models/persistence.py (HostRecord, read-only cross-check)

## Task 4: Ingest persist_scan rewire + materialisation call

**Order Given**: In `services/persistence.py` `persist_scan`: write `scan_mode=scan.scan_mode`, drop `target_mode`/`scan_profile`; rename `_persist_device`→`_persist_scan_host`, `device_index`→`scan_host_index`, `device_record`→`scan_host_record`; iterate `scan.hosts`; call `upsert_hosts_for_scan(...)` in the same transaction after scan-hosts/ports have ids. Add `test_host_materialisation.py`, update `test_ingest_scan.py` to the new vocabulary. Grep for stray `DeviceRecord`/`device_id`/`target_mode`/`scan_profile`/`_persist_device` in touched files and report (not fix) any out-of-scope breakage.

**What, How, and Why**: Rewrote `persist_scan` to build `ScanRecord` with `scan_mode` only (status keeps its model default `"completed"`), iterate `scan.hosts` (the `Host` schema from Task 2) via a renamed `_persist_scan_host`/`_persist_port` pair that writes `ScanHostRecord`/`PortRecord.scan_host_id`, and call `upsert_hosts_for_scan(session, scan_record, scan)` (Task 3's service) after scan-hosts, ports and findings are flushed but before the enrichment-job commit, so it runs in the same transaction and each `ScanHostRecord.host_id` is set before `session.commit()`. `upsert_finding`'s `device_record` parameter/`device_id` write were renamed to `scan_host_record`/`scan_host_id` to match `FindingRecord`'s renamed column (Task 1) — required for `persist_scan` to even compile, so kept in scope despite not being explicitly named in the rename list. Wrote `test_host_materialisation.py` constructing `ScanResult`/`Host` objects directly (rather than the shared JSON fixture, see blocker below) covering all four required scenarios. Updated `test_ingest_scan.py`'s import and first assertion to `ScanHostRecord`/`scan_mode`/`status == "completed"`.

**Decisions Made**:
- Built materialisation-test fixtures inline instead of reusing `contracts/examples/scan_result.example.json`, because that file is still in the old `devices`/`target_mode`/`scan_profile` shape (Task 8 — Contract deltas — is PENDING) and fails `ScanResult.model_validate` regardless of Task 4's changes.
- Left `upsert_finding`'s enrichment.py caller (`services/enrichment.py:153`) unrenamed/unfixed — out of Task 4's target files.

**Blockers found, not fixed (out of scope per instructions)**:
- `backend/src/api/services/enrichment.py` imports `DeviceRecord` from `api.models.persistence` (line 8) and reads `port_record.device_id` (line 125); neither exists any more after Task 1's model rename. This pre-dates Task 4 (confirmed by reverting my changes and re-testing) and is not caused by this task's edits. Because `services/worker.py` imports `services/enrichment.py`, and `tests/test_ingest_scan.py` imports `services/worker` for its worker tests, `tests/test_ingest_scan.py` and `tests/test_worker_startup.py` fail to *collect* — this blocks running the two other pre-existing tests in `test_ingest_scan.py`, though the one test I edited (`test_ingest_scan_accepts_enriched_findings_example`) and `test_host_materialisation.py` are both correct against `persist_scan` in isolation. Fixing `enrichment.py` is outside Task 4's Target Files; flagging for whichever task owns it (likely Task 1 follow-up or Task 8).
- `contracts/examples/scan_result.example.json` (Task 8's Target File) is still `devices`/`target_mode`/`scan_profile`-shaped; `ScanResult.model_validate` on it fails independent of Task 4.
- `uv run pytest` cannot fully green the suite in this environment because `DATABASE_URL_TEST` is unset (all DB-backed tests, including my new ones, report `skipped`) and the two collection errors above block two files outright. `uv run pytest --ignore=tests/test_ingest_scan.py --ignore=tests/test_worker_startup.py` passes 56/59 (3 unrelated pre-existing `test_settings.py` env-pollution failures). `uv run ruff check` passes clean on all touched files and repo-wide.

**Code Changed**:
- Modified: `backend/src/api/services/persistence.py`
- Modified: `backend/tests/test_ingest_scan.py`
- Created: `backend/tests/test_host_materialisation.py`

## Review: Task 4 — Ingest persist_scan rewire + materialisation call (gate)

**Order Given**: Review Task 4 of feature 015-read-path as authoritative gate. Target files:
`backend/src/api/services/persistence.py` (persist_scan rewire), `backend/src/api/services/enrichment.py`
(mechanical rename folded in by orchestrator per CLAUDE.md integration rule — it sits on the
`worker.py → enrichment.py` ingest call path and still referenced pre-Task-1 `DeviceRecord`/
`device_id`/`device_record` names), `backend/tests/test_host_materialisation.py` (new),
`backend/tests/test_ingest_scan.py` (updated). Verify every Task 4 Success Criterion against
TASKS.md, ARCHITECTURE.md (naming table, ingest service row, materialisation algorithm), and
TRUTH.md. Run `uv run pytest --ignore=tests/test_worker_startup.py` and `uv run ruff check` in
`backend/`; `test_worker_startup.py`'s hang is pre-existing/out of scope (byte-identical to main),
and the 3 `test_settings.py` env-leak failures are pre-authorized.

**What, How, and Why**:
- Read TASKS.md Task 4, ARCHITECTURE.md (system context, decision 2(b) materialisation algorithm,
  decision 3 rename table, the "New files and naming" table's `services/persistence.py` row), and
  TRUTH.md's business rules on `first_seen_at`/`last_seen_at`/`scan_mode`/`status`.
- Read the full diff of `backend/src/api/services/persistence.py` against `main`: `persist_scan`
  now builds `ScanRecord(scan_mode=scan.scan_mode, ...)` with no `target_mode`/`scan_profile`
  (relying on `status`'s model default `"completed"`); `_persist_device`→`_persist_scan_host`,
  `device_index`→`scan_host_index`, `device_record`/`device_id`→`scan_host_record`/`scan_host_id`
  throughout; iterates `scan.hosts` (not `.devices`); calls `upsert_hosts_for_scan(session,
  scan_record, scan)` after scan-hosts/ports/findings are flushed but before the final
  `session.commit()`, so materialisation runs inside the same transaction as the rest of ingest.
- Read the full diff of `backend/src/api/services/enrichment.py` against `main`: a purely
  mechanical rename (`DeviceRecord`→`ScanHostRecord` import, `port_record.device_id`→
  `port_record.scan_host_id`, `device_record=device`→`scan_host_record=device` kwarg) with no
  other line touched — confirms the orchestrator's scope note is accurate and the coder did not
  smuggle in unrelated changes.
- Read `backend/src/api/services/hosts.py` (Task 3's file, unmodified by Task 4) to confirm
  `upsert_hosts_for_scan`'s signature/behavior matches what `persist_scan` now calls.
- Read `backend/tests/test_host_materialisation.py` in full and checked each of its four tests
  against the Success Criteria: same-MAC scan A (older)/B (newer) → one `HostRecord`, both
  `ScanHostRecord`s share `host_id`, `first_seen_at == A.timestamp` unchanged after B,
  `last_seen_at == B.timestamp`, mutable attrs (ip/hostname/vendor) reflect B; MAC-absent
  resolves by IP (two same-IP no-MAC scans → one host); a host only in the latest scan has
  `first_seen_at == latest.timestamp`; every `ScanHostRecord.host_id` is set for a two-host scan.
  All four map 1:1 onto TASKS.md's Task 4 Success Criteria sentence.
- Read `backend/tests/test_ingest_scan.py`: confirmed it imports `ScanHostRecord` (not
  `DeviceRecord`), builds `ScanResult` via `scan_mode`/implicit `hosts` from the JSON fixture,
  and asserts `record.scan_mode == scan.scan_mode` and `record.status == "completed"`.
- Grepped `backend/src` for `DeviceRecord|target_mode|scan_profile|\.device_id` excluding
  `PersistedDevice`: zero hits — confirms the rename is complete with no stragglers.
- Grepped touched files for `# ponytail:` markers: none present, nothing to strip.
- Ran `uv run ruff check` on the four target files: all checks passed.
- Ran `uv run pytest --ignore=tests/test_worker_startup.py -q`: 56 passed, 16 skipped, 3 failed
  (all three are the pre-authorized `test_settings.py` env-leak failures — same names/messages as
  every prior review in this POOP log, confirmed pre-existing and unrelated to Task 4).
- Ran `uv run pytest tests/test_host_materialisation.py tests/test_ingest_scan.py -v`: all 8 tests
  SKIPPED (no `DATABASE_URL_TEST` locally) — expected per the review scope note; judged their
  assertions by reading, as instructed, rather than by execution.
- Did not run the full unscoped suite (`test_worker_startup.py` hangs); confirmed via
  `git diff --stat main..HEAD -- backend/tests/test_worker_startup.py` that the file is
  byte-identical to `main` (empty diff), so its hang is pre-existing and untouched by this task.

**Decisions Made**: APPROVE. All Task 4 Success Criteria are met: `scan_mode`/`hosts` payload
persists with `ScanRecord.scan_mode` equal to the sent value and `status == "completed"`;
`test_host_materialisation.py`'s four tests correctly assert the full materialisation contract
(single host across two scans, `first_seen_at` never moving backward, `last_seen_at` advancing,
mutable-attrs-reflect-latest, MAC-absent IP resolution, latest-only host's `first_seen_at`, every
`host_id` assigned); `test_ingest_scan.py` uses the renamed vocabulary and asserts
`status="completed"`. The CLAUDE.md TUI-threading integration rule is N/A per TRUTH/ARCHITECTURE's
explicit note (no new `ScanRunner`/`ScanOrchestrator` parameter added by this feature) — correctly
not applicable here. No duplicate scan paths or copied helpers: `persist_scan` calls Task 3's
single canonical `upsert_hosts_for_scan`, nothing reimplemented. No over-engineering: the diff is
exactly the specced rename plus one new call, `enrichment.py`'s change is a strict three-line
mechanical rename with zero unrelated edits, and the new test file is the minimal fixture-building
style already used elsewhere in the suite — nothing to shrink, no dead flexibility, no unneeded
abstraction. Files changed match Task 4's Target Files (plus the orchestrator-authorized
`enrichment.py` addition) exactly. Ruff clean; pytest clean modulo the pre-authorized env-leak
failures and the pre-existing, out-of-scope `test_worker_startup.py` hang.

**Code Reviewed**:
- backend/src/api/services/persistence.py
- backend/src/api/services/enrichment.py
- backend/src/api/services/hosts.py (read-only cross-check)
- backend/tests/test_host_materialisation.py
- backend/tests/test_ingest_scan.py

## Task 5: Read response schemas

### Order Given
New file only: backend/src/api/schemas/read.py. Create the nine contract-shaped
pydantic models per ARCHITECTURE "API response schemas": Port, ScanHostView
(HostPayload fields + required host_id, C9, distinct from ingest Host/HostPayload),
FindingRead (DB→wire mapping), HostSummary (+ first_seen_at, C6), HostScanHistoryEntry,
HostDetailResponse, ScanDetailResponse (hosts=ScanHostView[], findings=FindingRead[],
scan_mode/status/counts), and envelopes HostListResponse/FindingListResponse
({data, total, page}). Field names/types must match contracts/openapi/openapi.yaml
exactly for the touched schemas.

### What, How, and Why
Wrote backend/src/api/schemas/read.py with the nine models, matching field names/
types/constraints from the openapi.yaml components (Port, ScanDetailResponse,
HostSummary, HostScanHistoryEntry, HostDetailResponse, HostListResponse,
FindingRecord, FindingListResponse, DevicePayload) plus the two contract deltas
(C6 first_seen_at on HostSummary, C9 ScanHostView with required host_id) that
ARCHITECTURE.md specifies but that Task 8 applies to the yaml itself. Matched the
existing style of schemas/scan.py (constr patterns, Annotated Field bounds,
model_config extra="forbid" per additionalProperties: false in the contract).

### Decisions Made
- Kept ScanHostView fully separate from schemas/scan.py's Host/HostPayload per C9 —
  no shared base class, since the contract explicitly forbids reusing the ingest
  shape and the two schemas are allowed to drift independently.
- Declared local ScanMode/ScanStatus/Severity Literal aliases in read.py rather than
  importing from schemas/scan.py, since scan.py's ScanMode lacks a status concept and
  read.py is meant to be a self-contained wire-contract module distinct from ingest.
- FindingRead.host_id/host_ip are optional (Optional[UUID]/Optional[IPvAnyAddress])
  matching the contract's anyOf-with-null, since a finding may be host-scoped or
  scan-scoped only.
- Used model_config = ConfigDict(extra="forbid") on every model to mirror the
  contract's additionalProperties: false, consistent with ScanResult in scan.py.

### Code Changed
- Created: backend/src/api/schemas/read.py

## Task 5 tests — Read response schemas

### Order Given
Add pytest tests for Task 5 of feature 015-read-path: the new
backend/src/api/schemas/read.py (nine read-response pydantic models). Cover:
all nine models importable from api.schemas.read; HostSummary.first_seen_at
and ScanHostView.host_id present and required; ScanHostView distinct from
ingest Host/HostPayload; field names/types match the contract for the touched
schemas.

### What, How, and Why
Wrote backend/tests/test_read_schema.py mirroring the style of
test_ingest_schema.py (payload-builder helpers + model_validate). Tests cover:
an import/existence check enumerating all nine models and asserting each is a
pydantic BaseModel subclass; ScanHostView.host_id and HostSummary.first_seen_at
each get a "missing field raises ValidationError" case and a "present and
correctly typed" case; a distinctness check asserting ScanHostView is not
Host and neither subclasses the other; a shape check on ScanHostView rejecting
a missing hostname (a required field per contract); envelope shape checks for
HostListResponse and FindingListResponse (data/total/page); and a nested-model
check on ScanDetailResponse confirming its hosts list holds ScanHostView
instances.

### Decisions Made
- Imported only api.schemas.read plus api.schemas.Host (for the distinctness
  assertion), per the import-clean constraint.
- Did not exhaustively test every field of every model (e.g. FindingRead's
  full field list, Port's protocol/state literals) — Success Criteria asks for
  field/type match on the touched schemas (ScanHostView, HostSummary), so
  deeper per-field literal validation was left uncovered to avoid padding.
- No production code changes.

### Code Changed
- Created: backend/tests/test_read_schema.py

## Task 5 Review: Read response schemas

### Order Given
Review Task 5 of feature 015-read-path as authoritative gate: verify the nine new
pydantic models in `backend/src/api/schemas/read.py` and their tests in
`backend/tests/test_read_schema.py` against ARCHITECTURE.md "API response schemas" and
`contracts/openapi/openapi.yaml`, field-by-field, plus run the ruff/pytest gates.

### What, How, and Why
- Read `TASKS.md` Task 5 and the ARCHITECTURE.md "API response schemas" section for the
  spec, and `contracts/openapi/openapi.yaml` for the authoritative shapes of `Port`,
  `DevicePayload` (pre-rename `HostPayload`), `FindingRecord`, `HostSummary`,
  `HostScanHistoryEntry`, `HostDetailResponse`, `ScanDetailResponse`,
  `HostListResponse`/`FindingListResponse`.
- Read `backend/src/api/schemas/read.py` in full and compared every field, type,
  required/optional status, and constraint (patterns, min/max, enums) against the
  contract, cross-checking against the existing ingest convention in
  `backend/src/api/schemas/scan.py` (`Host`/`Port`) for fields the yaml marks
  "required" but ships a wire-level default (`mac`, `ports`) — the new models follow
  the same established pattern, not a new deviation.
- Confirmed `ScanHostView.host_id: UUID` is required with no default, and
  `HostSummary.first_seen_at: datetime` is required with no default (C6/C9).
- Confirmed `ScanHostView` does not subclass or alias the ingest `Host` model, and the
  test file asserts this explicitly (`test_scan_host_view_is_distinct_from_ingest_host`).
- Confirmed the contract deltas (ADR-013 renames, C6, C9) are correctly *not* yet
  applied to `contracts/openapi/openapi.yaml` — that is Task 8's scope, not Task 5's;
  `read.py` correctly implements the *post-delta* shape ahead of the yaml catching up.
- Verified `git status` shows only `backend/src/api/schemas/read.py` (new) and
  `backend/tests/test_read_schema.py` (new) as this task's changes; other dirty files
  (`schemas/__init__.py`, `schemas/persistence.py`, `schemas/scan.py`) are pre-existing
  uncommitted work from earlier tasks (Device→Host rename), untouched by this diff.
- Ran `cd backend && uv run ruff check src/api/schemas/read.py tests/test_read_schema.py`
  → `All checks passed!`.
- Ran `cd backend && uv run pytest tests/test_read_schema.py -q` → `10 passed`.
- Ran `cd backend && uv run pytest --ignore=tests/test_worker_startup.py -q` → `3 failed,
  66 passed, 16 skipped`; the 3 failures are all in `tests/test_settings.py`
  (`nvd_api_key` env leak / missing-DATABASE_URL cases), matching the pre-authorized,
  pre-existing failures called out in the review order. No other regressions.
- Checked for `# ponytail:` marker comments in the touched files: none present.
- CLAUDE.md's ScanRunner/ScanProgressScreen integration rule does not apply — Task 5
  adds no orchestrator/runner parameter, only pydantic response models.

### Decisions Made
`[APPROVE]`. All nine models are present with fields/types matching the contract for
the touched schemas (accounting for the not-yet-applied Task 8 yaml deltas, which this
task correctly anticipates per ARCHITECTURE's spec). `ScanHostView.host_id` and
`HostSummary.first_seen_at` are required with no default. `ScanHostView` is verifiably
distinct from the ingest `Host`. `FindingRead`'s field set and required list match the
DB→wire mapping spec. The two envelopes are `{data, total, page}`. No dead code, no
unrequested abstractions, no duplicate scan paths — models are flat pydantic classes
matching the existing codebase convention with nothing extra. Gates are clean modulo
the pre-authorized `test_settings.py` failures.

### Code Reviewed
- backend/src/api/schemas/read.py
- backend/tests/test_read_schema.py
- specs/015-read-path/TASKS.md (Task 5 section)
- specs/015-read-path/ARCHITECTURE.md (API response schemas section)
- contracts/openapi/openapi.yaml (Port, DevicePayload, FindingRecord, HostSummary,
  HostScanHistoryEntry, HostDetailResponse, ScanDetailResponse, HostListResponse,
  FindingListResponse, Severity, ScanMode, ScanStatus schemas)
- backend/src/api/schemas/scan.py (ingest Host/Port convention cross-check)

## Task 6: Read service — queries

### Order Given
Implement Task 6 of `specs/015-read-path/TASKS.md`: new file
`backend/src/api/services/read.py` implementing `list_hosts()`, `get_host_detail()`,
`get_scan_detail()`, `list_findings()` as read-only queries over the sync session.
`list_findings(host_id=...)` joins `FindingRecord.scan_host_id → ScanHostRecord.id →
ScanHostRecord.host_id == host_id` excluding `scan_host_id IS NULL`. `get_host_detail`
returns ports from the latest observation's scan-host and `scan_history` from
`scan_hosts`⋈`scans` where `host_id == id`. `get_scan_detail` maps each host row's
`host_id` from `ScanHostRecord.host_id` and reads `scan_mode`/`status` directly from
the stored scan, no vocabulary translation. Only create
`backend/src/api/services/read.py`.

### What, How, and Why
Wrote four functions matching `schemas/read.py`'s models exactly:
- `list_hosts(session, page, per_page)` — paginates `HostRecord` ordered by
  `last_seen_at` desc, maps straight to `HostSummary` (all fields, including
  `open_ports_count`/`highest_severity`, already materialized on `HostRecord` by
  `services/hosts.py`'s `upsert_hosts_for_scan` — no recomputation needed here).
- `get_host_detail(session, host_id)` — 404-shaped `None` return if the host is
  missing; ports come from the most-recently-created `ScanHostRecord` for that
  `host_id`; `scan_history` joins `scan_hosts`⋈`scans` on `host_id`, recomputing each
  entry's `open_ports_count`/`highest_severity` per historical scan-host via the
  existing `_open_ports_count`/`_highest_severity` helpers in `services/hosts.py`
  (reused rather than reimplemented).
- `get_scan_detail(session, scan_id)` — `None` if scan missing; builds `ScanHostView`
  rows straight from `ScanHostRecord.host_id` (no lookup/translation) and reads
  `scan.scan_mode`/`scan.status` directly off the stored `ScanRecord`; findings use an
  outer join to `ScanHostRecord` to resolve each finding's `host_id` (nullable is
  fine here — `FindingRead.host_id` is optional, unlike `ScanHostView.host_id`).
  `command_id` has no backing column so it's always `None`.
- `list_findings(session, host_id, page, per_page)` — when `host_id` is given, uses an
  inner join to `ScanHostRecord` (naturally excludes `scan_host_id IS NULL` rows per
  the spec); when omitted, uses an outer join so all findings are still returned with
  best-effort resolved `host_id`.
- `_ports_for_scan_host` and `_to_finding_read`/`_to_host_summary` are small private
  helpers shared across the four public functions to avoid duplicating the
  port/service join and the DB→wire finding mapping.

### Decisions Made
- Reused `services/hosts.py`'s private `_open_ports_count`/`_highest_severity` rather
  than duplicating severity-ordering logic, since `get_host_detail`'s `scan_history`
  needs the exact same per-scan-host aggregation those already compute.
- Pagination params (`page`, `per_page`) default to 1/20 to match the contract's
  existing `Page`/`PerPage` query-parameter defaults in `openapi.yaml`; Task 7's
  router wires the actual query params through.
- `list_hosts`/`get_host_detail` do not recompute `open_ports_count`/`highest_severity`
  for the *current* host state — they read `HostRecord`'s already-materialized columns,
  since Task 1/5's `upsert_hosts_for_scan` is the single writer of that projection and
  the read layer must stay read-only per ARCHITECTURE's "System context".
- `get_scan_detail`/`list_findings` intentionally do not translate `scan_mode`/`status`
  — read directly off `ScanRecord` columns per the task's explicit instruction (Task 1
  already dropped the vestigial `target_mode`/`scan_profile`).

### Code Changed
- Created: `backend/src/api/services/read.py`

## Task 6 Test Coverage (agent: test-writer)

### Order Given
Add test coverage for Task 6 (new `backend/src/api/services/read.py`), without duplicating Task 7's endpoint-level DB-integration tests.

### What, How, and Why
Inspected `read.py`: all four public functions (`list_hosts`, `get_host_detail`, `get_scan_detail`, `list_findings`) take a `Session` and issue queries directly; the two private helpers (`_ports_for_scan_host`, `_to_host_summary`, `_to_finding_read`) either also take a `Session` or are trivial dict-shaping functions already exercised indirectly by the public functions. There is no DB-free logic worth isolating. Per the task spec ("Covered by Task 7's endpoint tests"), behavioral coverage is deferred to `test_read_endpoints.py`. Added a single import-smoke test in `backend/tests/test_read_service.py` asserting the four public functions exist, are callable, and accept a `session` parameter — catching accidental renames/signature drift without duplicating Task 7's DB-integration assertions.

### Decisions Made
- No DB fixtures or session mocking added — would duplicate Task 7 coverage per spec.
- Did not test private helpers (`_ports_for_scan_host`, `_to_host_summary`, `_to_finding_read`) directly; they are session-bound or trivially covered via the public functions in Task 7.

### Code Changed
- Created: `backend/tests/test_read_service.py`

## Task 6 review — 2026-07-22

**Order Given**: Review Task 6 (read service — `backend/src/api/services/read.py`) as authoritative
gate. Verify success criteria against `TASKS.md` Task 6, `ARCHITECTURE.md`, `schemas/read.py`,
`models/persistence.py`; run `uv run ruff check` and `uv run pytest --ignore=tests/test_worker_startup.py`
in `backend/`.

**What, How, and Why**:
- Read `TASKS.md` Task 6 section, `ARCHITECTURE.md` (decisions 2/3/4, naming table), `schemas/read.py`,
  `models/persistence.py`, `services/read.py`, `services/hosts.py`, `tests/test_read_service.py`.
- Ran `uv run ruff check src/api/services/read.py tests/test_read_service.py` — clean.
- Ran `uv run pytest tests/test_read_service.py -v` — the single import-smoke test passes.
- Ran `uv run pytest --ignore=tests/test_worker_startup.py -q` — 3 failures, all in
  `tests/test_settings.py` (pre-authorized env-leak failures per review scope), 67 passed, 16 skipped.
- Because the only test for this task is an import-smoke test (behavioral coverage deferred to Task 7
  per spec), I wrote a throwaway sqlite-backed script (not committed) to actually invoke
  `list_findings()` against a `FindingRecord` row, to check query correctness as instructed
  ("Check query correctness carefully"). It crashed.

**Decisions Made — REJECT**:
1. `_to_finding_read` in `services/read.py` passes `finding.id` (an `int`, `FindingRecord.id`'s type
   per `models/persistence.py`) into `FindingRead.finding_id: UUID` (`schemas/read.py`). Pydantic
   does not coerce `int` → `UUID`; this raises `ValidationError` on any call to `list_findings()` or
   `get_scan_detail()` that touches a row with findings — confirmed by direct reproduction (see script
   above): `1 validation error for FindingRead / finding_id / UUID input should be a string, bytes or
   UUID object [type=uuid_type, input_value=1, input_type=int]`. This violates the Task 6 success
   criterion "each function returns the corresponding `schemas/read.py` model(s)" — it cannot, it
   crashes instead.
2. `get_host_detail`'s "latest observation" (ports) is selected via
   `ScanHostRecord.created_at.desc()` (row insertion order), while `upsert_hosts_for_scan` in
   `services/hosts.py` (the code that sets the host's mutable attrs: ip/mac/hostname/vendor/
   open_ports_count/highest_severity) defines "latest" via `scan_record.timestamp` comparison and
   explicitly handles out-of-order/backfilled scan ingestion (`ARCHITECTURE.md` decision 2(b),
   "older backfilled scan" comment in the algorithm). These two "latest" definitions diverge whenever
   a scan is persisted out of timestamp order, so `HostDetailResponse.ports` can come from a different
   scan than the one that produced `ip`/`mac`/`hostname`/`vendor`/`open_ports_count`/
   `highest_severity` on the same response — an internally inconsistent host detail view, and a
   violation of the ARCHITECTURE-mandated "latest observation" semantics that Task 6's own success
   criteria (and the review brief's explicit "latest-observation selection" instruction) call out.

Both are correctness bugs in the reviewed target file `backend/src/api/services/read.py`, not
pre-existing/out-of-scope issues — the mapping and ordering logic are new code written for this task.
Gates (ruff, pytest) pass, but passing gates does not substitute for correct query logic when the only
test is an import smoke test. Rejecting.

**Code Reviewed**: `backend/src/api/services/read.py`, `backend/tests/test_read_service.py`,
`backend/src/api/schemas/read.py`, `backend/src/api/models/persistence.py`,
`backend/src/api/services/hosts.py`, `specs/015-read-path/TASKS.md`, `specs/015-read-path/ARCHITECTURE.md`.

## Task 6 fix attempt (post-rejection)

**Order Given** — Fix the REJECTED Task 6 target file `backend/src/api/services/read.py` only,
addressing both reviewer-cited bugs: (1) `_to_finding_read` passing `finding.id` (int) into
`FindingRead.finding_id` (UUID), (2) `get_host_detail` selecting "latest observation" ports via
`ScanHostRecord.created_at` instead of joined `ScanRecord.timestamp`. Investigate bug #1's authoritative
type before touching it; stop and report rather than editing out of scope if the fix requires schema/model
changes.

**What, How, and Why**:
- Bug #2 (fixed in `read.py`): changed `get_host_detail`'s `latest_scan_host` query to
  `.join(ScanRecord, ScanHostRecord.scan_id == ScanRecord.scan_id)` and
  `.order_by(ScanRecord.timestamp.desc())` instead of `ScanHostRecord.created_at.desc()`, matching
  `upsert_hosts_for_scan`'s definition of "latest" (ARCHITECTURE decision 2(b): latest by
  `scan_record.timestamp`, not insertion order — needed to handle out-of-order/backfilled scans
  correctly). This keeps `HostDetailResponse.ports` sourced from the same scan as the mutable host
  attrs.
- Bug #1 (NOT fixed — investigated and stopping to report): traced the authoritative type across all
  three sources.
  - `contracts/openapi/openapi.yaml` `FindingRecord` schema (line 2124): `finding_id: {type: string,
    format: uuid}`, required.
  - `backend/src/api/schemas/read.py` `FindingRead.finding_id: UUID` — matches the contract.
  - `backend/src/api/models/persistence.py` `FindingRecord` (table `findings`, lines 108-136): the
    only identity column is `id: int | None = Field(default=None, primary_key=True)` (autoincrement
    PK). There is no UUID column anywhere on `FindingRecord` — no `public_id`, no `uuid` field, nothing
    a read-only query in `read.py` could select instead of `finding.id`.
  - Conclusion: this is a genuine cross-task schema/model gap, not a `read.py` bug. `read.py` (Task 6)
    cannot return a contract-valid `FindingRead.finding_id` because the row it reads
    (`FindingRecord`) was never given a UUID column by whichever task owns `models/persistence.py`
    (Task 1, per Task 6's stated dependency). Per instructions, stopping rather than fabricating a
    UUID (e.g. wrapping the int, generating a random UUID per response, or hashing) — any of those
    would either be non-stable across requests or silently diverge from whatever the eventual real fix
    (adding a UUID column to `findings` + a migration) does.

**Decisions Made**:
- Fixed bug #2 in place since it was a legitimate, self-contained `read.py` query-ordering fix within
  Task 6's target file.
- Left bug #1 unfixed and am reporting it as a cross-task gap: `FindingRecord` needs a UUID identity
  column (e.g. `finding_id: UUID = Field(default_factory=uuid4, unique=True, index=True)`) plus a
  migration, which is out of scope for `backend/src/api/services/read.py` and belongs to the
  task(s) owning `backend/src/api/models/persistence.py` / the alembic migrations (Task 1's territory
  per the Task 6 dependency line). Did not touch `schemas/read.py` or `models/persistence.py`.

**Code Changed**:
- Modified: `backend/src/api/services/read.py`

## Task 13: FindingRecord durable finding_id UUID + migration

**Order Given**: Add a durable UUID identity to `FindingRecord` (finding_id, unique+indexed, uuid4 default) and a chained alembic migration 06 (off 05) that adds the column nullable, backfills with `gen_random_uuid()`, sets NOT NULL, adds unique+index; downgrade reverses. Extend the migration test suite to cover it.

**What, How, and Why**: Added `finding_id: UUID = Field(default_factory=uuid4, unique=True, index=True)` to `FindingRecord` right after the existing int `id` PK, matching the file's existing UUID import and Field style. Wrote `20260722_06_finding_uuid.py` mirroring the structure of `20260722_05_host_identity.py`: `add_column` nullable, `op.execute` backfill via `gen_random_uuid()`, `alter_column` to NOT NULL, then two `create_index` calls (one `unique=True` for the uniqueness constraint, one plain index) — used `create_index(unique=True)` instead of `create_unique_constraint` because the migration test harness's `_record` helper only monkeypatches a fixed `OP_METHODS` list that doesn't include `create_unique_constraint`/`drop_constraint` for this style, and the existing `05` migration already establishes `create_index(unique=True)` as the project's convention for unique constraints in alembic migrations. Downgrade drops both indexes then the column.

**Decisions Made**: Used `create_index(..., unique=True)` rather than a real `UNIQUE CONSTRAINT` to stay consistent with the pattern already used for `uq_hosts_org_identity` in migration 05, and because it plugged directly into the existing test harness's `OP_METHODS` allowlist without needing to touch the shared test file's infra. No RLS/grant statements added since `findings` already has its RLS story handled elsewhere (task scope limited to the UUID column per Task 13 spec, which doesn't mention RLS for this migration).

**Code Changed**:
- Modified: `backend/src/api/models/persistence.py`
- Created: `backend/alembic/versions/20260722_06_finding_uuid.py`
- Modified: `backend/tests/test_host_identity_migration.py`

## Review: Task 13 — FindingRecord durable `finding_id` UUID + migration

**Order Given**: Review Task 13 of feature 015-read-path as the authoritative gate. Verify FindingRecord.finding_id UUID field, alembic migration 06 (chained off 05, nullable→backfill→NOT NULL→unique+index, clean downgrade), and migration test coverage. Run ruff + pytest gates in backend/.

**What, How, and Why**:
- Read `specs/015-read-path/TASKS.md` Task 13 section for success criteria and target files.
- Read `backend/alembic/versions/20260722_05_host_identity.py` and `20260722_06_finding_uuid.py` to verify the revision chain (`06.down_revision == "20260722_05"` == `05.revision`) and migration correctness.
- Read `backend/src/api/models/persistence.py` (FindingRecord and neighboring models) to verify the new `finding_id` field and confirm precedent for `unique=True, index=True` fields elsewhere in the codebase (`nvd_cache.query_key`, `invites.token_hash`) — both use a single unique index, not two.
- Read `backend/tests/test_host_identity_migration.py` migration-06 test.
- Ran `uv run ruff check` on the three changed/added files: clean.
- Ran `uv run pytest --ignore=tests/test_worker_startup.py` in backend/: 68 passed, 16 skipped, 3 failed — all 3 failures are the pre-authorized `test_settings.py` env-leak failures (nvd_api_key, carried_fields_default, missing_database_url). No new failures.
- Ran the migration-06 test in isolation: passed.

**Decisions Made**: REJECT. All functional success criteria are met (model field correct, int PK retained, migration chain unbroken, backfill/NOT NULL/unique/index sequence correct, downgrade reverses, test coverage present, gates green modulo pre-authorized failures). However, migration 06 creates two separate indexes (`uq_findings_finding_id` unique + `ix_findings_finding_id` non-unique) on the identical single column `finding_id`, which is redundant — the unique index alone satisfies both uniqueness and lookup-index needs, per the codebase's own established pattern for `unique=True, index=True` SQLModel fields elsewhere (baseline and identity-schema migrations use one index). This is over-engineering (duplicate/dead index) under ultra strictness and must be cut before approval, along with the matching test assertions.

**Code Reviewed**:
- backend/src/api/models/persistence.py
- backend/alembic/versions/20260722_06_finding_uuid.py
- backend/alembic/versions/20260722_05_host_identity.py
- backend/tests/test_host_identity_migration.py

## Fix: Task 13 — remove redundant `ix_findings_finding_id` index

**Order Given**: Fix the REJECTED Task 13 per the reviewer's exact instructions — delete the redundant `ix_findings_finding_id` create_index/drop_index pair from migration 06, drop the matching test assertions, and check whether `FindingRecord.finding_id`'s SQLModel `Field(unique=True, index=True)` should be aligned with precedent.

**What, How, and Why**: In `backend/alembic/versions/20260722_06_finding_uuid.py`, deleted the `op.create_index("ix_findings_finding_id", ...)` call in `upgrade()` and its matching `op.drop_index("ix_findings_finding_id", ...)` in `downgrade()`, keeping only the `uq_findings_finding_id` unique index. In `backend/tests/test_host_identity_migration.py`, removed the two `ix_findings_finding_id` assertions and narrowed `dropped_indexes` to `{"uq_findings_finding_id"}`. Checked the cited precedent fields (`nvd_cache.query_key` at persistence.py:161, `invites.token_hash` at identity.py:46) — both declare `Field(unique=True, index=True)` at the SQLModel level, identical to `FindingRecord.finding_id` (persistence.py:113). SQLModel's `unique=True, index=True` combination generates a single unique index (one physical index, not two), unlike the migration which had explicitly issued two separate `create_index` calls — so the ORM field declaration was never the source of the redundancy and needed no change.

**Decisions Made**: Left `persistence.py` untouched since `finding_id`'s Field declaration already matches the precedent pattern exactly; the redundancy was isolated to the raw alembic migration issuing two `create_index` calls on the same column, which is now fixed to one.

**Code Changed**:
- Modified: `backend/alembic/versions/20260722_06_finding_uuid.py`
- Modified: `backend/tests/test_host_identity_migration.py`

## Re-review: Task 13 (post-rejection fix)

**Order Given**: Re-review Task 13 of feature 015-read-path after the prior rejection fix (redundant `ix_findings_finding_id` index removed alongside the unique `uq_findings_finding_id`). Authoritative gate.

**What, How, and Why**:
- Read `specs/015-read-path/TASKS.md` Task 13 section to confirm Success Criteria.
- Read `backend/alembic/versions/20260722_06_finding_uuid.py`: upgrade adds nullable `finding_id` column, backfills via `gen_random_uuid()`, sets NOT NULL, creates exactly one index (`uq_findings_finding_id`, unique=True); downgrade drops that one index then the column. Confirms only one index is created — prior redundancy is gone.
- Confirmed `FindingRecord.finding_id` in `backend/src/api/models/persistence.py` (line 113) uses `Field(default_factory=uuid4, unique=True, index=True)`, matching the cited precedent `nvd_cache.query_key: str = Field(unique=True, index=True)` (line 161) — SQLModel/SQLAlchemy collapses `unique=True, index=True` into one unique index, not two.
- Read `backend/tests/test_host_identity_migration.py::test_migration_06_adds_finding_uuid`: asserts nullable add, backfill statement present, NOT NULL alter, exactly one created index (`uq_findings_finding_id`, unique), and downgrade's dropped index set equals `{"uq_findings_finding_id"}` only.
- Ran `uv run ruff check` on the three target files — all checks passed.
- Ran `uv run pytest tests/test_host_identity_migration.py -q` — 5 passed.
- Ran `uv run pytest --ignore=tests/test_worker_startup.py -q` (full non-hanging suite) — 68 passed, 16 skipped, 3 failed, all three failures in `tests/test_settings.py` (`test_missing_database_url_raises`, `test_carried_fields_default_when_env_unset`, `test_missing_database_url_fails_before_engine_construction`), matching the pre-authorized env-leak failures exactly.
- Checked `git status`/diff scope: only the three Target Files touched (`persistence.py` modified; migration + test file new/untracked). No orchestrator/`ScanRunner`/`ScanProgressScreen` parameter involved — CLAUDE.md integration rule not applicable to this schema/migration task.
- Grepped for `# ponytail:` markers in the touched files — none present.

**Decisions Made**: APPROVE. The rejection fix correctly removed the redundant `create_index`/`drop_index` pair and the corresponding test assertions; the migration now creates exactly one unique index, chains off `20260722_05`, and correctly does backfill + NOT NULL + downgrade. Model field already matched precedent and needed no change. Gates green (ruff clean, targeted and full test suite pass modulo pre-authorized env-leak failures). No `# ponytail:` markers to strip.

**Code Reviewed**:
- `backend/src/api/models/persistence.py`
- `backend/alembic/versions/20260722_06_finding_uuid.py`
- `backend/tests/test_host_identity_migration.py`
- `specs/015-read-path/TASKS.md` (Task 13 section)

## Task 6 fix attempt 2 (post-Task 13 unblock)

**Order Given**: Finish the REJECTED Task 6 of `015-read-path`. Bug #2 (latest-observation
ordering) was already fixed. Bug #1 (blocking, `int`→`UUID` `ValidationError` on
`FindingRead.finding_id`) is now unblocked by Task 13's durable `finding_id: UUID` column on
`FindingRecord`. Fix only `backend/src/api/services/read.py`: map `finding_id=finding.finding_id`
instead of `finding.id` in `_to_finding_read`; confirm bug #2's fix is still in place; re-check every
`FindingRead` field mapping against `schemas/read.py`/`models/persistence.py` for other type
mismatches.

**What, How, and Why**:
- Confirmed `FindingRecord.finding_id: UUID = Field(default_factory=uuid4, unique=True, index=True)`
  exists on `backend/src/api/models/persistence.py` (line 113), added by Task 13.
- Changed the single line in `_to_finding_read` (`backend/src/api/services/read.py`) from
  `finding_id=finding.id` to `finding_id=finding.finding_id`, resolving the reviewer-cited
  `ValidationError`.
- Confirmed bug #2's fix is intact: `get_host_detail`'s `latest_scan_host` query still joins
  `ScanRecord` and orders by `ScanRecord.timestamp.desc()`, not `ScanHostRecord.created_at` —
  untouched by this fix.
- Cross-checked every other `FindingRead` field against `FindingRecord`: `scan_id` (UUID→UUID),
  `host_id` (resolved `UUID | None` from the join, matches optional `UUID | None`), `host_ip`
  (`finding.ip: str | None` → `IPvAnyAddress | None`, pydantic coerces string IPs), `port`
  (`int | None`→`int | None`), `protocol`/`service`/`source`/`source_script`/`cve_id` (`str | None`
  each side), `cvss_score` (`float | None`), `severity` (`str`→`Severity` literal, pydantic
  validates), `title`/`description`/`recommendation`/`evidence` (`str`→`constr`), `references`
  (`finding.references_json: list[str]`→`references: list[constr]`), `detected_at`
  (`finding.created_at: datetime`→`datetime`) — no other mismatches found.

**Decisions Made**: Single-line fix only, per the reviewer's own conclusion that this was purely a
missing-column gap now resolved by Task 13; no other `read.py` change was warranted.

**Code Changed**:
- Modified: `backend/src/api/services/read.py`

## Review: Task 6 (re-review after fixes)

**Order Given**: Re-review Task 6 of 015-read-path after fixes for prior REJECT (finding_id int→UUID mismatch; get_host_detail latest-observation ordering by wrong timestamp column). Authoritative gate.

**What, How, and Why**: Read `specs/015-read-path/TASKS.md` Task 6 section, `backend/src/api/schemas/read.py`, `backend/src/api/models/persistence.py`, and the full `backend/src/api/services/read.py`. Verified bug #1 fix: `_to_finding_read` now maps `finding_id=finding.finding_id`, the durable UUID column (`FindingRecord.finding_id: UUID`, added in Task 13), not the int PK — resolves the prior ValidationError. Verified bug #2 fix: `get_host_detail`'s latest-observation query now joins `ScanRecord` on `ScanHostRecord.scan_id == ScanRecord.scan_id` and orders by `ScanRecord.timestamp.desc()` (was previously ordering by `ScanHostRecord.created_at`). Checked all four functions (`list_hosts`, `get_host_detail`, `get_scan_detail`, `list_findings`) build valid `schemas/read.py` models with correct field mappings and no residual type mismatches. Confirmed `list_findings`'s host-scoped join (`FindingRecord.scan_host_id → ScanHostRecord.id`, filtered `ScanHostRecord.host_id == host_id`) and the unscoped path's outer join with null-safe `host_id` passthrough. Confirmed `get_scan_detail` maps `host_id=scan_host.host_id` per row and reads `scan_mode`/`status` directly from `ScanRecord` with no vocabulary translation. Ran `uv run ruff check src/api/services/read.py` in `backend/` → all checks passed. Ran `uv run pytest --ignore=tests/test_worker_startup.py -q` in `backend/` → 68 passed, 16 skipped, 3 failed (all three in `tests/test_settings.py`, the pre-authorized env-leak failures per the task instructions, unrelated to Task 6). No `# ponytail:` markers present in `services/read.py` to strip.

**Decisions Made**: APPROVE. Both previously identified bugs are correctly fixed. No new correctness issues found; no over-engineering (functions are minimal, no dead abstractions, no unrequested flexibility). Behavioral/endpoint test coverage is explicitly out of scope for Task 6 per instructions (Task 7's job). Gate commands run as specified; only the pre-authorized failures present.

**Code Reviewed**: `backend/src/api/services/read.py`, `backend/src/api/schemas/read.py`, `backend/src/api/models/persistence.py`, `specs/015-read-path/TASKS.md`.

## Task 7: Routers + app mount + endpoint tests

**Order Given**: Implement Task 7 of `specs/015-read-path/TASKS.md` — add `routers/hosts.py`, `routers/scans.py`, `routers/findings.py` (plus `routers/__init__.py`) wrapping the Task 6 read-service functions, mount them in `main.py`, add `tests/test_read_endpoints.py` (mirroring `test_health.py`'s `TestClient` + `dependency_overrides` pattern, no real DB), and update `test_health.py` for the new route surface.

**What, How, and Why**: Read the Task 7 section, the ARCHITECTURE naming-table router rows and the "main.py mount + existing-test note", `backend/src/api/main.py`, `services/read.py`, `schemas/read.py`, `models/persistence.py`, and `tests/test_health.py`. Added `routers/hosts.py` (`GET /api/v1/hosts` → `list_hosts`, `GET /api/v1/hosts/{host_id}` → `get_host_detail`, 404 on `None`), `routers/scans.py` (`GET /api/v1/scans/{scan_id}` → `get_scan_detail`, 404 on `None`), `routers/findings.py` (`GET /api/v1/findings?host_id=` → `list_findings`), each depending on `Session = Depends(get_session)` per the existing `read_health` pattern (no auth dependency added — none exists yet to wrap). Mounted all three via `app.include_router(...)` in `main.py`, matching the naming table's "Touch" instruction. Updated `test_health.py`: dropped `/api/v1/findings` from `DISCARDED_BUSINESS_PATHS` (now a real mounted route) while keeping bare `/api/v1/scans` (list is out of scope); flipped `test_routers_package_is_not_importable` to `test_routers_package_is_importable`; rewrote the route-surface assertion to expect all five GET routes. Wrote `tests/test_read_endpoints.py` using an in-memory SQLite engine (`SQLModel.metadata.create_all`) injected via `app.dependency_overrides[get_session]`, seeding one scan/host/scan_host/port/service/finding row and asserting: 200 + correct shape for all four endpoints; 404 for unknown `host_id`/`scan_id`; `GET /findings?host_id=` scoped to that host with its `highest_severity` present among returned findings' severities; scan-detail host rows carrying `host_id`; and the specified contract-shape fields (`first_seen_at`, `last_seen_at`, `host_id`) appear in each payload.

**Decisions Made**: Discovered during verification that installed FastAPI (0.139.0) no longer flattens included sub-router routes into `app.routes` as `APIRoute` instances directly — they're wrapped in lazy `_IncludedRouter` objects — so the original `test_health.py` route-surface assertion (`isinstance(route, APIRoute)` over `app.routes`) silently found only `/api/v1/health`; added a small `_flatten_api_routes` recursive helper in the test to walk `original_router.routes` and restore an accurate assertion, since this is orthogonal to Task 7's actual scope but required to make the existing-test update true to its stated intent. Also found the SQLite `sqlite://` in-memory engine opens a fresh empty database per connection unless pinned to a single connection; added `poolclass=StaticPool` to the test fixture's `create_engine` call so `create_all` and the request-scoped session share the same in-memory database — a one-line, well-known SQLAlchemy fix, not a new dependency. No `# ponytail:` markers needed — every line traces directly to a named success criterion.

**Code Changed**:
- Created: `backend/src/api/routers/__init__.py`
- Created: `backend/src/api/routers/hosts.py`
- Created: `backend/src/api/routers/scans.py`
- Created: `backend/src/api/routers/findings.py`
- Created: `backend/tests/test_read_endpoints.py`
- Modified: `backend/src/api/main.py`
- Modified: `backend/tests/test_health.py`

## Test Verification: Task 7 (test-writer pass)

**Order Given**: Strengthen/verify pytest tests for Task 7 (read routers + endpoint tests). Confirm the existing `test_read_endpoints.py` and `test_health.py` (already written by the coder) genuinely exercise behavior against the full Success-Criteria matrix, scrutinize `_flatten_api_routes` for legitimacy, add any missing cases, run the suite, and log results. Tests only.

**What, How, and Why**: Read Task 7's Success Criteria, `test_read_endpoints.py`, `test_health.py`, and all three routers (`hosts.py`, `scans.py`, `findings.py`). Confirmed the existing single-host fixture proved 200-shape and 404 paths but could not prove `/findings?host_id=` actually *filters* (only one host existed, so an unfiltered bug would have passed unnoticed) and that scan-detail host rows carry `host_id` correctly across multiple hosts. Extended `_seed()` in `test_read_endpoints.py` with a second host/scan_host/finding (`other_host`, `other_finding`) sharing the same scan, then: strengthened `test_list_hosts_happy_path` to assert both hosts are present and to compare `first_seen_at` against the exact seeded `isoformat()` value (not just presence); strengthened `test_get_host_by_id_happy_path` to assert exact `first_seen_at`/`last_seen_at` values and scan-history contents; strengthened `test_get_scan_by_id_happy_path` to assert both hosts' `host_id`s appear in `hosts` and both appear in `findings`; rewrote `test_list_findings_filtered_by_host_id` to assert the filtered result excludes `other_host`'s `host_id` and `other_finding`'s `finding_id` (proving real filtering, not a coincidental single-row match); added `test_list_findings_unfiltered_returns_all_hosts` to cover the no-filter branch, which wasn't covered before. Verified `_flatten_api_routes` empirically: called `TestClient(app).get("/api/v1/hosts")` with no `dependency_overrides`, which reached `get_session` and raised a real `psycopg.OperationalError` attempting to connect to Postgres — proving the router is actually mounted and reachable (a routing/mount bug would 404 before ever touching the DB dependency), confirming the helper is a legitimate FastAPI-0.139 `_IncludedRouter`-unwrapping adaptation, not a workaround masking a broken mount.

**Decisions Made**: Kept the fake-session/SQLite boundary as-is (no DB mocking added beyond the coder's existing in-memory `StaticPool` fixture) since that's the correct unit boundary per CLAUDE.md's testability guidance. Chose to add a second host/finding at the fixture level rather than a separate fixture, to keep `_seed()` as the single source of truth and mirror the existing style. Did not add tests for pagination (`page`/`per_page` params on `list_hosts`) or the host-detail `ports`/`scan_history` deep shape beyond scan_id, since Task 7's Success Criteria don't name those and the existing scope is routers + endpoint tests, not exhaustive service-layer re-verification (already covered in Task 6). No production code changed.

**Code Changed**:
- Modified: `backend/tests/test_read_endpoints.py`

## Review: Task 7 — Routers + app mount + endpoint tests

**Order Given**: Review Task 7 of feature 015-read-path (routers/__init__.py, hosts.py, scans.py, findings.py, main.py mount, test_read_endpoints.py, test_health.py update) as authoritative gate.

**What, How, and Why**: Read TASKS.md Task 7 section, ARCHITECTURE.md router rows and main.py mount note, schemas/read.py, services/read.py (both pre-existing from Tasks 5/6). Read all Task 7 target files. Verified the four endpoints (GET /hosts, /hosts/{id}, /scans/{id}, /findings) each use Depends(get_session), return correct schemas, and 404 on unknown ids via HTTPException. Verified findings router accepts host_id query param and filters correctly per service layer (already reviewed logic in services/read.py). Confirmed main.py mounts all three routers via app.include_router. Inspected test_read_endpoints.py: seeds two hosts/scans/findings, asserts happy paths, 404s, host_id filter isolation, and highest_severity presence — all present. Inspected test_health.py: DISCARDED_BUSINESS_PATHS updated to drop /api/v1/findings (now mounted) while keeping bare /api/v1/scans (still unmounted, correct); route-surface assertion lists all 5 expected paths; test_routers_package_is_importable added. Independently verified (via `uv run python -c`) that FastAPI 0.139 wraps included routers in `_IncludedRouter` objects with a `.original_router.routes` attribute, confirming `_flatten_api_routes` genuinely unwraps real mounted routes rather than masking a mount bug — routes are reachable via TestClient in test_read_endpoints.py, not merely introspectable. Ran `uv run ruff check` on all touched files — clean. Ran `uv run pytest --ignore=tests/test_worker_startup.py -q` — 3 failures, all in test_settings.py (nvd_api_key env leak), matching the explicitly pre-authorized failures; all read-endpoint and health tests pass (12 passed, 1 skipped when run in isolation). No `# ponytail:` markers found in touched files.

**Decisions Made**: APPROVE. All Success Criteria met: four endpoints wired correctly, 404s work, findings host_id filter isolates correctly with highest_severity visible, scan-detail rows carry host_id, contract-shape assertions present, test_health.py correctly reflects new route surface, and the _flatten_api_routes helper was verified against real FastAPI 0.139 internals rather than trusted blindly. No integration-rule concern (no new orchestrator/runner parameter in this task). Code is minimal — thin routers delegating to services/read.py, no unrequested abstractions, auth-wrappable structure achieved simply via undecorated Depends(get_session) with no premature auth logic.

**Code Reviewed**:
- backend/src/api/routers/__init__.py
- backend/src/api/routers/hosts.py
- backend/src/api/routers/scans.py
- backend/src/api/routers/findings.py
- backend/src/api/main.py
- backend/tests/test_read_endpoints.py
- backend/tests/test_health.py
- backend/src/api/schemas/read.py (context, pre-existing)
- backend/src/api/services/read.py (context, pre-existing)

## Task 8: Contract deltas — openapi.yaml + example

**Order Given**: Implement Task 8 (standalone, no deps): apply ADR-013 renames, C6, and C9 to `contracts/openapi/openapi.yaml`, and update `contracts/examples/scan_result.example.json` to match.

**What, How, and Why**: In openapi.yaml, renamed `ScanIngestRequest.devices` to `hosts` (property + required entry), renamed the `DevicePayload` component to `HostPayload` (definition and its remaining `$ref` in `ScanIngestRequest.hosts.items`), and renamed `ScanIngestAcceptedResponse.devices_received` to `hosts_received` (property, required entry, and the 202 example value). Added `first_seen_at` (string/date-time) to `HostSummary.properties` and `HostSummary.required` per C6. Added a new `ScanHostView` component (HostPayload's fields plus required `host_id: uuid`, `additionalProperties: false`) per C9, and repointed `ScanDetailResponse.hosts.items` to `$ref` it instead of `DevicePayload`, updating the adjacent description text to reference `HostPayload`/`ScanHostView` correctly. Also updated two example/prose leftovers referencing the old `devices` field name: the ingest error-example `field: devices[0].ip` → `hosts[0].ip`, and the `ScanIngestRequestExample` shared example's `devices:` list → `hosts:`. In the example JSON, replaced `target_mode`/`scan_profile` with `scan_mode: "standard"` and renamed the `devices` array to `hosts`.

**Decisions Made**: Left `HostPayload` field-for-field identical to the old `DevicePayload` (only the component name changed), per the explicit instruction that HostPayload stays unchanged apart from the rename. `ScanHostView` is response-only and structurally duplicates HostPayload's five fields plus `host_id`, rather than trying to compose it via allOf, since the task called for it to have `additionalProperties: false` and a flat required list, which is simplest expressed as its own definition. Updated the two prose/example spots still saying `devices` (error example `field`, and `ScanIngestRequestExample`) even though not explicitly named as required renames, because leaving stale field names in shared examples would make the example fail its own schema (`ScanIngestRequestExample` is literally validated against `ScanIngestRequest`, which now requires `hosts`).

**Code Changed**:
- Modified: `contracts/openapi/openapi.yaml`
- Modified: `contracts/examples/scan_result.example.json`

## Task 8: Contract deltas — openapi.yaml + example (tests)

### Order Given
Handle test coverage for Task 8 of feature 015-read-path (contract deltas: contracts/openapi/openapi.yaml + contracts/examples/scan_result.example.json), per the orchestrator's search-first-then-extend instructions.

### What, How, and Why
Searched for existing contract-validating tests and found two: `hardware-agent/tests/test_contract_models.py` (parses `contracts/openapi/openapi.yaml` with `yaml.safe_load` and asserts on schema shape) and `backend/tests/test_ingest_scan.py` (loads `contracts/examples/scan_result.example.json` and validates it via `ScanResult.model_validate`, exercising the backend ingest schema end-to-end). Confirmed the openapi.yaml and example file already contain the Task 8 deltas (no `DevicePayload`/`devices_received`, `HostSummary.required` includes `first_seen_at`, `ScanHostView` exists with required `host_id` and `ScanDetailResponse.hosts.items` refs it, example uses `scan_mode`/`hosts`). Extended `hardware-agent/tests/test_contract_models.py` — the closer match for direct openapi.yaml/example assertions — with four new tests: absence of `DevicePayload`/`devices_received` strings; `HostSummary.required` includes `first_seen_at` with `date-time` format; `ScanHostView.required` includes `host_id` (uuid) and `ScanDetailResponse.hosts.items` `$ref`s `ScanHostView`; the example JSON has `hosts`/`scan_mode` and lacks `devices`/`target_mode`/`scan_profile`. Ran `uv run pytest tests/test_contract_models.py -q` — 10 passed.

### Decisions Made
- Did not touch `backend/tests/test_ingest_scan.py` — it already exercises the example against the real backend `ScanResult` schema (Task 2/4 territory) and needed no changes for the Task 8 deltas specifically; `test_contract_models.py` is the more direct/appropriate home for openapi.yaml-shape assertions.
- No new test framework introduced; mirrored the existing `yaml.safe_load` + dict-path-assertion style already used in the file.
- Did not add a Pydantic-model-level test for `ScanHostView`/`HostPayload` since those Python contract models belong to Task 9 (Pi `contracts.py` rename), out of scope here.

### Code Changed
- hardware-agent/tests/test_contract_models.py

## Task 8 Review — Contract deltas (openapi.yaml + example)

**Order Given**: Review Task 8 of feature 015-read-path as authoritative gate. Verify openapi.yaml has no remaining DevicePayload/devices_received/ScanIngestRequest.devices references; HostSummary.required includes first_seen_at; ScanHostView exists with required host_id (uuid, additionalProperties:false) and ScanDetailResponse.hosts.items refs it; HostPayload unchanged apart from rename; example uses scan_mode + hosts; YAML parses and example validates; run contract tests in hardware-agent/ and backend/; ruff check on touched test file.

**What, How, and Why**:
- Read TASKS.md Task 8 section, ARCHITECTURE.md "Contract deltas" section, and ADR-013 for context.
- Grepped openapi.yaml for `DevicePayload`, `devices_received`, `ScanIngestRequest.devices` — zero hits (only legitimate `ScanHostView`, `HostPayload`, `hosts_received` remain).
- Inspected `HostSummary` schema: `first_seen_at` present in both `properties` and `required`, format `date-time`.
- Inspected `ScanHostView`: `additionalProperties: false`, `required` includes `host_id` (uuid) plus HostPayload fields; `ScanDetailResponse.hosts.items` correctly `$ref`s `ScanHostView`. `HostPayload` itself confirmed unchanged apart from rename (still used by `ScanIngestRequest.hosts`).
- Inspected `scan_result.example.json`: uses `scan_mode` + `hosts`, no `target_mode`/`scan_profile`/`devices`.
- Parsed YAML with PyYAML (`uv run --with pyyaml`) — parses cleanly.
- Validated example against `ScanIngestRequest` schema with `jsonschema` (`uv run --with jsonschema --with pyyaml`) — validation raised on `metadata.additionalProperties.oneOf` int/number ambiguity, confirmed via `git diff main -- contracts/openapi/openapi.yaml` that this `oneOf` block is untouched by this diff (pre-existing quirk, not a Task 8 regression); with `elapsed_seconds` popped, the example validates cleanly, confirming Task 8's actual changes (hosts/scan_mode/ScanHostView/first_seen_at) are structurally correct.
- Ran `uv run pytest tests/test_contract_models.py -q` in hardware-agent/: 10 passed (includes 4 new contract-delta tests from test-engineer, additive to Task 12's scope).
- Ran `uv run pytest tests/test_ingest_scan.py -q` in backend/: 4 skipped (no DB, as expected — no errors).
- Ran `uv run ruff check tests/test_contract_models.py` in hardware-agent/: all checks passed.
- Reviewed diff of test file for over-engineering: 4 small, direct assertion tests, no unrequested abstraction. No `# ponytail:` markers found in touched files.
- Confirmed changed files match Task 8's Target Files (`contracts/openapi/openapi.yaml`, `contracts/examples/scan_result.example.json`) plus test-engineer's additive test file.

**Decisions Made**: APPROVE. All success criteria verified directly against the spec text. The one jsonschema validation error encountered (`metadata.additionalProperties` oneOf integer/number overlap) is a pre-existing artifact untouched by this diff, not attributable to Task 8. No CLAUDE.md orchestrator-parameter integration concern applies to this contract-only task. No ponytail markers to strip.

**Code Reviewed**:
- contracts/openapi/openapi.yaml
- contracts/examples/scan_result.example.json
- hardware-agent/tests/test_contract_models.py

## Task 9: ADR-013 serialization rename in Pi contract layer

### Order Given
Implement Task 9 of `specs/015-read-path/TASKS.md`: in
`hardware-agent/src/agent/normalize/contracts.py`, rename `DevicePayload`→`HostPayload`
and `ScanPayload.devices`→`ScanPayload.hosts: list[HostPayload]`; in
`hardware-agent/src/agent/normalize/__init__.py`, re-export `HostPayload` in place of
`DevicePayload`. Producers, TUI read-sites, and Pi test files are intentionally left
referencing the old names (Tasks 10-12) and are pre-authorized to break.

### What, How, and Why
- Renamed the `DevicePayload` pydantic model to `HostPayload` in contracts.py, matching
  ADR-013's vocabulary unification (device → host).
- Renamed `ScanPayload.devices` field to `ScanPayload.hosts`, typed as `list[HostPayload]`.
- Updated `normalize/__init__.py` imports and `__all__` to export `HostPayload` instead of
  `DevicePayload`.
- Did not touch `scanner/stages.py`, `scanner/runner.py`, TUI read-sites, or Pi test files —
  out of scope per Task 9 and explicitly deferred to Tasks 10-12.

### Decisions Made
- Pure rename, no behavior change; no ponytail markers needed since this is a mechanical
  contract rename with no simplification tradeoffs.

### Code Changed
- Modified: `hardware-agent/src/agent/normalize/contracts.py`
- Modified: `hardware-agent/src/agent/normalize/__init__.py`

## Task 10: Pi producers — stages + runner

### Order Given
Rename Pi-side scan payload producers per ARCHITECTURE "Rename blast radius": `stages.build_device_payload(host) -> DevicePayload` becomes `build_host_payload(host) -> HostPayload`; `runner.py` must build `hosts` (not `devices`) and construct `ScanPayload(hosts=...)`.

### What, How, and Why
Renamed the function and its return type annotation in `scanner/stages.py`, importing `HostPayload` from `agent.normalize.contracts` (already renamed in Task 9) instead of `DevicePayload`. In `scanner/runner.py`, renamed the local `devices` list to `hosts_payload` (kept distinct from the existing `hosts: list[HostInfo]` parameter already in scope) and passed it as `ScanPayload(hosts=hosts_payload, ...)`. This keeps the Pi producer naming consistent with the renamed `HostPayload`/`ScanPayload.hosts` contract from Task 9.

### Decisions Made
- Named the runner's local variable `hosts_payload` rather than `hosts` to avoid shadowing the existing `hosts: list[HostInfo]` argument in `_build_payload`.

### Code Changed
- Modified: `hardware-agent/src/agent/scanner/stages.py`
- Modified: `hardware-agent/src/agent/scanner/runner.py`

## Task 11: Pi TUI screens — read-site rename

### Order Given
Rename every `payload.devices` read to `payload.hosts` in the three Pi TUI screens (scan_view.py: 3, scan_progress.py: 3, home.py: 2), field name only, display logic unchanged.

### What, How, and Why
Grepped each target file for `.devices`, confirmed exactly the counts specified in TASKS.md, then did a straight text substitution of `payload.devices` -> `payload.hosts` in the three files. No other logic touched.

### Decisions Made
Used a scoped regex substitution restricted to the literal `payload.devices` attribute access to avoid touching unrelated `.devices` usages (none existed) or any display/formatting code.

### Code Changed
- Modified: hardware-agent/src/agent/tui/screens/scan_view.py
- Modified: hardware-agent/src/agent/tui/screens/scan_progress.py
- Modified: hardware-agent/src/agent/tui/screens/home.py

## Task 12: Pi tests — rename mirror set

### Order Given
Apply the field/keyword rename across the nine Pi test files per ARCHITECTURE naming
table (Pi test rows): `DevicePayload`→`HostPayload` imports/usage, `.devices`→`.hosts`
assertions, `ScanPayload(devices=[...])` keyword → `hosts=[...]`, and
`build_device_payload`→`build_host_payload` references. Extend
`test_contract_models.py` with the three new contract-rename assertions (import from
both modules, `hosts` accepts a `HostPayload` list, `devices=` keyword no longer
populates the model). Gate: `uv run pytest` and `uv run ruff check` both green in
`hardware-agent/`.

### What, How, and Why
- Grepped all nine target files for `devices`/`DevicePayload`/`build_device_payload`
  first, confirmed no other non-target file in `hardware-agent/` still referenced the
  old names (source was already renamed by earlier tasks).
- Renamed `DevicePayload`→`HostPayload` in imports and constructors, `.devices`→
  `.hosts` in assertions, `devices=`→`hosts=` in keyword construction, and
  `build_device_payload`→`build_host_payload` (import + call) in
  `test_extensive_e2e.py`. Used `perl -pi` instead of BSD `sed` since `\b` word
  boundaries aren't supported by macOS `sed`.
- Left unrelated occurrences of the word "devices" untouched: test function names
  describing behavior (`test_zero_hosts_has_no_devices`), UI copy assertions ("Total
  devices:", "Done — 2 devices, ..."), and the openapi negative assertions that check
  `"DevicePayload"`/`"devices"` are absent from the spec/example (those stay as literal
  strings, not payload field references).
- Fixed `tests/unit/test_workspace.py::test_written_json_is_valid`, which asserted
  `data["devices"]` against the serialized `ScanPayload` JSON — that key is now
  `data["hosts"]`.
- Re-sorted the `from agent.normalize.contracts import (...)` blocks alphabetically
  (`FindingPayload` before `HostPayload`) in the three files where the mechanical
  rename put `HostPayload` first, to keep ruff's import-sort rule green.
- Added three tests to `test_contract_models.py` per the ARCHITECTURE guidance
  (lines 496-503): `HostPayload` importable from both `agent.normalize.contracts` and
  `agent.normalize`; `ScanPayload.hosts` accepts a `HostPayload` list; and — since
  `ScanPayload` has no `extra="forbid"` model config, so pydantic silently drops
  unknown kwargs rather than raising — the ARCHITECTURE-sanctioned fallback: assert a
  `devices=` keyword leaves `payload.hosts == []` and the payload has no `devices`
  attribute, rather than requiring a `TypeError`.

### Decisions Made
- Did not add `extra="forbid"` to `ScanPayload`'s model config to make `devices=`
  raise `TypeError` — out of scope for a test-only rename task, and ARCHITECTURE
  explicitly offers the "extra kwargs tolerated" fallback assertion as an
  alternative, which is what pydantic's default behavior requires here.
- Left the `devices` local variable name in `test_scan_progress_screen.py`'s
  `_make_payload` helper — it's assigned to the `hosts=` keyword on construction;
  renaming a purely local variable wasn't part of the rename's success criteria
  and constitutes a non-required beautification.

### Code Changed
- Modified: `hardware-agent/tests/test_contract_models.py`
- Modified: `hardware-agent/tests/unit/test_tui_scan_view.py`
- Modified: `hardware-agent/tests/unit/test_headless.py`
- Modified: `hardware-agent/tests/unit/test_scan_runner_partial.py`
- Modified: `hardware-agent/tests/unit/test_scan_runner_cancel.py`
- Modified: `hardware-agent/tests/unit/test_scan_progress_screen.py`
- Modified: `hardware-agent/tests/integration/test_tui_flows.py`
- Modified: `hardware-agent/tests/unit/test_workspace.py`
- Modified: `hardware-agent/tests/unit/test_quick_mode_argv.py`
- Modified: `hardware-agent/tests/integration/test_extensive_e2e.py`

## Tasks 9-12: ADR-013 Pi rename front (contracts, producers, TUI screens, tests)

### Order Given
Review Tasks 9, 10, 11, 12 of `specs/015-read-path/TASKS.md` together as a unit
(authoritative gate). Verify against ARCHITECTURE.md "Rename blast radius" / Pi
naming table rows and ADR-013. Run `uv run pytest` and `uv run ruff check` in
`hardware-agent/`, global grep for leftover `DevicePayload`/`build_device_payload`/
`ScanPayload(devices`/`.devices` on ScanPayload, confirm Task 8 contract-delta
tests remain, and append this POOP.md entry.

### What, How, and Why
- Read `hardware-agent/src/agent/normalize/contracts.py`: `HostPayload` model
  present, `ScanPayload.hosts: list[HostPayload]`, no `DevicePayload` remaining.
- Read `hardware-agent/src/agent/normalize/__init__.py`: re-exports `HostPayload`
  (not `DevicePayload`).
- Grepped `scanner/stages.py` / `scanner/runner.py`: `build_host_payload` is the
  sole producer name; `runner.py` constructs `ScanPayload(hosts=hosts_payload, ...)`.
- Grepped `tui/screens/{scan_view,scan_progress,home}.py`: all reads are
  `payload.hosts`, no `payload.devices` left.
- Grepped all of `src/` and `tests/` for `DevicePayload`, `build_device_payload`,
  `ScanPayload(devices`, `payload.devices`: only hit was the intentional
  negative-assertion string `"DevicePayload" not in text` in
  `tests/test_contract_models.py` (openapi-drift guard, pre-existing pattern from
  Task 8) — no leaks.
- Confirmed `test_contract_models.py` has: `test_host_payload_importable_from_contracts_and_normalize`,
  `test_scan_payload_hosts_accepts_host_payload_list`, and
  `test_scan_payload_rejects_devices_keyword` (asserts `hosts == []` and
  `not hasattr(payload, "devices")` when `devices=` kwarg passed — correct given
  `ScanPayload` doesn't set `extra="forbid"`, so silent-drop is the accurate,
  least-invasive behavior to assert; no unrequested `extra="forbid"` config was
  added). Task 8's contract-delta tests (`test_schema_enum_matches_pydantic_literal`,
  `test_openapi_has_no_device_payload_or_devices_received`,
  `test_scan_ingest_example_uses_hosts_not_devices`, etc.) all still present.
- Ran `uv run ruff check src/ tests/` in `hardware-agent/`: all checks passed.
- Ran `uv run pytest` in `hardware-agent/`: 503 passed, 0 failed.
- `git status --porcelain hardware-agent/` matched exactly the union of Target
  Files listed across Tasks 9-12 — no scope creep.
- Grepped for `# ponytail:` markers in touched files: none found, nothing to strip.
- No orchestrator/runner parameter was added by this front (pure rename), so the
  CLAUDE.md `ScanRunner`/`ScanProgressScreen` threading rule is not triggered.

### Decisions Made
APPROVE. All four tasks' Success Criteria verified directly against code; global
grep confirms no leftover `DevicePayload`/`build_device_payload`/old keyword/old
field access outside the one intentional negative-assertion string; full test
suite and ruff are clean; diff scope matches Target Files exactly; no
over-engineering found (straight mechanical rename, no added abstractions).

### Code Reviewed
- hardware-agent/src/agent/normalize/contracts.py
- hardware-agent/src/agent/normalize/__init__.py
- hardware-agent/src/agent/scanner/stages.py
- hardware-agent/src/agent/scanner/runner.py
- hardware-agent/src/agent/tui/screens/scan_view.py
- hardware-agent/src/agent/tui/screens/scan_progress.py
- hardware-agent/src/agent/tui/screens/home.py
- hardware-agent/tests/test_contract_models.py
- hardware-agent/tests/unit/test_tui_scan_view.py
- hardware-agent/tests/unit/test_headless.py
- hardware-agent/tests/unit/test_scan_runner_partial.py
- hardware-agent/tests/unit/test_scan_runner_cancel.py
- hardware-agent/tests/unit/test_scan_progress_screen.py
- hardware-agent/tests/integration/test_tui_flows.py
- hardware-agent/tests/unit/test_workspace.py
- hardware-agent/tests/unit/test_quick_mode_argv.py
- hardware-agent/tests/integration/test_extensive_e2e.py

---

## Docs drift (docs-sync, orchestrator mode — reported, not auto-applied)

`.claude/docs` code-map fully synced (see log.md 2026-07-22). Items left for a human decision
because they touch curated `docs/` KB or the MAINTAINING standing-facts list:

- **`.claude/docs/MAINTAINING.md` "Standing facts to preserve"** — three bullets are now partially
  superseded by this feature and should be revised by a human: (1) "backend not wired / health-only"
  → the READ path (`/api/v1/hosts`, `/hosts/{id}`, `/scans/{id}`, `/findings`) is now mounted; ingest
  POST + auth remain unwired; (2) "device ↔ host rename / devices[] frozen by ADR-011" → ADR-013 now
  retires `device` from the wire (`hosts`/`HostPayload`); (3) "contract divergence scan_mode vs
  target_mode/scan_profile" → reconciled to `scan_mode` end-to-end.
- **`docs/architecture/` + `docs/adr/ADR-011`** — may still describe the frozen `devices[]` ingest
  vocabulary; ADR-013/ADR-014 supersede this. Recommend running `architecture-adr-sync` to reconcile
  (not auto-patched: these are decision docs).
- **`backend/src/api/schemas/persistence.py`** legacy `Persisted*` models (`PersistedDevice`,
  `device_count`) are pre-existing dead code, intentionally NOT renamed by this feature.
