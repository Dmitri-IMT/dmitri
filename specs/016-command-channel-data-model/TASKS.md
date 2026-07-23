# Tasks — Command-channel data model + lifecycle state machine (`016-command-channel-data-model`)

5 tasks. **Unblocked now: #1, #2**

Two parallel tracks: **Schema** (#1 → #3 → #4) and **Lifecycle logic** (#2 → #5).
Split scope finely: models → migration → tests, alongside the pure lifecycle module + its tests.

---

## Task 1: Agent + Command SQLModel table models
- **Description**: Create the `Agent` and `Command` `table=True` SQLModel definitions per the ARCHITECTURE.md "Data model / contracts" tables, mirroring `models/identity.py` style (`utc_now` default factory). `agents`: `id` (UUID pk), `org_id` (FK→`orgs.id`, `index=True`), `display_name`, `secret_ciphertext`/`secret_nonce` (`LargeBinary`), `secret_key_version` (int), nullable `revoked_at`/`last_seen_at`, `created_at`. NO `secret`/`secret_hash`/`online` column. `commands`: `id` (UUID pk), `org_id` (FK, index), `agent_id` (FK→`agents.id`, index), `scan_id` (FK→`scans.scan_id`, NOT NULL + UNIQUE), `scan_mode`, `subnet`, `status`, nullable `error_code`, and exactly four timestamps `created_at`/`delivered_at`/`started_at`/`completed_at` (deliberately NO `uploading_at`). Verify the model-import path used by `alembic/env.py`/package `__init__` and add the new module import there if the two models are not otherwise loaded for metadata/autogenerate. Define columns only — write no crypto/secret logic (scope fence).
- **Dependencies**: —
- **Target Files**: [`backend/src/api/models/command.py`]
- **Success Criteria**: `Agent` and `Command` models import cleanly and register in SQLModel metadata; column set exactly matches the ARCHITECTURE.md tables (encrypted-secret columns present, no `secret`/`secret_hash`/`online`, four timestamps only); `commands.scan_id` is NOT NULL with a UNIQUE constraint; `org_id` present on both; `uv run ruff check` passes on the new file.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Command lifecycle pure logic module
- **Description**: Create the pure (no-DB) lifecycle module per ARCHITECTURE.md "Lifecycle module". Implement `next_status(current, target) -> str` enforcing the legal edge table (`queued`→{`delivered`,`expired`}; `delivered`→{`running`,`expired`}; `running`→{`uploading`,`failed`}; `uploading`→{`done`,`failed`}; `done`/`failed`/`expired` terminal), where `target == current` is a no-op success returning `current` and any illegal edge raises `InvalidCommandTransition(current, target)`. Implement `scan_status_for(command_status) -> str` as the fixed pure projection (`queued`/`delivered`→`pending`, `running`→`accepted`, `uploading`→`processing`, `done`→`completed`, `failed`/`expired`→`failed`). Define `InvalidCommandTransition` as a small custom domain exception (NOT `ValueError`) whose message names current and target. Keep the two functions separate so the projection is reusable without a transition.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/services/command_lifecycle.py`]
- **Success Criteria**: every legal edge returns its target; every illegal edge raises `InvalidCommandTransition` naming current+target; `next_status(s, s)` returns `s` for every status; terminal states are hard sinks; `scan_status_for` returns the fixed mapping for all seven statuses; `uv run ruff check` passes on the new file.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: Alembic migration for agents + commands
- **Description**: Create the migration per ARCHITECTURE.md "Migration" with `revision = "20260723_07"`, `down_revision = "20260722_06"`. `upgrade()` creates `agents` then `commands` (agents first — `commands.agent_id` FK depends on it), using `sa.LargeBinary()` for binary, `sqlmodel.sql.sqltypes.AutoString()` for strings, `sa.Uuid()` for uuids, `sa.DateTime()` for timestamps; `commands.status` is unconstrained VARCHAR (no ENUM/CHECK). Create indexes `ix_agents_org_id`, `ix_commands_org_id`, `ix_commands_agent_id`, and a UNIQUE constraint `uq_commands_scan_id` (serves as the `scan_id` index). Apply the mandatory security fence to BOTH tables exactly like `20260716_02_identity_schema.py`: `ENABLE ROW LEVEL SECURITY`; guarded `REVOKE ALL PRIVILEGES … FROM anon`/`authenticated` (`DO $$ … IF EXISTS pg_roles …`); `GRANT SELECT, INSERT, UPDATE … TO dmitri_runtime`. `downgrade()` revokes the `dmitri_runtime` grants then drops `commands` then `agents` (reverse FK order); no role create/drop.
- **Dependencies**: Task 1
- **Target Files**: [`backend/alembic/versions/20260723_07_command_channel.py`]
- **Status**: COMPLETED
- **Success Criteria**: `upgrade()` then `downgrade()` both succeed and round-trip; `agents`/`commands` created in FK-safe order with the exact column set, four timestamps and no `uploading_at`; `commands.scan_id` NOT NULL + UNIQUE and FKs `scans.scan_id`; the three indexes and `uq_commands_scan_id` exist; both tables get RLS + anon/authenticated revoke + `dmitri_runtime` SELECT/INSERT/UPDATE grant; `uv run ruff check` passes.
- **Review Rejections**: 0

## Task 4: Migration tests
- **Description**: Create migration tests mirroring `backend/tests/test_migrations.py` patterns (`_migrate`, `_table_shape`/monkeypatched-`op`, `test_live_migration_round_trip_and_security`/`_has_privilege`). Cover ARCHITECTURE.md "Testing expectations": migration round-trips up→down with existing `hosts`/`scans` queries still working; both new tables have `relrowsecurity = true`; `anon`/`authenticated` hold none of SELECT/INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER and `dmitri_runtime` holds SELECT/INSERT/UPDATE but NOT DELETE/TRUNCATE/REFERENCES/TRIGGER; `agents` has `secret_ciphertext`/`secret_nonce`/`secret_key_version` and NO `secret`/`secret_hash`; `org_id` present on both; `commands.scan_id` NOT NULL + FK, `commands.agent_id` FK, four timestamps and no `uploading_at`; the three indexes exist and a second command with an already-used `scan_id` is rejected (proves the 1:1 UNIQUE invariant).
- **Dependencies**: Task 3
- **Target Files**: [`backend/tests/test_command_migration.py`]
- **Success Criteria**: tests assert every bullet above and pass under `uv run pytest`; `uv run ruff check` passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 5: Lifecycle unit tests
- **Description**: Create pure unit tests (no DB) for the lifecycle module per ARCHITECTURE.md "Testing expectations": every legal edge returns its target; every non-listed `(current, target)` raises `InvalidCommandTransition` whose message names current and target; terminal (`done`/`failed`/`expired`) → any is rejected; `delivered → expired` legal while `delivered → failed` rejected; `next_status(s, s)` returns `s` for every status; `scan_status_for` returns the fixed mapping for all seven command statuses as a pure projection (no transition performed).
- **Dependencies**: Task 2
- **Target Files**: [`backend/tests/test_command_lifecycle.py`]
- **Success Criteria**: all listed scenarios asserted and passing under `uv run pytest`; `uv run ruff check` passes.
- **Status**: COMPLETED
- **Review Rejections**: 1

---

## Dependency graph

```
#1 → #3 → #4     (schema track)
#2 → #5          (lifecycle track)
```

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Agent + Command SQLModel table models | COMPLETED |
| 2 | Command lifecycle pure logic module | COMPLETED |
| 3 | Alembic migration for agents + commands | COMPLETED |
| 4 | Migration tests | COMPLETED |
| 5 | Lifecycle unit tests | COMPLETED |
