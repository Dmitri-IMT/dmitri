# POOP — 016-command-channel-data-model

## Task 1: Agent + Command SQLModel table models

### Order Given
Implement Task 1 from TASKS.md: create `backend/src/api/models/command.py` with `Agent` and
`Command` `table=True` SQLModel definitions exactly matching the ARCHITECTURE.md column tables,
mirroring `models/identity.py` style, and verify/wire the model-import path so the two models
register on SQLModel metadata for Alembic autogenerate. Columns only — no crypto/secret logic.

### What, How, and Why
Created `Agent` and `Command` as `SQLModel, table=True` classes matching the ARCHITECTURE.md
tables column-for-column: `Agent` has the three encrypted-secret columns
(`secret_ciphertext`/`secret_nonce` as `bytes` with `sa_type=LargeBinary`, `secret_key_version`
int), nullable `revoked_at`/`last_seen_at`, and `created_at` via `utc_now` default factory — no
`secret`/`secret_hash`/`online` column. `Command` has `org_id`/`agent_id` FKs with `index=True`,
`scan_id` FK to `scans.scan_id` with `unique=True` (NOT NULL by default since no `| None`), and
exactly four timestamps (`created_at`/`delivered_at`/`started_at`/`completed_at`), no
`uploading_at`. Followed `identity.py`'s idiom (`Field(default_factory=uuid4, primary_key=True)`,
`Field(foreign_key=...)`, `utc_now` imported from `persistence`).

Investigated the model-import path: `alembic/env.py` only imported `api.models.persistence`
directly (not the `api.models` package `__init__`), and `identity` was not imported there either
even though its migration already exists — so the existing pattern relies on whatever import
happens to run first in-process to populate the shared `SQLModel.metadata`. Added `command` (and
`identity`, which was previously missing) to the `env.py` import so all three model modules
register before Alembic autogenerate/metadata operations. Also added `command` to
`api/models/__init__.py`'s aggregator import for consistency with the existing `identity`/
`persistence` pattern used elsewhere in the app.

### Decisions Made
- Used `Field(sa_type=LargeBinary)` for the two binary secret columns since SQLModel's `bytes`
  Python type doesn't map to `LargeBinary` by default.
- Left `agent_id`/`scan_id`/`org_id` as non-Optional UUID fields (no `| None`) so SQLModel/SQLAlchemy
  infers `nullable=False`, matching the "no" Null column in the spec table without adding an
  explicit `nullable=False` kwarg (matches existing `identity.py`/`persistence.py` idiom).
- Added the previously-missing `identity` import to `alembic/env.py` alongside `command` since the
  same "not otherwise loaded" gap applied to it; this is the minimal fix to make the documented
  autogenerate path actually work for all non-`persistence` models, not just the new one.
- Wrote columns only — no crypto, no migration, no tests, per the Task 1 scope fence.

### Code Changed
- Created: `backend/src/api/models/command.py`
- Modified: `backend/src/api/models/__init__.py`
- Modified: `backend/alembic/env.py`

## Task 1 tests: Agent + Command model coverage

### Order Given
Add/adjust pytest tests for the files changed in Task 1 (`backend/src/api/models/command.py`,
`backend/src/api/models/__init__.py`, `backend/alembic/env.py`) — models-layer coverage only:
metadata registration, exact expected column set (encrypted-secret columns present, no
`secret`/`secret_hash`/`online`), exactly four timestamps with no `uploading_at`, and
`commands.scan_id` non-nullable + unique at the model/table level. DB-level migration
shape/fence/uniqueness assertions belong to Task 4's `test_command_migration.py` and were
explicitly out of scope here.

### What, How, and Why
Created `backend/tests/test_command_models.py`, a pure metadata-level test module with no DB
connection: it imports `api.models.command` and inspects `SQLModel.metadata.tables["agents"]` /
`["commands"]` directly via SQLAlchemy `Table.columns`. Tested that both tables register on the
shared metadata (proving the `__init__.py`/`env.py` import wiring works), that each table's exact
column-name set matches the ARCHITECTURE.md spec, that `agents` has no `secret`/`secret_hash`/
`online` columns, that `commands` has no `uploading_at` column, and that `commands.scan_id` has
`nullable is False` and `unique is True` on the SQLAlchemy column object. No fixtures, no DB, no
migration involved — this only proves the Python model definitions match the spec, which is a
distinct concern from Task 4's live-Postgres fence/constraint verification.

