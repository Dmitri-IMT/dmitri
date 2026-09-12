# TASKS — OT agent hardening (`045-ot-agent-hardening`)

10 tasks. **All ten landed** on `feat/045-ot-agent-hardening` in worktree `/Users/gui/Projects/dmitri-045-ot-agent-hardening`. Do not implement from `feat/dmi-157-harden-active-ot-scans`.

Cut the implementation branch from `main`, not from `audit/nspi-137`. Ordering constraint: Task 1 lands alone before Task 2; Task 2 must not land first.

Approved sources: `TRUTH.md`, `ARCHITECTURE.md`, `DESIGN.md`, `INTEGRATION.md`. Interview decisions (OT-only ceiling, no `partial_result` from OT time stop, durable Limits line, 042 item 14 replaced) are already written into those files.

Blast radius is `hardware-agent/` and `backend/`. Test agent: `test-engineer`. Review agent: `code-reviewer`. Gate: `uv run pytest` and `uv run ruff check` in the touched layer (`hardware-agent/` never `ruff format` the repo; `backend/` is `ruff check` only). Task 10 also runs `npm run gen:types && npm run typecheck && npm run build` in `frontend/`. No `frontend-test-engineer`; there is no OT web screen.

---

## Task 1: Merge the forked Alembic heads
- **Description**: Add empty merge revision `20260912_20` with `down_revision = ("20260905_19", "20260908_19")` per ARCHITECTURE.md §8. Do not rewrite `20260903_18`. Lands first, alone.
- **Dependencies**: —
- **Target Files**: [`backend/alembic/versions/20260912_20_merge_ot_and_activity_heads.py`, `backend/tests/test_alembic_single_head.py`]
- **Tests**: `test_alembic_single_head.py` — `ScriptDirectory.get_heads()` has length 1.
- **Success Criteria**:
  - `alembic heads` reports exactly one revision.
  - Upgrade from empty applies every pending change in order through `20260912_20`.
  - Released revisions are unchanged.
- **Status**: DONE (`0ee7360`)
- **Review Rejections**: 0

## Task 2: Fail the backend suite when no database is set
- **Description**: Replace `pytest.skip` in `postgres_engine` with `pytest_configure` raising `UsageError` when `DATABASE_URL_TEST` is unset, per ARCHITECTURE.md §7.2. No opt-out. Lands after Task 1 so the suite can migrate.
- **Dependencies**: Task 1
- **Target Files**: [`backend/tests/conftest.py`, `backend/tests/test_database_required.py`]
- **Tests**: `test_database_required.py` — subprocess `pytest` with `DATABASE_URL_TEST` unset exits non-zero, names the reason, and cannot be made to pass with a flag.
- **Success Criteria**:
  - A run without a test database aborts collection with exit code 4.
  - The skip at conftest 121-124 is gone.
  - With `./database.sh --test`, the suite reaches assertions instead of skipping.
- **Status**: DONE (`a32228e`)
- **Review Rejections**: 0

## Task 3: Bound and classify untrusted device data at parse
- **Description**: Add `agent/ot/untrusted.py` and apply it in FC43 decode and NSE identification parse. Record parse failures. Classify errors by key, not substring. Add `truncated` on identification. Per ARCHITECTURE.md §3.1–3.4.
- **Dependencies**: —
- **Target Files**: [`hardware-agent/src/agent/ot/untrusted.py`, `hardware-agent/src/agent/ot/modbus/client.py`, `hardware-agent/src/agent/ot/modbus/nse.py`, `hardware-agent/src/agent/ot/modbus/models.py`, `hardware-agent/tests/unit/test_ot_untrusted.py`, `hardware-agent/tests/unit/test_modbus_client.py`, `hardware-agent/tests/unit/test_modbus_nse.py`]
- **Tests**: `test_ot_untrusted.py` (128-char / 16-object caps, `truncated`); `test_modbus_nse.py` (zero-padded sid, recorded failure, `"ExceptionLogger 3000"`); `test_modbus_client.py` (bounded decode).
- **Success Criteria**:
  - Oversized identification is truncated or rejected at parse; the unit is kept; `truncated=True`.
  - One unreadable unit id keeps valid units and counts the failure.
  - A product name containing "exception" is not marked failed.
- **Status**: DONE (`a024255`)
- **Review Rejections**: 0

