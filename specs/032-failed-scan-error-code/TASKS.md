# Tasks — Give a failed scan a readable reason (`032-failed-scan-error-code`)

7 tasks. **All COMPLETED.**

> **Blast radius is `backend/` and `frontend/` — not `hardware-agent/`.**
>
> | Tasks | Test agent | Review agent | Gate |
> |---|---|---|---|
> | 1–6 (backend) | `test-engineer` | `code-reviewer` | `./database.sh --test`, then `uv run ruff check src tests` + `uv run pytest` from `backend/` |
> | 7 (frontend) | `frontend-test-engineer` | `frontend-code-reviewer` | `npm run lint && npm run typecheck && npm test && npm run build` from `frontend/` |
>
> **A non-zero pytest skip count is NOT green** — without a live `dmitri_test`, `conftest.py`
> skips every DB-backed test, which is most of tasks 2–6. **Never run `ruff format` (or any
> formatter) in `backend/`;** `ruff check` is the only Python gate there.
>
> The CLAUDE.md `ScanRunner` / `ScanProgressScreen` integration rule does **not** apply: no
> orchestrator parameter is added and `hardware-agent/src` is untouched.

---

## Task 1: Failure-code vocabulary and normalisation helpers
- **Description**: Create the leaf module holding the closed `ScanErrorCode` set and the two pure
  functions every read path uses, per ARCHITECTURE.md §2.1 and the naming table. Eight codes
  exactly: `device_offline`, `device_busy`, `agent_disconnected`, `scan_failed`, `invalid_command`,
  `result_unavailable`, `ingest_failed`, `unknown`. It lives in `api/core/` (mirroring
  `api/core/severity.py`) because `schemas/read.py` and `schemas/commands.py` have no import edge
  between them today and must not gain one.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/core/error_codes.py`, `backend/tests/test_error_codes.py`]
- **Tests**: `backend/tests/test_error_codes.py` — pure unit asserts, no DB, mirroring
  `backend/tests/test_read_schema.py`. Proves all 8 codes round-trip, `None` stays `None`, an
  off-contract string normalises to `unknown`, the set is exactly 8, a non-failed status yields
  `None` regardless of what is stored, and a `failed` status is never bare.
- **Success Criteria**:
  - `normalise_error_code(c) == c` for each of the 8 published codes; `normalise_error_code(None) is None`; `normalise_error_code("scan_timeout") == "unknown"`.
  - `scan_error_code("failed", None) == "unknown"` and `== "unknown"` for an unrecognised string.
  - `scan_error_code(s, "scan_failed") is None` for each of `pending`, `accepted`, `processing`, `completed`.
  - `len(SCAN_ERROR_CODES) == 8` and it equals the `Literal` members.
  - The module imports nothing from `api.schemas` or `api.services`.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Type and normalise the command read path
- **Description**: Adopt the shared alias on `CommandDetail.error_code` (schemas/commands.py:47,
  `str | None` → `ScanErrorCode | None`) **and** wrap the `get_command_detail` passthrough in
  `normalise_error_code`, per ARCHITECTURE.md §2.3/§2.4. These ship together or not at all:
  tightening the schema alone makes `GET /commands/{command_id}` raise a pydantic
  `ValidationError` — a 500 — on any row holding a code outside the published set (Constraint 2).
- **Absorbed**: the `schemas/commands.py` alias edit — a type-only change that no test can fail on
  its own; it is observable exactly through the `get_command_detail` cases below.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/schemas/commands.py`, `backend/src/api/services/commands.py`, `backend/tests/test_get_command.py`]
- **Tests**: `backend/tests/test_get_command.py` — extends the existing `_seed_command` /
  `TestClient` fixtures. Proves the off-contract row returns `200` + `"unknown"` rather than 500.
- **Success Criteria**:
  - A command storing an off-contract code returns `200` with `error_code: "unknown"` — explicitly asserted as a non-500 regression.
  - A command storing a published code returns that code unchanged.
  - A `queued` command returns `error_code: null`.
  - `apply_status` is unchanged.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: Put the reason and the command id on the scan detail
- **Description**: Add `error_code: ScanErrorCode | None` to `ScanDetailResponse` (after
  `command_id`), and in `get_scan_detail` replace the hardcoded `command_id=None` at
  services/read.py:170 with a real lookup through `commands.command_for_scan`, deriving
  `error_code` via `scan_error_code(scan.status, …)`. Read-time join only — no column on `scans`,
  no migration, no backfill. Per ARCHITECTURE.md §2.2/§2.4. `ScanSummary` and `list_scans` stay
  untouched.
