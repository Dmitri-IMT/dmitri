# Structural re-evaluation — Task 1

## Trigger

Task 1 reached four consecutive reviewer rejections. In every cycle, the six focused Alembic
tests, `uv sync --frozen --extra dev`, `uv lock --check`, and Ruff passed. The reviewers found
no Task 1 implementation defect, but the full backend suite remained at 7 passed and 5 failed.
Per the feature-orchestrator contract, Task 1 is `BLOCKED_STRUCTURAL` and no further code work
may start without human approval of this revision.

## Symptom

All five failures are in `backend/tests/test_ingest_scan.py`. Each test loads
`contracts/examples/scan_result.example.json`, whose legacy payload contains `scan_mode` and
omits the required `target_mode` and `scan_profile` fields. `ScanResult` rejects the payload
before any Task 1 Alembic behavior is exercised.

The approved plan assigned `backend/tests/test_ingest_scan.py` to Task 3, made Task 3 depend on
Tasks 1 and 2, omitted the shared example from the mandatory file table, and simultaneously
required the complete backend suite to pass for every task. Task 1 therefore could not pass
its gate without changing files it did not own, while the task that owned the failing test
could not start.

## Root cause

This is a specification and orchestration deadlock, not an implementation regression:

- Repository history shows the required scan fields and the ingest tests predate Task 1.
- The stale example also predates Task 1 and still carries the superseded `scan_mode` field.
- Task 1 did not change the relevant Pydantic, SQLModel, FastAPI, SQLAlchemy, or pytest
  versions.
- The Task 1 file fence had no legitimate place to repair the shared example or ingest tests.
- The architecture converted the reviewer's task-scoped pytest rule into an unconditional
  full-suite rule before the known failing compatibility surface had an owner.
- `backend/tests/test_migrations.py` was used as Task 1's focused proof but was not listed in
  Task 1's target files, leaving its staged test ownership underspecified.

The intent of the quality gate remains valid: no feature may ship with a red backend suite,
and the authoritative Postgres-backed CI run must pass without database-test skips. The
ordering of that gate was invalid.

## Revised plan

1. Keep Task 1's implementation scope unchanged and give it explicit ownership of the
   non-database Alembic configuration tests already used to review it.
2. Use a focused task gate for Tasks 1 and 2: the migration test module, frozen dependency
   checks where applicable, and Ruff must pass. The known ingest failures are not a Task 1 or
   Task 2 approval gate because neither task owns that compatibility surface.
3. Give Task 3 exact ownership of `contracts/examples/scan_result.example.json` alongside
   `backend/tests/test_ingest_scan.py`. Task 3 must replace the legacy field with valid
   `target_mode` and `scan_profile` values without changing the example's scenario or the
   scan schema.
4. Make Task 3 the first mandatory complete-backend-suite gate. Its full local pytest run
   must pass; from Task 3 onward, every backend-changing task keeps the complete suite green.
5. Keep Task 4's independent gate scoped to the checked-in OpenAPI contract test because it
   changes no backend code.
6. Keep Task 10 and feature approval unchanged: Postgres 17, migrations up/down, the complete
   backend suite, zero database-test skips, frozen sync, and Ruff must all pass in CI.

This plan does not deselect tests, weaken `ScanResult`, add defaults, mask validation, or
permit the known failures to survive the task that owns them.

## Exact spec changes

### `TRUTH.md`

- Clarify the quality-gate acceptance row: task approval is scoped to the task's owned
  behavior, while feature approval still requires the complete Postgres-backed CI result.
- Add an incremental-gate row requiring the pre-existing compatibility debt to be resolved at
  its assigned owner before later backend tasks proceed.

### `ARCHITECTURE.md`

- Add `contracts/examples/scan_result.example.json` to the mandatory file table and assign
  its schema-compatibility correction to Task 3.
- Clarify phased ownership of `backend/tests/test_migrations.py`: Task 1 owns the initial
  non-database Alembic configuration coverage, Task 2 may add baseline-focused coverage, and
  Task 3 owns the database-backed round-trip/security expansion.
- Replace the unconditional per-task full-suite paragraph with exact staged gates: focused
  gates for Tasks 1–2, contract-only coverage for Task 4, complete backend pytest beginning at
  Task 3 and remaining mandatory for later backend tasks, and unchanged authoritative CI.
- Constrain the shared example change to replacing `scan_mode` with schema-valid
  `target_mode`/`scan_profile`; no scan-schema or business-route change is authorized.

### `TASKS.md`

- Keep Task 1 `BLOCKED_STRUCTURAL` with four rejections until the human gate is released.
- Add `backend/tests/test_migrations.py` to Tasks 1 and 2 with exact staged ownership.
- Replace Tasks 1–2's ambiguous full-suite criteria with their focused migration/lint gates.
- Add `contracts/examples/scan_result.example.json` to Task 3's target files and require its
  schema-valid correction plus a green complete backend suite.
- Make Task 4's contract-only test gate explicit.
- Record the human-gate and restart procedure without prematurely resetting status or
  rejection count.

No application, test, contract-example, or dependency file is changed by this structural
re-evaluation.

## Human gate

**Decision required:** approve or reject the staged quality gate and Task 3 ownership of the
shared scan example. Until approval, Task 1 remains `BLOCKED_STRUCTURAL`, its rejection count
remains 4, and no coder, test engineer, or reviewer may resume feature implementation.

On explicit human approval:

1. The feature orchestrator changes Task 1 to `IN_PROGRESS` and resets its `Review Rejections`
   from 4 to 0.
2. The orchestrator spawns a **fresh Task 1 coder from step 1**. The rejected coders are not
   resumed. The fresh coder re-audits the existing Task 1 files against the amended target
   list and criteria; it does not edit the Task 3-owned ingest test or shared example.
3. A test engineer runs the amended focused Task 1 gate, then a fresh reviewer independently
   runs that same gate and decides `[APPROVE]` or `[REJECT]` under the reset rejection cycle.
4. After Task 1 approval, execution continues through Task 2. Task 3 then performs the first
   authorized shared-example/ingest compatibility change and must restore the complete
   backend suite to green before Task 5 or any later backend-changing task begins.

Approval phrase: `APPROVE STRUCTURAL_REEVAL — Task 1`.

