# TASKS — Headless agent entrypoint (DMI-51, spec 012)

Execution checklist for the feature-orchestrator. Specs: `TRUTH.md`, `ARCHITECTURE.md`
(no `DESIGN.md` — no TUI screen changes). Ledger: `POOP.md`.

## Dependency graph

```
Task 1 (config SCAN_MODES) ──┐
                             ├──> Task 3 (headless.py) ──> Task 4 (CLI + exit alignment)
Task 2 (run_blocking)     ───┘
```

## Task 1: Add SCAN_MODES tuple to config

- **Description**: Add `SCAN_MODES: tuple[str, ...] = ("quick", "standard", "extensive", "nspi", "max")` to `config.py` as the single enumerable source of truth for the mode set (currently only repeated `Literal`s). No other config change — no timeout, budget, or knob. See ARCHITECTURE.md § Data model.
- **Dependencies**: —
- **Target Files**: [hardware-agent/src/agent/config.py, hardware-agent/tests/unit/test_config_modes.py (or extend test_config_timeouts.py)]
- **Success Criteria**:
  - `config.SCAN_MODES == ("quick", "standard", "extensive", "nspi", "max")`.
  - Test asserts `SCAN_MODES` equals `typing.get_args(...)` of the `ScanPayload.scan_mode` `Literal` (drift guard).
  - No other change to `config.py`; existing tests remain green.
  - `uv run pytest` and `uv run ruff check` pass.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Add ScanRunner.run_blocking()

- **Description**: Add a thin public method `run_blocking(self) -> None` to `ScanRunner` in `tui/scanner.py` that runs `self._run()` on the calling thread (results still delivered through the existing `on_complete`/`on_error` callbacks). Additive only: no constructor-signature change, no change to `start()`, no other edits to the file (spec 011 coordinates on this file — touch only the new method). See ARCHITECTURE.md § Design decision 2.
- **Dependencies**: —
- **Target Files**: [hardware-agent/src/agent/tui/scanner.py, hardware-agent/tests/unit/test_scan_runner_events.py (only if a run_blocking test is added there; existing tests must not be edited)]
- **Success Criteria**:
  - `ScanRunner.run_blocking()` exists, is public, runs the pipeline synchronously, and delivers results via the existing callbacks.
  - `ScanRunner.__init__` signature unchanged; `ScanProgressScreen` and `home.py` untouched.
  - All existing `test_scan_runner_*` and `test_scan_progress_screen.py` tests pass with zero edits.
  - `uv run pytest` and `uv run ruff check` pass.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: New headless front-door module agent/headless.py

- **Description**: Create `hardware-agent/src/agent/headless.py` per ARCHITECTURE.md § Design decision 3: `validate_inputs(mode, subnet)` (mode ∈ `config.SCAN_MODES`; subnet must contain `/` and parse as `ipaddress.IPv4Network(strict=False)`; else raise `InvalidScanInput`), `run_headless_scan(mode, subnet, *, workspace_root=None, reporter=None, runner=None) -> HeadlessScanResult` (validate → resolve workspace via `agent.paths` `load_config`/`default_results_dir` → pre-create `results/` (OSError → outcome="fatal" before scanning) → construct `ScanRunner` with capturing callbacks → `run_blocking()` → on payload: `write_scan_result` + classify from `metadata["partial_result"]`; on error: outcome="fatal", no JSON), `HeadlessScanResult` dataclass, `InvalidScanInput(ValueError)`, `EXIT_CODES = {"completed": 0, "partial": 10, "fatal": 20}`, `INVALID_INPUT_EXIT = 2`, `StderrReporter` (implements `ScanReporter`: `emit(event)` prints `event.message` to stderr). Must not import `textual` or the `agent.tui` package except `agent.tui.scanner` (ScanRunner) and `agent.tui.results` (write_scan_result). No forked scan logic.
- **Dependencies**: 1, 2
- **Target Files**: [hardware-agent/src/agent/headless.py, hardware-agent/tests/unit/test_headless.py]
- **Success Criteria**:
  - Same shape: headless run with a fake runner into `tmp_path` writes `<ts>_<subnet-slug>.json` under `tmp_path/results` that passes `ScanPayload.model_validate`; structure matches a direct `ScanRunner` run of the same inputs (mirror `test_scan_runner_partial.py` harness).
  - Programmatic result: `run_headless_scan(...)` returns `HeadlessScanResult(outcome="completed", payload=<ScanPayload>, result_path=<written file>)`.
  - Failure semantics: monkeypatched `stages.run_port_stage` raising `FatalScanError` → `outcome="partial"`, JSON has `partial_result is True`, `terminated_by == "error"`, `interrupted_stage == "ports"`; pre-discovery fatal → `outcome="fatal"`, no JSON.
  - One pipeline: monkeypatching `stages.run_port_stage` changes the headless result; `headless` imports `ScanRunner`/`write_scan_result` (no reimplementation).
  - Input validation: unknown mode, `192.168.1.5` (no `/`), and malformed subnet each raise `InvalidScanInput`; `discover_hosts` never called; no `results/` dir created.
  - Exit-code contract: `headless.EXIT_CODES == {"completed": 0, "partial": 10, "fatal": 20}` and `INVALID_INPUT_EXIT == 2` (ADR-012 drift guard).
  - Existing TUI tests green with zero edits.
  - `uv run pytest` and `uv run ruff check` pass.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: CLI `dmitri agent` branch + exit-code alignment