## Task 4: Isolate inventory, pace probes, corroborate profiles
- **Description**: One bad FC43 must not erase sibling units. Sleep `inter_request_delay_ms` before every FC43 probe. Identity-only matches may only apply a conservative profile. Absent ranges summarise as `None`. Restore `results.get(ip)` in the port stage. Per ARCHITECTURE.md §3.2, §3.5–3.6, §4.1, §5.1.
- **Dependencies**: Task 3
- **Target Files**: [`hardware-agent/src/agent/ot/modbus/inventory.py`, `hardware-agent/src/agent/ot/modbus/mapper.py`, `hardware-agent/src/agent/ot/policy.py`, `hardware-agent/src/agent/scanner/stages.py`, `hardware-agent/tests/unit/test_modbus_inventory.py`, `hardware-agent/tests/unit/test_modbus_mapper.py`, `hardware-agent/tests/unit/test_modbus_profile_corroboration.py`]
- **Tests**: `test_modbus_inventory.py` (per-unit isolation, injected sleep); `test_modbus_mapper.py` (absent summary); `test_modbus_profile_corroboration.py` (widen / narrow / CIDR-MAC).
- **Success Criteria**:
  - A `struct.error` on unit 3 keeps units 1, 2, 4.
  - Consecutive identification probes are separated by at least the configured delay.
  - Identity alone cannot widen; CIDR or MAC can; a narrower profile always applies.
  - Empty numeric lists do not report min/max 0.
- **Status**: DONE (`e2dd657`)
- **Review Rejections**: 0

## Task 5: Keyed digest and strip process data from the contract
- **Description**: HMAC-SHA256 digest on the Pi. Remove `validations`, raw values, aggregates, and `value_sha256` from agent, backend ingest, OpenAPI, and the example payload. Add `value_digest`, `truncated`, `write_requests_sent`. `extra="forbid"` on the four remaining Modbus models. Per ARCHITECTURE.md §2 and INTEGRATION.md §2.
- **Absorbed**: In-memory dataclass still computes absent summaries (Task 4 owns the lying-empty-list fix). Constants `DIGEST_*` have no branch of their own.
- **Dependencies**: Task 4
- **Target Files**: [`hardware-agent/src/agent/ot/digest.py`, `hardware-agent/src/agent/ot/modbus/models.py`, `hardware-agent/src/agent/ot/modbus/mapper.py`, `hardware-agent/src/agent/normalize/contracts.py`, `backend/src/api/schemas/industrial.py`, `backend/src/api/schemas/scan.py`, `contracts/openapi/openapi.yaml`, `contracts/examples/scan_result.example.json`, `hardware-agent/tests/unit/test_ot_digest.py`, `hardware-agent/tests/unit/test_modbus_mapper.py`, `hardware-agent/tests/test_contract_models.py`, `backend/tests/test_ingest_schema.py`, `backend/tests/test_contract_fidelity.py`]
- **Tests**: `test_ot_digest.py` (keyed, stable, different per address, no key → `None`); `test_contract_models.py` and `test_contract_fidelity.py` (removed fields absent, `ModbusValidationPayload` gone); `test_modbus_mapper.py` with `caplog` (no process value in logs).
- **Success Criteria**:
  - Wire, example JSON, and ingest models have no `values` / aggregates / `validations`.
  - Digest matches `hmac-sha256:` plus 64 hex, or is null.
  - Agent-side models reject extras at least as strictly as the backend.
- **Status**: DONE (`3803ae6`)
- **Review Rejections**: 0

## Task 6: Bound the OT stage, prove read-only, recover lost service evidence
- **Description**: OT stage and host deadlines, `ot_stage_deadline` event, metadata flags without flipping `partial_result`. `ReadOnlyModbusClient` plus reachability test. Measured write counter. Egress-only AST walk. Deep-stage `detect_services` recovery. Wire inventory pacing and `results.get(ip)` if Task 4 left a stub. Per ARCHITECTURE.md §5, §6.1.
- **Absorbed**: `MAX_OT_STAGE_SECONDS` / `MAX_OT_HOST_SECONDS` have no test except the stage that uses them. `progress.py` kind addition is observable only through the stage and the progress screen (Task 7 asserts the live line).
- **Dependencies**: Task 5
- **Target Files**: [`hardware-agent/src/agent/ot/modbus/readonly.py`, `hardware-agent/src/agent/ot/modbus/client.py`, `hardware-agent/src/agent/ot/policy.py`, `hardware-agent/src/agent/scanner/stages.py`, `hardware-agent/src/agent/scanner/progress.py`, `hardware-agent/src/agent/discovery/service_detection.py`, `hardware-agent/tests/unit/test_modbus_readonly.py`, `hardware-agent/tests/unit/test_egress_only.py`, `hardware-agent/tests/unit/test_modbus_stage.py`, `hardware-agent/tests/unit/test_deep_stage_service_recovery.py`, `hardware-agent/tests/unit/test_nspi_constants.py`]
- **Tests**: `test_modbus_readonly.py` (`write_register` raises `WriteAttemptError`); `test_egress_only.py`; `test_modbus_stage.py` (deadline, measured write counter, metadata seconds, `partial_result` unchanged); `test_deep_stage_service_recovery.py`; `test_nspi_constants.py` (defaults produce a non-`None` OT deadline).
- **Success Criteria**:
  - Default config enforces count, delay, and OT time bounds.
  - Ceiling stops the OT stage, keeps evidence, stamps `modbus_stage_deadline_reached` and `modbus_stage_deadline_seconds`.
  - No listening socket under `src/agent/`.
  - A host with open ports and a lost deep step keeps earlier service evidence.