### Decisions Made
- Scoped strictly to model/metadata assertions; deliberately did not touch or duplicate
  migration round-trip, RLS fence, or live-privilege checks (Task 4's job).
- Used `SQLModel.metadata.tables[...]` + raw column introspection rather than instantiating rows,
  since Task 1 defines schema only, no persistence behavior to exercise.
- One assertion per concern (registration, column set, secret-column exclusions, timestamp set,
  scan_id nullability/uniqueness) rather than one giant combined test, to keep failures legible.
- No test needed for `alembic/env.py`'s offline/online migration functions themselves — that's
  exercised by the existing `test_migrations.py` machinery and Task 4's dedicated test file.

### Code Changed
- Created: `backend/tests/test_command_models.py`

## Review: Task 1 — Agent + Command SQLModel table models

**Order Given**: Review Task 1 of specs/016-command-channel-data-model/TASKS.md (Agent + Command SQLModel models), scoped to backend/src/api/models/command.py, backend/src/api/models/__init__.py, backend/alembic/env.py, backend/tests/test_command_models.py.

**What, How, and Why**:
- Read Task 1's Success Criteria in TASKS.md and the "Data model / contracts" section of ARCHITECTURE.md to establish the exact expected column sets for `agents` and `commands`.
- Read backend/src/api/models/command.py and diffed its columns field-by-field against the ARCHITECTURE.md tables: `agents` (id, org_id FK+index, display_name, secret_ciphertext/secret_nonce as LargeBinary, secret_key_version, revoked_at, last_seen_at, created_at) and `commands` (id, org_id FK+index, agent_id FK+index, scan_id FK→scans.scan_id NOT NULL+UNIQUE, scan_mode, subnet, status, error_code, exactly four timestamps created_at/delivered_at/started_at/completed_at, no uploading_at). Confirmed no `secret`, `secret_hash`, or `online` columns exist.
- Verified model registration: backend/src/api/models/__init__.py imports `command` alongside `identity`/`persistence`; backend/alembic/env.py imports `command` too, so SQLModel metadata picks up both new tables for autogenerate.
- Read backend/tests/test_command_models.py: asserts both tables register on metadata, exact column-set equality for both tables, absence of secret/secret_hash/online, four-timestamp set present with no uploading_at, and scan_id nullable=False + unique=True.
- Ran `uv run pytest tests/test_command_models.py -q` → 7 passed.
- Ran `uv run ruff check` on all four touched/created files → All checks passed.
- Confirmed via `git status --short backend/` that only the four Target Files were touched (no stray edits).
- Grepped all four files for `# ponytail:` markers — none present, nothing to strip.
- Confirmed ARCHITECTURE.md explicitly states no hardware-agent/tui/scanner files are in scope and the CLAUDE.md ScanRunner/ScanProgressScreen thread-through rule does not apply to this task (no orchestrator parameter involved).
- No crypto/secret logic was added — `command.py` defines columns only, matching the scope fence.

**Decisions Made**: APPROVE. Column sets match ARCHITECTURE.md exactly on both tables, encrypted-secret columns (secret_ciphertext/secret_nonce/secret_key_version) present, forbidden columns (secret/secret_hash/online) absent, four timestamps only with no uploading_at, commands.scan_id is NOT NULL + UNIQUE, org_id present on both tables with index=True, model registration wired correctly through both `models/__init__.py` and `alembic/env.py`, no crypto/lifecycle/migration code leaked into this task's scope, tests and ruff both green, diff scope matches Target Files exactly, no ponytail markers to strip.

**Code Reviewed**:
- backend/src/api/models/command.py
- backend/src/api/models/__init__.py
- backend/alembic/env.py
- backend/tests/test_command_models.py

## Task 2: Command lifecycle pure logic module

### Order Given
Implement Task 2 from TASKS.md: create `backend/src/api/services/command_lifecycle.py`, a PURE
module (no DB, no model imports) implementing `next_status(current, target) -> str` per the
ARCHITECTURE.md legal edge table, `scan_status_for(command_status) -> str` as the fixed pure
projection, and `InvalidCommandTransition` as a small custom domain exception naming current and
target. No tests (Task 5's scope).

### What, How, and Why
Created `command_lifecycle.py` with two module-level dicts as the data source of truth:
`_LEGAL_EDGES` (current status -> set of legal target statuses, terminal states mapped to empty
sets) and `_SCAN_STATUS_BY_COMMAND_STATUS` (the fixed seven-entry projection table). `next_status`
short-circuits on `target == current` (idempotent no-op per ADR-011), otherwise checks membership
in `_LEGAL_EDGES[current]` and raises `InvalidCommandTransition` on a miss. `scan_status_for` is a
one-line dict lookup. Kept the two functions fully independent (neither calls the other) per the
architecture note that the projection must be reusable without a transition. No imports beyond
`__future__` — verified pure per the no-DB/no-model-imports constraint.

### Decisions Made
- Used two plain module-level dicts as the lookup tables rather than an enum or state-machine
  library — the edge table and projection table are small, fixed, and match the spec's tabular
  form directly; no speculative abstraction warranted (ponytail rung 1-3: stdlib dict is enough).
- `InvalidCommandTransition` stores `current`/`target` as attributes in addition to the message,
  matching the common pattern of custom domain exceptions elsewhere for caller introspection,
  without adding anything not requested.
- Did not add type aliases/Literal types for status strings since the task signature specifies
  plain `str` and no schema/model file was in scope to define such a type against.

### Code Changed
- Created: `backend/src/api/services/command_lifecycle.py`

## Task 5: test_command_lifecycle.py

### Order Given
Write pure unit tests (no DB) for `backend/src/api/services/command_lifecycle.py`, mirroring
existing test style under `backend/tests/`, covering every ARCHITECTURE.md bullet: every legal
edge, every illegal edge (message names current and target), terminal-as-hard-sink, the
delivered-but-not-started distinction (delivered->expired legal, delivered->failed rejected),
duplicate-frame absorption (next_status(s, s) == s for all statuses), and scan_status_for as a
pure projection over all seven command statuses.

### What, How, and Why
Created `backend/tests/test_command_lifecycle.py`. Derived `LEGAL_EDGES` directly from the
module's documented edge table and computed `ILLEGAL_EDGES` as the complement over all
(current, target) pairs with current != target, so the illegal-edge test parametrization can
never drift from the legal-edge list. Parametrized tests assert `next_status` returns the target
on every legal edge and raises `InvalidCommandTransition` with both status names present in
`str(exc)` on every illegal edge. A nested-parametrize test over (terminal status x all statuses)
asserts every terminal->non-self transition raises and terminal->self returns self, covering the
hard-sink requirement without hand-listing each case. Added two explicit single-case tests for the
delivered->expired/delivered->failed distinction the spec calls out by name, even though they are
already covered by the parametrized sets, since ARCHITECTURE.md names this scenario specifically.
Duplicate-frame absorption is parametrized over all seven statuses. `scan_status_for` is tested
against the fixed seven-entry mapping table and with a call-twice-same-result assertion for
purity (no state, no side effect between calls).

### Decisions Made
- Generated `ILLEGAL_EDGES` from `STATUSES` minus `LEGAL_EDGES` rather than hand-enumerating,
  so the test suite self-updates if a status is added and can't silently drift from the source
  edge list; this is a computed fixture, not a mocked boundary — no DB/network mocking needed
  since the module under test is pure.
- No separate "target not in _LEGAL_EDGES.get(current, set())" test for made-up status strings
  (e.g. "bogus") — out of scope, the module's contract is over the seven known statuses only.
- Reused `pytest.raises(...).value` message assertion (substring check for both status names)
  rather than snapshotting the exact exception string, matching the "assert behavior not
  snapshots" instruction.
- Ran `uv run pytest tests/test_command_lifecycle.py -q` locally: 80 passed.

### Code Changed
- Created: `backend/tests/test_command_lifecycle.py`

## Review: Task 2 (lifecycle module) + Task 5 (lifecycle unit tests)

**Order Given**: Review Task 2 (`backend/src/api/services/command_lifecycle.py`) and Task 5
(`backend/tests/test_command_lifecycle.py`) against their Success Criteria in TASKS.md and the
"Lifecycle module" / "Testing expectations" sections of ARCHITECTURE.md.

**What, How, and Why**:
- Read TASKS.md Task 2 and Task 5 sections, and ARCHITECTURE.md lines 91-127 (Lifecycle module)
  and 204-215 (lifecycle testing expectations).
- Read `backend/src/api/services/command_lifecycle.py` in full and
  `backend/tests/test_command_lifecycle.py` in full.
- Ran `cd backend && uv run pytest tests/test_command_lifecycle.py -q` → 80 passed.
- Ran `cd backend && uv run ruff check src/api/services/command_lifecycle.py
  tests/test_command_lifecycle.py` → **1 error**: `I001 Import block is un-sorted or
  un-formatted` in `tests/test_command_lifecycle.py` (blank line separating stdlib/third-party
  import from first-party import block should be removed). Confirmed with `--diff`; fixable via
  `ruff check --fix`, not a false positive.
- Verified module content against spec: legal edge table matches ARCHITECTURE.md exactly
  (`queued→{delivered,expired}`, `delivered→{running,expired}`, `running→{uploading,failed}`,
  `uploading→{done,failed}`, `done`/`failed`/`expired` terminal); `next_status` no-ops on
  `target == current` before checking edges (absorbs duplicates for terminal states too);
  `InvalidCommandTransition` is a custom `Exception` subclass (not `ValueError`) whose message
  names both `current` and `target` via `repr`; `scan_status_for` fixed dict mapping matches the
  ARCHITECTURE.md projection table for all seven statuses; module has no DB/model imports (only
  `from __future__ import annotations`) — PURE as required.
- Verified test file covers every ARCHITECTURE.md testing bullet: legal edges, illegal edges
  (message contains current+target), terminal hard sink, `delivered→expired` legal /
  `delivered→failed` rejected, duplicate-frame absorption for all seven statuses, and
  `scan_status_for` mapping + purity check.

**Decisions Made**: Rejected solely on the failing `uv run ruff check` gate, which is an explicit,
non-negotiable Success Criterion listed verbatim in both Task 2 and Task 5 ("`uv run ruff check`
passes on the new file" / implied by Task 5's shared quality gate with Task 2's target). The
module and test logic themselves are correct, complete, and appropriately minimal — no
over-engineering findings (no unused abstractions, no unrequested flexibility, dict-based edge
table and projection are the natural minimal representation). This is a one-line mechanical fix
(remove the blank line before the first-party import in the test file, or run
`ruff check --fix`), not a design issue.

**Code Reviewed**:
- `backend/src/api/services/command_lifecycle.py`
- `backend/tests/test_command_lifecycle.py`

## Lint fix: test_command_lifecycle.py import ordering

### Order Given
Code review rejected the lifecycle tests solely for `uv run ruff check` failing with
`I001 Import block is un-sorted or un-formatted` in `backend/tests/test_command_lifecycle.py`
(blank line between the `import pytest` block and the first-party
`from api.services.command_lifecycle import (...)` block). Fix only the import formatting, no
test logic changes.

### What, How, and Why
Ran `uv run ruff check --fix tests/test_command_lifecycle.py` from `backend/`, which removed the
stray blank line and merged the import block per isort rules (1 error fixed). No test logic or
assertions touched.

### Decisions Made
Used ruff's own `--fix` rather than hand-editing, since the fix is mechanical and scoped exactly
to import sorting.

### Code Changed
`backend/tests/test_command_lifecycle.py` (import block only).

### Verification
`uv run ruff check tests/test_command_lifecycle.py` → All checks passed.
`uv run pytest tests/test_command_lifecycle.py -q` → 80 passed.

## Re-review: Task 2 (lifecycle module) + Task 5 (lifecycle unit tests)

**Order Given**: Re-review Task 2 and Task 5 after the sole prior rejection reason — a ruff
`I001` import-sort error in `backend/tests/test_command_lifecycle.py` — was fixed via
`ruff check --fix` (import formatting only, no logic change). Confirm the fix resolved the issue
and all Task 2 + Task 5 Success Criteria still hold.

**What, How, and Why**:
- Re-read TASKS.md Task 2 and Task 5 sections and confirmed no scope/criteria changes since the
  prior review.
- Read `backend/src/api/services/command_lifecycle.py` in full: `_LEGAL_EDGES` matches the
  ARCHITECTURE.md edge table exactly, `next_status` no-ops on `target == current` before the edge
  check (covers terminal self-transitions too), `InvalidCommandTransition` is a custom `Exception`
  subclass naming both `current`/`target` via `repr` in the message, `scan_status_for` is a pure
  one-line dict lookup over the fixed seven-entry projection, module has zero imports beyond
  `from __future__ import annotations` (fully DB-free/pure).
- Read `backend/tests/test_command_lifecycle.py` in full: import block is now a single sorted
  group (`import pytest` then blank line then first-party import, no stray blank line inside a
  block) — the reported `I001` cause is gone. Test coverage unchanged from prior review: legal
  edges, illegal edges (message contains both status names), terminal hard-sink (parametrized),
  `delivered→expired`/`delivered→failed` explicit cases, duplicate-frame absorption for all seven
  statuses, `scan_status_for` mapping + purity check.
- Ran `cd backend && uv run pytest tests/test_command_lifecycle.py -q` → **80 passed**.
- Ran `cd backend && uv run ruff check src/api/services/command_lifecycle.py
  tests/test_command_lifecycle.py` → **All checks passed.**
- Grepped both files for `# ponytail:` markers → none present, nothing to strip.
- Confirmed no orchestrator/runner parameter is involved in this task (pure lifecycle module with
  no DB/model/API wiring), so the CLAUDE.md `ScanRunner`/`ScanProgressScreen` integration rule does
  not apply here.
- Confirmed changed files match Target Files for both tasks exactly: only
  `backend/src/api/services/command_lifecycle.py` (Task 2) and
  `backend/tests/test_command_lifecycle.py` (Task 5).

**Decisions Made**: APPROVE. The single prior rejection reason (ruff `I001`) is resolved and
verified with a clean `ruff check` run; tests pass in full (80/80); all Task 2 and Task 5 Success
Criteria are met (legal/illegal edges, terminal hard sinks, no-op self-transitions, custom
exception naming current+target, fixed pure `scan_status_for` projection, purity/no-DB
constraint); no over-engineering findings — dict-based lookup tables remain the minimal correct
representation, test suite derives illegal edges from the legal-edge list rather than
hand-duplicating data, no unrequested abstractions introduced.

**Code Reviewed**:
- `backend/src/api/services/command_lifecycle.py`
- `backend/tests/test_command_lifecycle.py`

## Task 3: Alembic migration for agents + commands

### Order Given
Implement Task 3 from TASKS.md: create `backend/alembic/versions/20260723_07_command_channel.py`
with `revision = "20260723_07"`, `down_revision = "20260722_06"`, creating `agents` then `commands`
(FK-safe order), the three indexes plus `uq_commands_scan_id`, and the mandatory security fence on
both tables copied from `20260716_02_identity_schema.py`'s pattern. No tests (Task 4's scope).

### What, How, and Why
Copied the `_qualified`/`_revoke_supabase_roles` helper pattern verbatim from
`20260716_02_identity_schema.py`, retargeted at a `COMMAND_TABLES = ("agents", "commands")` tuple.
`upgrade()` creates `agents` first with its FK to `orgs.id`, then `commands` with FKs to `orgs.id`,
`agents.id`, and `scans.scan_id` plus `UniqueConstraint("scan_id", name="uq_commands_scan_id")`
(matching the model's `unique=True`, and doubling as the required index per ARCHITECTURE.md — no
separate `scan_id` index created). Column types follow the spec exactly: `sa.LargeBinary()` for
`secret_ciphertext`/`secret_nonce`, `sqlmodel.sql.sqltypes.AutoString()` for all string columns
(`display_name`, `scan_mode`, `subnet`, `status`, `error_code`), `sa.Uuid()` for all id/FK columns,
`sa.DateTime()` for all seven timestamp columns, `sa.Integer()` for `secret_key_version`.
`commands.status` has no ENUM/CHECK (unconstrained VARCHAR per the spec — the lifecycle module is
the only guard). After both `create_table` calls, indexes `ix_agents_org_id`, `ix_commands_org_id`,
`ix_commands_agent_id` are created, then RLS is enabled on both tables, anon/authenticated
privileges guard-revoked, and `dmitri_runtime` granted SELECT/INSERT/UPDATE — identical sequence
and SQL shape to the identity migration. `downgrade()` reverses in FK-safe order: revoke grants,
drop `commands` indexes/table, drop `agents` index/table; no role create/drop, matching the spec.

### Decisions Made
- Reused the exact `_qualified`/`_revoke_supabase_roles` helper shape from
  `20260716_02_identity_schema.py` rather than inventing a new fence pattern, per the explicit
  "copy this migration's fence exactly" instruction.
- Declared FK constraints via `sa.ForeignKeyConstraint` inside `create_table` (matching
  `20260716_02`'s `users`/`invites` style) rather than `op.create_foreign_key` as a separate step,
  since all three FKs on `commands` and the one on `agents` are known at table-creation time.
- Did not add a CHECK constraint on `commands.status` — ARCHITECTURE.md explicitly documents this
  column as unconstrained VARCHAR with the lifecycle module as the only guard.
- Single UNIQUE constraint (`uq_commands_scan_id`) instead of a separate unique index, since a
  UNIQUE constraint on Postgres implicitly creates its own index — avoids the redundant index the
  spec explicitly says is unnecessary.

### Code Changed
- Created: `backend/alembic/versions/20260723_07_command_channel.py`

## Task 4: test_command_migration.py

### Order Given
Write the migration tests for `backend/tests/test_command_migration.py`, mirroring
`backend/tests/test_migrations.py`'s patterns exactly (`_migrate`, `_table_shape` /
monkeypatched-`op` offline shape checks, `_has_privilege` live-DB privilege checks, and the same
skip/gating conventions), covering every ARCHITECTURE.md testing bullet for the Task 3 migration:
round-trip up/down, security fence privileges, secret-not-one-way column shape, direct tenancy,
FK/timestamp shape, and the `commands.scan_id` UNIQUE 1:1 invariant.

### What, How, and Why
Created `backend/tests/test_command_migration.py`. Loaded the migration module the same way
`test_migrations.py` loads the baseline (`importlib.util.spec_from_file_location` against the
literal `20260723_07_command_channel.py` path) rather than globbing, since this task targets one
specific migration file, not "whatever the newest migration is."

Offline (no DB) tests, monkeypatching `op.create_table`/`create_index`/`execute` exactly like
`test_baseline_matches_model_metadata_and_security_fence`:
- `test_migration_matches_model_metadata_and_security_fence` — runs `upgrade()`, rebuilds the
  created tables' shape via the imported `_table_shape` helper from `test_migrations`, and asserts
  each created column/FK/unique/index group is a subset of the matching `SQLModel.metadata` table
  (same subset-not-equality style the baseline test uses, to tolerate compiled-type-string
  differences between hand-written `sa.Column` migration DDL and SQLModel-derived columns without
  being a snapshot test). Directly asserts the ADR-015 secret shape (`secret_ciphertext`/
  `secret_nonce`/`secret_key_version` present, `secret`/`secret_hash` absent), `org_id` present on
  both tables, `commands.scan_id` FK target and NOT NULL, `commands.agent_id` FK target, the four
  timestamp columns present with no `uploading_at`, the three named indexes, and the
  `uq_commands_scan_id`-equivalent unique-column-set. Then asserts the exact RLS-enable /
  guarded-revoke / grant `execute()` statement sequence, mirroring the baseline's statement-list
  assertion.
- `test_migration_downgrade_drops_tables_and_grants` — monkeypatches `drop_table`/`drop_index`/
  `execute`, asserts `commands` drops before `agents` (FK-safe order) and the single REVOKE
  statement fires.

Live-DB tests (gated by the existing `postgres_engine` fixture, which itself `pytest.skip`s when
`DATABASE_URL_TEST` is unset — the same gating `test_migrations.py` relies on, so no new skip logic
was needed):
- `test_live_migration_round_trip_and_kept_engine_queries` — uses `_migrate(engine, "20260722_06")`
  to go down one revision (proving `agents`/`commands` absent pre-migration) then
  `_migrate(engine, "head")` back up, asserting both tables now exist, then runs a kept-engine query
  against `ScanRecord` (`scans`) and a raw `SELECT id FROM public.hosts` to prove existing
  read paths still work after the new migration lands.
- `test_live_fence_privileges` — mirrors `_has_privilege`/`test_live_migration_round_trip_and_security`:
  asserts `relrowsecurity = true` for both tables via `pg_class`, that `anon`/`authenticated` hold
  none of the seven privileges, and that `dmitri_runtime` holds SELECT/INSERT/UPDATE but not
  DELETE/TRUNCATE/REFERENCES/TRIGGER.
- `test_live_commands_scan_id_unique_constraint` — uses the existing `migrated_database` fixture
  (truncates between tests), inserts an `Org`, a `ScanRecord`, an `Agent`, then two `Command` rows
  both pointing at the same `scan_id`; asserts the second `session.commit()` raises
  `sa.exc.IntegrityError`, proving the UNIQUE constraint enforces the 1:1 Command:Scan invariant at
  the DB level (not just at the SQLModel `unique=True` Python level).

### Decisions Made
- Reused `_table_shape` and `_has_privilege` by importing them from `test_migrations` rather than
  duplicating them, since both are already private test-module helpers with an established import
  precedent in this repo (`conftest.py` functions are imported the same way).
- Used subset (`<=`) comparisons for the offline shape checks instead of strict equality, matching
  the baseline test's own precedent for handling model-vs-migration type-compilation differences,
  rather than asserting brittle exact-tuple equality that could break on incidental SQLAlchemy
  type-string formatting differences unrelated to the schema itself.
- Chose `_migrate(engine, "20260722_06")` (one revision back) rather than `"base"` for the
  round-trip test, since the ARCHITECTURE.md bullet only requires proving this migration's own
  up/down correctness and existing-table query continuity, not re-testing the full stack's
  base-to-head journey the way `test_migrations.py`'s own full-stack test already does.
- Live-DB behavior (fence privileges, unique-constraint rejection) is asserted only through
  `postgres_engine`/`migrated_database`-gated tests, never faked or mocked, per the "assert
  behavior not snapshots" instruction and the existing project convention of skipping rather than
  stubbing Postgres-only guarantees (RLS, UNIQUE) when no live DB is available.
- Did not add a separate test asserting `agents.org_id`/`commands.org_id` FK target
  (`orgs.id`) beyond what the offline model-subset check already covers, since ARCHITECTURE.md's
  tenancy bullet only requires the columns exist, not a duplicate FK-target assertion already
  implied by the FK/shape bullet's coverage of `commands`.

### Verification
`uv run pytest tests/test_command_migration.py -q` locally (no `DATABASE_URL_TEST` set in this
environment) → **2 passed, 3 skipped** — the two offline shape/downgrade tests pass; the three
live-DB tests (`test_live_migration_round_trip_and_kept_engine_queries`,
`test_live_fence_privileges`, `test_live_commands_scan_id_unique_constraint`) skip via the
`postgres_engine` fixture's existing `DATABASE_URL_TEST`-unset guard, identical to how
`test_migrations.py`'s own live tests skip in this environment. No local Postgres instance was
available to exercise the live path; the live assertions were written to mirror
`test_live_migration_round_trip_and_security`'s verified pattern exactly, so they are expected to
pass under CI/a real `dmitri_test` database but were not executed end-to-end here.

### Code Changed
- Created: `backend/tests/test_command_migration.py`

## Review: Task 3 (Alembic migration) + Task 4 (migration tests)

**Order Given**: Review Task 3 and Task 4 of specs/016-command-channel-data-model/TASKS.md as authoritative gate — verify migration correctness against ARCHITECTURE.md "Migration"/"Testing expectations" and the identity-schema fence pattern, run pytest and ruff on the touched scope.

**What, How, and Why**
- Read TASKS.md Task 3/4 sections and ARCHITECTURE.md "Migration"/"Testing expectations" sections in full.
- Diffed `backend/alembic/versions/20260723_07_command_channel.py` against `backend/alembic/versions/20260716_02_identity_schema.py` (fence pattern reference): revision/down_revision correct, agents-then-commands creation order, `sa.LargeBinary`/`AutoString`/`sa.Uuid`/`sa.DateTime` types used consistently, `status` is plain AutoString with no ENUM/CHECK, all three indexes plus `uq_commands_scan_id` UNIQUE present, `commands.scan_id` NOT NULL FK→scans.scan_id, `commands.agent_id` FK→agents.id, exactly four timestamp columns with no `uploading_at`, RLS enable + guarded anon/authenticated revoke + dmitri_runtime SELECT/INSERT/UPDATE grant on both tables (statement-for-statement match to the identity-schema helper functions), and downgrade revoking grants then dropping commands before agents.
- Read `backend/tests/test_command_migration.py` and cross-checked against `backend/tests/test_migrations.py` patterns (`_migrate`, `_table_shape`, `_has_privilege`, monkeypatched `op`). Confirmed every ARCHITECTURE.md "Testing expectations" bullet is covered: offline metadata/shape/fence-statement test, offline downgrade-drop-order test, live round-trip + kept `hosts`/`scans` queries, live RLS + full privilege matrix (anon/authenticated denied, dmitri_runtime SELECT/INSERT/UPDATE only), live UNIQUE-constraint rejection test for duplicate `scan_id`.
- Ran `cd backend && uv run pytest tests/test_command_migration.py -v` — result: 2 passed, 3 skipped (skips are the `postgres_engine`-dependent live tests, correctly gated via `pytest.skip("DATABASE_URL_TEST not set")` in `conftest.py`, mirroring `test_migrations.py`'s own gating — not silently absent, offline tests pass).
- Ran `cd backend && uv run ruff check alembic/versions/20260723_07_command_channel.py tests/test_command_migration.py` — result: All checks passed.
- Grepped for `# ponytail:` markers in both touched files — none found, so no strip needed.
- Confirmed no crypto/secret-writing logic present (only column definitions, matching the "define columns, write no secret" scope fence) and confirmed the CLAUDE.md ScanRunner/ScanProgressScreen integration rule is explicitly N/A per ARCHITECTURE.md (backend-only feature, no TUI/scanner files touched, none in Target Files).

**Decisions Made**: APPROVE. Migration is a faithful copy of the identity-schema fence pattern applied to the new tables with correct column types, FK-safe creation order, exact index/constraint set, and correct downgrade order. Tests exercise every bullet in ARCHITECTURE.md's "Testing expectations" for `test_command_migration.py`, live tests are correctly gated (skip, not absent) and offline tests pass. Both `pytest` and `ruff check` are clean over the touched scope. No overengineering found — code reuses the existing `_qualified`/`_revoke_supabase_roles` shape from the identity-schema migration rather than inventing new abstractions.

**Code Reviewed**:
- backend/alembic/versions/20260723_07_command_channel.py
- backend/tests/test_command_migration.py
- backend/alembic/versions/20260716_02_identity_schema.py (reference pattern)
- backend/tests/test_migrations.py (reference pattern)
- backend/src/api/models/command.py (Task 1 dependency, read-only cross-check)
- backend/tests/conftest.py (fixture gating verification)