- **Description**: Per ARCHITECTURE.md § Design decision 4: add an `agent` branch to `cli.py`'s hand-rolled dispatch (no argparse rewrite): `dmitri agent <mode> <subnet>` (wrong arity → usage error, exit 2); reuse `_check_nmap()` (missing → existing guidance, exit 20); call `run_headless_scan(mode, subnet, reporter=StderrReporter())`; on `InvalidScanInput` print message to stderr, exit 2; on success print one JSON line to stdout (`{"outcome", "result_path", "scan_id"}`, both null on fatal) and exit per `EXIT_CODES`. Update the usage string. Align existing exits: `_run_tui` nmap-missing `1→20`, top-level unknown-command `1→2`; update the two existing CLI tests in `tests/integration/test_tui_flows.py` (`test_cli_nmap_missing` → 20, `test_cli_unknown_command` → 2) and the two spec-000 contracts (`specs/000-agent-tui/contracts/cli.md`, `specs/000-agent-tui/checklists/requirements.md`); add a superseded-by-spec-012 note to `BUG-004` and `plans/01-cli-entry-and-skeleton.md` (historical records, content otherwise untouched).
- **Dependencies**: 3
- **Target Files**: [hardware-agent/src/agent/cli.py, hardware-agent/tests/integration/test_tui_flows.py, hardware-agent/tests/unit/test_cli_agent.py, specs/000-agent-tui/contracts/cli.md, specs/000-agent-tui/checklists/requirements.md, BUG-004 (superseded note), plans/01-cli-entry-and-skeleton.md (superseded note)]
- **Success Criteria**:
  - New `test_cli_agent.py`: `cli.main()` with monkeypatched `sys.argv` + stubbed `run_headless_scan` exits 0/10/20 per outcome, 2 for bad arity and `InvalidScanInput`, 20 when `_check_nmap()` stubbed False; mirrors the existing `test_cli_*` harness.
  - Updated existing tests: `test_cli_nmap_missing` expects 20, `test_cli_unknown_command` expects 2.
  - JSON line on stdout contains `outcome`, `result_path`, `scan_id` (`null` result_path/scan_id on fatal).
  - Spec-000 contract docs updated; BUG-004 and plans/01 carry superseded-by-spec-012 notes.
  - No TUI screen/flow/output change.
  - `uv run pytest` and `uv run ruff check` pass.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Status table

| Task | Name | Status | Rejections |
|------|------|--------|------------|
| 1 | config SCAN_MODES | COMPLETED | 0 |
| 2 | ScanRunner.run_blocking() | COMPLETED | 0 |
| 3 | agent/headless.py | COMPLETED | 0 |
| 4 | CLI agent branch + exit alignment | COMPLETED | 1 |