- **Status**: DONE (`5072001`)
- **Review Rejections**: 0

## Task 7: Validate depth where it acts and restore completed-with-partial
- **Description**: `validate_nspi_depth` on `ScanRunner.__init__` before any request. Headless delegates. Progress screen catches `UnsupportedScanDepth` and implements DESIGN.md §2 and §4 (incomplete vs stopped vs refused) plus the live `⏱` line for `ot_stage_deadline` (DESIGN.md §3.1). Restore ADR-010 success path on `main`. Per ARCHITECTURE.md §4.2, §6. CLAUDE.md: both `ScanRunner` construction sites.
- **Dependencies**: Task 6
- **Target Files**: [`hardware-agent/src/agent/config.py`, `hardware-agent/src/agent/scanner/errors.py`, `hardware-agent/src/agent/scanner/runner.py`, `hardware-agent/src/agent/headless.py`, `hardware-agent/src/agent/tui/screens/scan_progress.py`, `hardware-agent/src/agent/tui/screens/home.py`, `hardware-agent/tests/unit/test_scan_depth_validation.py`, `hardware-agent/tests/unit/test_scan_progress_screen.py`, `hardware-agent/tests/unit/test_scan_runner_partial.py`, `hardware-agent/tests/unit/test_workspace.py`]
- **Tests**: `test_scan_depth_validation.py` and `test_scan_progress_screen.py` (refused depth, `interrupted_stage=None` is not "an earlier stage", OT ceiling does not force `badge-incomplete`); `test_scan_runner_partial.py` (completed vs genuine failure); `test_workspace.py` (completed-with-partial not in `_FAILED_TERMINATED_BY`).
- **Success Criteria**:
  - Unpermitted depth is refused before any active request from headless and from the TUI path through `ScanProgressScreen`.
  - Finished with skipped hosts: `terminated_by="completed"`, `partial_result=True`, `interrupted_stage=None`.
  - ScanModeScreen stays unchanged (`disabled=True` on active validation).
- **Status**: DONE (`3c6f67d`)
- **Review Rejections**: 0

## Task 8: Render device text and digests on the results screen
- **Description**: Escape every device string; apply DESIGN.md display limits and notices; range lines show status and 8 hex of `hmac-sha256:` digest; Limits line when `modbus_stage_deadline_reached`. No process statistics. Per DESIGN.md §1, §3.3, §5 and ARCHITECTURE.md §3.7.
- **Absorbed**: `tui/markup.py` `safe()` cannot be tested except through the screen that uses it.
- **Dependencies**: Task 5, Task 6
- **Target Files**: [`hardware-agent/src/agent/tui/markup.py`, `hardware-agent/src/agent/tui/screens/scan_view.py`, `hardware-agent/tests/unit/test_tui_scan_view.py`]
- **Tests**: `test_tui_scan_view.py` — vendor `[/nope]` renders literally with no `MarkupError`; no `nonzero `/`min `/`max ` tokens; `digest a1b2c3d4`; notice when shortened; Limits line from metadata flag.
- **Success Criteria**:
  - Hostile markup does not raise; `[/b]` appears as typed.
  - Parse-time `truncated` is independent of the 48-character display cut.
  - Readable range with no key shows `digest not recorded`.
- **Status**: DONE (`2bf16c3`)
- **Review Rejections**: 0

## Task 9: Persist industrial observations
- **Description**: Migration `20260912_21`: `industrial_services`, `modbus_units`, `findings.modbus_unit_id`, `orgs.ot_digest_key`, RLS and grants. Persist on ingest, idempotent, unit-attributed findings. Provisioner issues or reuses the org digest key. Per ARCHITECTURE.md §2.4, §8 and INTEGRATION.md §3–4.
- **Dependencies**: Task 1, Task 5
- **Target Files**: [`backend/alembic/versions/20260912_21_industrial_observations.py`, `backend/src/api/models/persistence.py`, `backend/src/api/models/identity.py`, `backend/src/api/services/industrial.py`, `backend/src/api/services/persistence.py`, `backend/src/api/management/provision_agent.py`, `backend/src/api/core/config.py`, `backend/tests/test_industrial_observations_migration.py`, `backend/tests/test_industrial_persistence.py`, `backend/tests/test_provision_agent.py`]
- **Tests**: `test_industrial_observations_migration.py` (empty, from `20260905_19`, reversible); `test_industrial_persistence.py` (lifecycle fields, idempotent ingest, `FindingRead.modbus_unit`); `test_provision_agent.py` (one key per org).
- **Success Criteria**:
  - Upgrade from empty and from the last released state reaches head without rewriting old revisions.
  - Downgrade of the repair revisions returns a consistent earlier state.
  - Same scan ingested twice yields one row per unit.
  - Retention days 180 is stated in config. No pruning job.