- **Absorbed**: the `schemas/read.py` field addition — a type-only change observable only through
  the service and route cases below.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/schemas/read.py`, `backend/src/api/services/read.py`, `backend/tests/test_read_service_scans.py`, `backend/tests/test_read_endpoints.py`]
- **Tests**: `backend/tests/test_read_service_scans.py` (service level, existing `make_scan` /
  `read_factories` seeding) and `backend/tests/test_read_endpoints.py` (route level, existing
  `GET /api/v1/scans/{scan_id}` cases).
- **Success Criteria**:
  - Failed scan + command with a published code → that code, from **one** request.
  - Failed scan + command with a NULL code → `"unknown"`; with an off-contract stored string → `"unknown"`; with **no** command row at all → `"unknown"`.
  - A `completed` scan whose command holds `scan_failed` → `error_code is None`.
  - `command_id` is the real command id, not `null`.
  - The scan **list** response carries no `error_code` key.
  - The route body shows `error_code` and a non-null `command_id`; a non-failed scan's body shows `error_code: null`.
  - No Alembic migration is added.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: Make the stale sweep record why
- **Description**: `sweep_stale_commands` writes `status="failed"` with no code today — the most
  common real failure has no reason anywhere. Add `error_code` to the existing `.values(...)` as a
  `case()`: `device_offline` for the `queued → expired` branch, `agent_disconnected` for the
  `else_ → failed` branch, per ARCHITECTURE.md §2.5. The `case()` reads pre-update
  `Command.status`, which is correct and consistent with the two `case()` expressions already
  there — do not "fix" it.
- **Dependencies**: Task 1, Task 3
- **Target Files**: [`backend/src/api/services/commands.py`, `backend/tests/test_commands_service.py`, `backend/tests/test_worker_sweep.py`]
- **Tests**: `backend/tests/test_commands_service.py` — extends the existing `T0` / `STALE` /
  `_seed_agent` helpers. `test_worker_sweep.py` is run unchanged as a no-regression check.
- **Success Criteria**:
  - Stale `queued` → `expired` **and** `error_code == "device_offline"`.
  - Stale `delivered` / `running` / `uploading` → `failed` **and** `error_code == "agent_disconnected"`.
  - The mirrored `scans.status` write still happens.
  - A swept `running` row's scan detail reports `agent_disconnected` end-to-end.
  - The `device_offline` branch is asserted via `GET /commands/{id}`, **never** via scan detail — ADR-011 forbids an `expired` row from having a `scan_id`, so a scan-detail test for it would seed an illegal row and hit the DDL CHECK (Constraint 1).
  - `test_worker_sweep.py` still passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 5: Prove a newer Pi is never silenced
- **Description**: The inbound `AgentStatusFrame.error_code` stays `str | None` **by design** —
  tightening it would make a version-skewed Pi's failure report fail validation, losing a real
  failure and stranding the command (ARCHITECTURE.md §2.6). Prove that end-to-end, and correct the
  misleading fixture: `test_agent_ws_channel.py` lines 504 and 513 use `scan_timeout`, a code no Pi
  in `hardware-agent/src` emits — change both to `scan_failed`.
- **Dependencies**: Task 2
- **Target Files**: [`backend/tests/test_agent_ws_channel.py`]
- **Tests**: `backend/tests/test_agent_ws_channel.py` — extends its existing failed-report case.
- **Success Criteria**:
  - Reporting an unpublished code (e.g. `"warp_core_breach"`) keeps the socket open, is not rejected, and stores the string verbatim in `commands.error_code`.
  - `GET /commands/{id}` then reads `"unknown"` for that row.
  - Lines 504 and 513 read `scan_failed`; no other `scan_timeout` occurrence is touched.
  - `backend/src/api/schemas/agent_frames.py` is **unmodified**.
  - `backend/tests/test_agent_frames.py:106` is **unmodified** — its off-contract string is the guard proving this permissiveness, and rewriting it would delete the evidence.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6: Publish the enum in the contract
- **Description**: Hand-write the `ScanErrorCode` enum into `contracts/openapi/openapi.yaml` and
  point both schemas at it, per ARCHITECTURE.md §2.5: a new `components.schemas.ScanErrorCode`
  (8 values), `ScanDetailResponse.properties.error_code` added as an `anyOf` `$ref` + `null` and
  **not** added to `required`, and `CommandDetail.properties.error_code` re-pointed from its
  untyped `anyOf` to the same `$ref`. `AgentStatusFrame` in the YAML is untouched. The YAML is the
  published contract — `/openapi.json` is disabled and there is no generator, so this edit is the
  only way the contract changes.
- **Dependencies**: Task 2, Task 3
- **Target Files**: [`contracts/openapi/openapi.yaml`]
- **Tests**: No new test file, and this is the rule's stated exception rather than a merge
  candidate: `backend/tests/test_contract_fidelity.py` **already** parametrises `ScanDetailResponse`
  and `CommandDetail`, and its `_property_shape` resolves `$ref` before fingerprinting and folds
  `anyOf: [X, null]` into `{...X, nullable: true}`. That existing test is the authoritative gate and
  fails loudly if the YAML and the FastAPI app disagree. It must go green with **no edit** to it.
- **Success Criteria**:
  - `test_contract_fidelity.py` passes unmodified.
  - The YAML follows the existing `ScanStatus` / `ScanMode` / `CommandStatus` `$ref` pattern.
  - `error_code` is absent from both schemas' `required` lists.
  - `AgentStatusFrame` is unchanged in the YAML.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 7: Ship the operator's sentences
- **Description**: Add the frontend copy deck at `frontend/src/lib/scanFailureReasons.ts` per
  ARCHITECTURE.md §2.7 — `SCAN_FAILURE_REASONS: Record<ScanErrorCode, string>` keyed off the
  **generated** type, plus `scanFailureReason(code: string | null): string` that reads through a
  widened `Record<string, string | undefined>` with a `??` fallback to the `unknown` sentence.
  The copy is verbatim and approved: **do not reword, re-punctuate, or "fix" the em dashes.**
  The deck has no caller today — DMI-88 builds the Scan Detail screen and will import it. That is
  deliberate and approved: a tested module with no consumer yet, not a stopgap.
- **Absorbed**: the `npm run gen:types` regeneration of `frontend/src/types/openapi.d.ts` — a
  generated artifact that carries no test of its own; it is exercised by this task's typecheck,
  since the deck cannot compile unless the union arrived.
- **Dependencies**: Task 6
- **Target Files**: [`frontend/src/types/openapi.d.ts`, `frontend/src/lib/scanFailureReasons.ts`, `frontend/src/lib/scanFailureReasons.test.ts`]
- **Tests**: `frontend/src/lib/scanFailureReasons.test.ts` — plain Vitest beside the source,
  mirroring `frontend/src/lib/review.test.ts`. No React, no MSW, no rendering.
- **Success Criteria**:
  - `npm run gen:types` produces the committed `openapi.d.ts`, and re-running it leaves a clean diff. The file is never hand-edited.
  - The deck's key set equals an explicit literal list of the 8 codes.
  - Each of the 8 lookups returns the approved sentence, asserted verbatim.
  - `scanFailureReason('warp_core_breach')` and `scanFailureReason(null)` both return the `unknown` sentence.
  - No sentence contains a code string, `_`, `nmap`, or `Traceback`; every sentence ends with `.`.
  - `npm run typecheck` passes — this is the compile-time half of the drift gate, since an erased type cannot be enumerated at runtime. A code added to the union without copy must fail `tsc`.
  - No page, component, hook, query key, or route is added. `src/api/` is untouched.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Dependency graph

```
#1 ─┬─→ #2 ─┬─→ #5
    │       │
    ├─→ #3 ─┴─→ #6 → #7
    │       │
    └───────┴─→ #4
```

`#2` and `#3` are independent of each other and can run in parallel once `#1` lands.
`#4` needs `#3` for its end-to-end scan-detail assertion. `#5` needs `#2` for its
`GET /commands/{id}` assertion.

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Failure-code vocabulary and normalisation helpers | COMPLETED |
| 2 | Type and normalise the command read path | COMPLETED |
| 3 | Put the reason and the command id on the scan detail | COMPLETED |
| 4 | Make the stale sweep record why | COMPLETED |
| 5 | Prove a newer Pi is never silenced | COMPLETED |
| 6 | Publish the enum in the contract | COMPLETED |
| 7 | Ship the operator's sentences | COMPLETED |
