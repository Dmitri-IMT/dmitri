# TASKS — Headless agent entrypoint (DMI-51, spec 012)

Execution checklist for the feature-orchestrator. Specs: `TRUTH.md`, `ARCHITECTURE.md`
(no `DESIGN.md` — no TUI screen changes). Ledger: `POOP.md`.

## Dependency graph

```
Task 1 (config SCAN_MODES) ──┐
                             ├──> Task 3 (headless.py) ──> Task 4 (CLI + exit alignment)
Task 2 (run_blocking)     ───┘

DMI-69 — result-write failure is fatal, not a traceback (ship-audit follow-up):

Task 5 (prune_results OSError) ──> Task 6 (headless fatal + CLI stderr) ──> Task 7 (docs)
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
    **Superseded by Task 6 decision 3:** on a result-write fatal, `result_path` is null but
    `scan_id` is non-null because the captured payload survives.
  - Spec-000 contract docs updated; BUG-004 and plans/01 carry superseded-by-spec-012 notes.
  - No TUI screen/flow/output change.
  - `uv run pytest` and `uv run ruff check` pass.
- **Status**: COMPLETED
- **Review Rejections**: 1

---

# DMI-69 — result-write failure (ship-audit follow-up)

Tasks 1–4 shipped spec 012 and are closed. Tasks 5–7 close a gap the ship audit found in the
module Task 3 created: `run_headless_scan` calls `write_scan_result` unguarded, so a scan that
**completes successfully** but cannot be persisted (unwritable workspace, disk full) escapes as an
uncaught `OSError` — `dmitri agent` dies with a traceback and exits `1`, outside the ADR-012
contract that requires `20`.

This introduces a **third flavor of `fatal`** that neither ADR-010 nor ADR-012 anticipated:
*everything succeeded, then persistence failed*. Six decisions were settled with the user and
**override the DMI-69 issue text where they conflict** (the issue's Expected list is wrong on three
points; it will be amended in Linear separately):

1. **Outcome is `fatal`, not `partial`.** `fatal` is the only outcome whose "Result JSON written?
   no" is truthful. `partial` promises a `result_path` that does not exist. Per `CONTEXT.md`, a Pi
   that "took the command, then broke" → Command `failed`, and only `fatal` maps there.
2. **`prune_results` swallows `OSError`** — it runs after a successful write and deletes *old*
   files; a failed `unlink` must never invalidate a new good scan.
3. **The payload is returned, not discarded** (the issue says `payload=None` — that is wrong; the
   scan found things, and `None` would claim it found nothing). Rule: *payload = what the scan
   found, or `None` if it never found anything.*
4. **The error is printed to stderr** by the CLI — nothing reads `HeadlessScanResult.error` today,
   so the message the issue asks for would otherwise be invisible.
5. **`error` is an `OSError` with a descriptive message**, not a string — the field is typed
   `Exception | None`. No new exception class (CLAUDE.md §2: no single-use abstractions).
6. **The stale docs are amended, no new ADR** — nothing new is being decided, and ADR-012 §2 forbids
   new outcome vocabulary.

## Task 5: Contain OSError in prune_results

- **Description**: Per DMI-69 decision 2: `prune_results` in `scanner/workspace.py` deletes the oldest result files and is called by `write_scan_result` **after** the new file is already written. An `OSError` from its `unlink` loop currently propagates out of `write_scan_result`, making a fully successful write look like a total failure — the caller reports "result lost" while the file sits on disk. Contain `OSError` around the unlink loop so pruning cannot invalidate a successful write. Pruning is opportunistic housekeeping, not part of the persistence contract. Do **not** touch `write_scan_result`'s own `mkdir`/`write_text` — those must still raise, because after this task an `OSError` escaping `write_scan_result` must mean exactly one thing: **no result file exists**. Task 6 depends on that invariant. Precedent: `specs/011-nspi-port-stage-fix/ARCHITECTURE.md` gave the sibling `prune_logs` the same "never raise" treatment and recorded `prune_results` as deliberately deferred ("`prune_results` is out of scope (unchanged)").
- **Dependencies**: —
- **Target Files**: [hardware-agent/src/agent/scanner/workspace.py, hardware-agent/tests/unit/test_workspace.py]
- **Success Criteria**:
  - An `OSError` raised by `Path.unlink` during pruning does not propagate out of `prune_results`.
  - When pruning fails, `write_scan_result` still returns the written path and the new file exists on disk with valid `ScanPayload` JSON.
  - `OSError` from `write_scan_result`'s own `mkdir` and `write_text` still propagates (regression guard for the invariant Task 6 relies on).
  - The six existing `TestPruneResults` tests and `test_prunes_to_10_after_writing` pass with zero edits.
  - Containment is **per file**, not around the whole loop: one unlinkable file must not abort pruning of the rest. `files` is sorted oldest-first, so a permanently stuck old file would otherwise be first in line on every call and `results/` would grow unbounded for the life of the appliance.
  - A test covers "one old file fails to unlink, the rest are still pruned".
  - `uv run pytest` and `uv run ruff check` pass.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 6: Fatal outcome when the result write fails + stderr visibility

- **Description**: Per DMI-69 decisions 1, 3, 4, 5. In `headless.py`, wrap the `write_scan_result(captured_payload, str(workspace_root))` call (reached only when a payload was captured, i.e. the scan already completed or ended partial) in a **narrow** `try/except OSError`, returning `HeadlessScanResult(outcome="fatal", payload=captured_payload, result_path=None, error=OSError(f"Scan completed but the result file could not be written to {workspace_root}: {exc}"))`. Mirror the shape of the existing early-return fatal a few lines above. `OSError` only — no broad exception handling, no retry, no alternate storage. Note the payload **is** returned (decision 3) — this deliberately contradicts the DMI-69 issue text, and the existing pre-discovery fatal keeps `payload=None` because there the scan genuinely never produced one. In `cli.py`'s `_run_agent`, print `result.error` to stderr when it is not `None`, before `raise SystemExit(...)`. The stdout JSON line keeps **exactly** the keys `{"outcome", "result_path", "scan_id"}` — its shape is frozen by ADR-012 §3, so the error goes to stderr only (the channel `StderrReporter` already uses). Note this also gives the pre-existing pre-scan `mkdir` fatal a visible message for the first time.
- **Dependencies**: 5
- **Target Files**: [hardware-agent/src/agent/headless.py, hardware-agent/src/agent/cli.py, hardware-agent/tests/unit/test_headless.py, hardware-agent/tests/unit/test_cli_agent.py]
- **Success Criteria**:
  - `write_scan_result` raising `OSError` after a completed scan → `run_headless_scan` returns `outcome="fatal"`, `result_path is None`, `payload is captured_payload` (**not** None), and `error` is an `OSError` whose message states the scan completed and the result could not be written.
  - The exception does not escape `run_headless_scan`.
  - Writable-workspace behavior is unchanged: a completed scan still returns `outcome="completed"` with a real `result_path`, and a partial still returns `"partial"`.
  - Only `OSError` is caught — no bare `except`, no `Exception`.
  - `cli.py` exits `20` on this path and prints the error message to stderr; stdout still carries exactly one JSON line with keys `outcome`, `result_path`, `scan_id` and no others.
  - Because the payload survives, `scan_id` in that JSON line is **non-null** on this fatal path (superseding Task 4's "null result_path/scan_id on fatal" criterion, which assumed the only fatal was pre-scan).
  - Tests monkeypatch `agent.headless.write_scan_result` — **no `chmod`-based test** (there is none in the suite, and it silently passes as root in CI).
  - The existing fatal test asserting `payload is None` is **not** edited — it covers the pre-discovery `FatalScanError` path where no payload was ever produced.
  - `headless.EXIT_CODES` / `INVALID_INPUT_EXIT` assertions and `test_headless_imports_shared_runner_and_writer` stay green.
  - `uv run pytest` and `uv run ruff check` pass.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 7: Documentation alignment

- **Description**: Per DMI-69 decision 6. Tasks 5–6 make several documents actively false, because they all describe `fatal` as something that can only happen *before* data exists. Amend, in this order: **(a)** `docs/adr/ADR-012-headless-exit-code-contract.md` — §1's fatal row says "fatal before any preservable data"; re-anchor it on the truthful invariant, **"no result JSON written"**, and add the completed-but-unwritten case; §2 ("outcome derives from the runner's terminal state — no new vocabulary") needs a carve-out noting this fatal is an I/O failure layered on an already-classified payload, **not** a projection of `terminated_by`/`partial_result`. **(b)** `docs/adr/ADR-010-scan-contingency-policy.md` §2 — the decision table says "Fatal **depois** da descoberta → **PARAR**, emitir parcial"; add a row for a fatal **in the write itself**: stop, no partial, because the preservation channel is what failed. **This file is written in Portuguese — match it.** **(c)** `docs/CLI.md` — the exit-code table's `20` row ("Fatal startup or environment error — nmap missing, unwritable workspace, agent fatal before preservable data") is the live CLI reference and is wrong; fix it and add an example of the completed-but-unwritten JSON line plus its stderr message. **(d)** `specs/012-headless-agent-entrypoint/ARCHITECTURE.md` — §3 point 4 ("Persist + classify") describes `write_scan_result` as a step that cannot fail (add the third branch); the §4 outcome table duplicates ADR-012's false fatal row; the sentence following it ("The `completed`/`partial`/`fatal` split is exactly the runner's own terminal classification") is the load-bearing claim this change breaks; and § Testing expectations needs a persist-failure row. **(e)** `specs/012-headless-agent-entrypoint/TRUTH.md` (~lines 36-41) — "the same conditions are fatal" asserts TUI/headless parity; the TUI has no exit-code contract, so carve out this headless-only failure mode. **(f)** This file — add a note under Task 4's success criteria that its "null result_path/scan_id on fatal" parenthetical is superseded by Task 6 decision 3; **do not rewrite the COMPLETED entry itself**. **(g)** `docs/adr/ADR-011-pi-command-channel.md` (~lines 112, 142) — the wire statuses `running|uploading|done|failed` never enumerate the `outcome`→status mapping; add a clarifying note that headless `fatal` → `failed`, including the case where the scan succeeded but could not be persisted (the daemon may still hold the payload from the return value). **(h)** `docs/roadmap/PI.md` (~line 118) — "Uploads results via `POST /api/v1/scans`" assumes a completed scan always has an uploadable result; footnote the exception. **Also fix pre-existing drift in (d)**: ARCHITECTURE.md points at `tui/results.py:write_scan_result` in ~11 places, but DMI-68 (commit `62a86e1`) moved it to `scanner/workspace.py`; correct every occurrence. **Do not touch** `POOP.md` (append-only ledger), `docs/tests/nspi-september/*` (dated field record), `specs/011-nspi-port-stage-fix/*` (its "prune_results is out of scope" was true for spec 011), or `specs/000-agent-tui/*` (absent from this checkout — `.gitignore:218`; ADR-012 §4 keeps its exit-`1` wording as history).
- **Dependencies**: 6
- **Target Files**: [docs/adr/ADR-012-headless-exit-code-contract.md, docs/adr/ADR-010-scan-contingency-policy.md, docs/adr/ADR-011-pi-command-channel.md, docs/CLI.md, docs/roadmap/PI.md, specs/012-headless-agent-entrypoint/ARCHITECTURE.md, specs/012-headless-agent-entrypoint/TRUTH.md, specs/012-headless-agent-entrypoint/TASKS.md]
- **Success Criteria**:
  - No surviving claim in any of the target files that `fatal` means "before any preservable data" or equivalent.
  - ADR-012's fatal row is anchored on "no result JSON written"; §2 carries the carve-out for the I/O-failure fatal.
  - ADR-010's new decision-table row is written in Portuguese, matching the file.
  - `docs/CLI.md`'s `20` row is accurate and shows the completed-but-unwritten example.
  - Spec 012 ARCHITECTURE.md has no remaining reference to `tui/results.py`; all point to `scanner/workspace.py`.
  - Task 4's success criteria carry a superseding note; the entry itself is otherwise unedited and stays COMPLETED.
  - ADR-011 and PI.md carry the daemon-facing note.
  - No edits to POOP.md, docs/tests/nspi-september/*, specs/011-*, or specs/000-*.
  - Docs only — **zero changes under `hardware-agent/`**.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Status table

| Task | Name | Status | Rejections |
|------|------|--------|------------|
| 1 | config SCAN_MODES | COMPLETED | 0 |
| 2 | ScanRunner.run_blocking() | COMPLETED | 0 |
| 3 | agent/headless.py | COMPLETED | 0 |
| 4 | CLI agent branch + exit alignment | COMPLETED | 1 |
| 5 | prune_results OSError containment | COMPLETED | 1 |
| 6 | headless write-failure fatal + CLI stderr | COMPLETED | 0 |
| 7 | documentation alignment | COMPLETED | 0 |