- **Status**: DONE (`dc2a4a9`)
- **Review Rejections**: 0

## Task 10: Read industrial observations, degrade bad rows, regenerate types
- **Description**: Read views on host/scan/finding APIs. `_validate_or_degrade` for OS and OT JSON. Organisation isolation. Generated frontend types only. Docs drift in ARCHITECTURE.md §9.5 except ADR-019 status (already Accepted). Superseded-by banner on 042 ARCHITECTURE.md §7. Per ARCHITECTURE.md §2.5, §7.1, §9.5, §10.2–10.3.
- **Absorbed**: OpenAPI read-schema edits cannot be asserted except through `test_read_schema.py` / `test_contract_fidelity.py`. Frontend is `openapi.d.ts` only. Doc files have no failing test; reviewer greps the §9.5 list.
- **Dependencies**: Task 9
- **Target Files**: [`backend/src/api/schemas/read.py`, `backend/src/api/services/read.py`, `backend/tests/test_industrial_read_routes.py`, `backend/tests/test_unreadable_row_degradation.py`, `backend/tests/test_read_schema.py`, `backend/tests/test_contract_fidelity.py`, `contracts/openapi/openapi.yaml`, `frontend/src/types/openapi.d.ts`, `specs/042-nspi-modbus-ot/ARCHITECTURE.md`, `docs/CLI.md`, `docs/README.md`, `docs/DEV-SETUP.md`, `docs/tests/nspi-modbus-inventory.md`, `docs/tests/nspi-modbus-read-only-mapping.md`, `docs/roadmap/TASKS.md`, `docs/roadmap/README.md`, `.claude/docs/hardware-agent/ot.md`, `.claude/docs/hardware-agent/index.md`, `.claude/docs/hardware-agent/overview.md`, `.claude/docs/hardware-agent/daemon.md`, `.claude/docs/hardware-agent/tui.md`, `.claude/docs/backend/migrations.md`, `.claude/docs/backend/models.md`, `.claude/docs/backend/schemas.md`, `.claude/docs/backend/services.md`, `.claude/docs/contracts.md`, `.claude/docs/index.md`, `.claude/CLAUDE.md`]
- **Tests**: `test_industrial_read_routes.py` (read-back equality, org isolation); `test_unreadable_row_degradation.py` (200, other hosts, `unreadable_fields`); `test_read_schema.py` / `test_contract_fidelity.py` (no value fields, no `ModbusValidationPayload`). Frontend gate: `npm run gen:types && npm run typecheck && npm run build`.
- **Success Criteria**:
  - Host read describes the same service, units, identification, and range statuses as ingest.
  - One junk JSON column does not 500 the list.
  - No frontend component or screen changes.
  - Each path in ARCHITECTURE.md §9.5 is updated (ADR-019 already done).
- **Status**: DONE (`b5ab84e`)
- **Review Rejections**: 0

---

## Dependency graph

```text
#1 ──→ #2
 #     └──→ #9 ──→ #10
#3 ──→ #4 ──→ #5 ──→ #6 ──→ #7
                  │         └──→ #8
                  └──→ #9
```

Parallel tracks: Alembic (#1) beside parse bounds (#3). After #6, progress/outcome (#7) beside results screen (#8). Persistence (#9) after merge (#1) and contract (#5). Task 5 waits on Task 4 so `mapper.py` is not edited in parallel.

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Merge the forked Alembic heads | DONE `0ee7360` |
| 2 | Fail the backend suite when no database is set | DONE `a32228e` |
| 3 | Bound and classify untrusted device data at parse | DONE `a024255` |
| 4 | Isolate inventory, pace probes, corroborate profiles | DONE `e2dd657` |
| 5 | Keyed digest and strip process data from the contract | DONE `3803ae6` |
| 6 | Bound the OT stage, prove read-only, recover lost service evidence | DONE `5072001` |
| 7 | Validate depth where it acts and restore completed-with-partial | DONE `3c6f67d` |
| 8 | Render device text and digests on the results screen | DONE `2bf16c3` |
| 9 | Persist industrial observations | DONE `dc2a4a9` |
| 10 | Read industrial observations, degrade bad rows, regenerate types | DONE `b5ab84e` |
