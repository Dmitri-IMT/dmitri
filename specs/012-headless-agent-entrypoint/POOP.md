# POOP — spec 012

## agent-developer — Task 1

### Order Given
Task 1 from `specs/012-headless-agent-entrypoint/TASKS.md`: add `SCAN_MODES: tuple[str, ...] = ("quick", "standard", "extensive", "nspi", "max")` to `hardware-agent/src/agent/config.py` as the single enumerable source of truth for the mode set. No other config change; no tests (test-engineer follows).

### What, How & Why
Added the module-level `SCAN_MODES` tuple to `config.py`, placed immediately after the imports and before the `AgentSettings` dataclass. This gives `validate_inputs` in the upcoming `headless.py` (Task 3) an enumerable value to check `mode` membership against, since today the mode set only exists as repeated `Literal["quick", "standard", "extensive", "nspi", "max"]` annotations with no runtime-iterable form.

### Decisions Made
- Placed the tuple at module top level, above `AgentSettings`, rather than inside the class or near `TIMEOUTS`, since it is a standalone constant not tied to the dataclass.
- Did not change the existing `Literal` annotations on `AgentSettings.scan_mode` / `with_overrides` to reference `SCAN_MODES` — task scope is additive only ("No other config change").
- Left `_parse_scan_mode` (only recognizes `quick`/`standard`, part of the discontinued env-driven path) untouched — out of scope per TRUTH.md and the existing dead-code note.

### Code Changed
- Modified: `hardware-agent/src/agent/config.py`

## test-engineer — Task 1

### Order Given
Write tests for Task 1 of spec 012 (`config.SCAN_MODES`) per TASKS.md Success Criteria and ARCHITECTURE.md § Testing expectations, row "Modes source in sync": assert `config.SCAN_MODES == ("quick", "standard", "extensive", "nspi", "max")` and assert it equals `typing.get_args(...)` of the `ScanPayload.scan_mode` `Literal`, extending `test_config_timeouts.py` or creating `test_config_modes.py`, whichever mirrors existing patterns best.

### What, How & Why
Extended `hardware-agent/tests/unit/test_config_timeouts.py` (rather than creating a new file) since it already owns config-module constant/behavior assertions in the same file, and the new checks are a natural sibling to `TestResilienceConfigDefaults`. Added a `TestScanModes` class with two tests: `test_matches_documented_tuple` asserts `config.SCAN_MODES` equals the literal documented tuple; `test_matches_scan_payload_literal` reads `ScanPayload.model_fields["scan_mode"].annotation`, extracts its `Literal` args via `typing.get_args`, and asserts they equal `config.SCAN_MODES` — this is the drift guard so the config tuple and the pydantic contract's `Literal` cannot diverge silently.

### Decisions Made
- Chose to extend `test_config_timeouts.py` over creating `test_config_modes.py`: the file already tests other `config.py` module-level constants/behavior in a similar class-per-concept style, so a new small `TestScanModes` class fits without introducing a near-empty sibling file.
- Read `ScanPayload.scan_mode`'s `Literal` via `ScanPayload.model_fields["scan_mode"].annotation` + `typing.get_args` (pydantic v2 `model_fields` API) rather than importing internal contract internals, keeping the test black-box against the public model.
- No production code touched; no comments/docstrings added to the test file (existing module docstring at the top of the file was left untouched since it predates this change).
- Ran `uv run pytest tests/unit/test_config_timeouts.py -v` (20 passed) and a scoped `tests/test_contract_models.py` run alongside it to confirm no interaction with `ScanPayload` import elsewhere; did not run full `uv run pytest`/`ruff` suite since scope is limited to this one task's files.

### Code Changed
- Modified: `hardware-agent/tests/unit/test_config_timeouts.py`

## code-reviewer — Task 1

### Order Given
Review gate for Task 1 of spec 012: verify the coder's `SCAN_MODES` tuple addition to `hardware-agent/src/agent/config.py` and the test-engineer's `TestScanModes` in `hardware-agent/tests/unit/test_config_timeouts.py` against the Task 1 Success Criteria and ARCHITECTURE.md (§ Data model, Testing expectations "Modes source in sync"). Confirm surgical change, drift guard against `ScanPayload.scan_mode`, no comments/docstrings in new tests. Run full `uv run pytest` and `uv run ruff check`.

### What, How & Why
Reviewed `git diff` on both files. Production change is a single added line: `SCAN_MODES: tuple[str, ...] = ("quick", "standard", "extensive", "nspi", "max")`, placed after imports, no other config edits — matches ARCHITECTURE.md § Data model exactly. The test file adds `TestScanModes` with two tests: one asserting the literal tuple, one asserting `config.SCAN_MODES == typing.get_args(ScanPayload.model_fields["scan_mode"].annotation)` — the required drift guard. No comments or docstrings in the new test code.
Ran (from `hardware-agent/`): `uv run pytest -q` → 466 passed; `uv run ruff check src/agent/config.py tests/unit/test_config_timeouts.py` → All checks passed. Verified no `# ponytail:` markers present in either touched file (nothing to strip).

### Decisions Made
APPROVE. All four Success Criteria met: SCAN_MODES equals the documented tuple; the get_args drift guard against ScanPayload.scan_mode is asserted; config.py received no other change; pytest and ruff both pass. Change is surgical and matches the architecture spec.

### Code Reviewed
- hardware-agent/src/agent/config.py
- hardware-agent/tests/unit/test_config_timeouts.py

## agent-developer — Task 2

### Order Given
Task 2 from `specs/012-headless-agent-entrypoint/TASKS.md`: add a thin public method `run_blocking(self) -> None` to `ScanRunner` in `hardware-agent/src/agent/tui/scanner.py` that runs `self._run()` on the calling thread, results delivered through the existing `on_complete`/`on_error` callbacks. Additive only: no constructor-signature change, no change to `start()`, no other edits to the file; do not touch `ScanProgressScreen`, `home.py`, or any test.

### What, How & Why
Added `run_blocking(self) -> None: self._run()` directly below `start()` in `ScanRunner`. This gives the upcoming `headless.py` (Task 3) a public, non-underscore entry point to drive the pipeline synchronously on the calling thread instead of reaching into the private `_run()` across a module boundary, while `start()` keeps spawning a daemon thread for the TUI unchanged. `_run()` already delivers its result exclusively through `self._on_complete`/`self._on_error`, so no callback plumbing was needed — the new method is a one-line passthrough.

### Decisions Made
- Placed `run_blocking()` immediately after `start()` (both are the two public ways to drive `_run()`), rather than elsewhere in the class, to keep the two execution-mode entry points adjacent.
- Made no change to `__init__`, `start()`, or any other method — per ARCHITECTURE.md § Design decision 2 and the spec-011 coordination note (011 is also mid-edit on this file), keeping the diff to exactly the new method to avoid merge conflicts.
- No comments/docstrings added (project preference); no tests written (test-engineer follows).

### Verification
- `uv run pytest tests/unit/test_scan_runner_events.py tests/unit/test_scan_runner_partial.py -q` → 17 passed, zero edits to either test file.
- `uv run ruff check src/agent/tui/scanner.py` → All checks passed.
- `git diff` on the file shows exactly 3 added lines (the new method) and nothing else.

### Code Changed
- Modified: hardware-agent/src/agent/tui/scanner.py

## test-engineer — Task 2

### Order Given
Write tests for Task 2 of spec 012 proving `ScanRunner.run_blocking()` runs the pipeline synchronously on the calling thread and delivers the payload via `on_complete`. Add test(s) to `hardware-agent/tests/unit/test_scan_runner_events.py` mirroring its existing harness (fake `NmapRunner`, monkeypatched `check_network_connectivity`). Do not edit any existing test — additive only. No comments/docstrings.

### What, How & Why
Added a new `TestScanRunnerRunBlocking` class at the end of `test_scan_runner_events.py` with two tests. `test_run_blocking_delivers_payload_via_on_complete` mirrors `TestScanRunnerNoReporter.test_run_completes_without_reporter` but calls `runner.run_blocking()` instead of `runner._run()`, asserting the captured `on_complete` list has exactly one payload — proving the public method delivers the same result as the private one it wraps. `test_run_blocking_does_not_spawn_thread` monkeypatches `agent.tui.scanner.threading.Thread` to a callable that raises `AssertionError` if constructed, then calls `run_blocking()` and asserts both that `on_complete` still received the payload and that `runner._thread` remains `None` — this proves the pipeline ran on the calling thread with zero thread construction, not merely that a background thread happened to finish before the assertion (a race that a bare `join()`-based test would leave open).

### Decisions Made
- Used a monkeypatched, exception-raising `threading.Thread` stub (rather than e.g. asserting on timing or a mutable flag toggled inside a thread) as the mocking boundary to prove synchronicity deterministically — any accidental thread spawn inside `run_blocking()`/`_run()` fails the test immediately instead of being masked by fast completion.
- Reused the existing `_FakeRunner` and `check_network_connectivity` monkeypatch pattern already present in the file rather than introducing new fixtures.
- Did not test the `on_error` path for `run_blocking()` separately since `run_blocking()` is a pure passthrough to the already-tested `_run()` (`TestScanRunnerFailure` covers `on_error` via `_run()` directly); Task 2's success criteria only require proving synchronous execution and `on_complete` delivery for the new method.
- No production code changed; no comments/docstrings added.

### Code Changed
- Modified: hardware-agent/tests/unit/test_scan_runner_events.py

## code-reviewer — Task 2

### Order Given
Review gate for Task 2 of spec 012: verify the coder's `run_blocking()` addition to `hardware-agent/src/agent/tui/scanner.py` (only production diff on the file, ~3 lines, no other changes) and the test-engineer's `TestScanRunnerRunBlocking` (2 additive tests) in `hardware-agent/tests/unit/test_scan_runner_events.py` against the Task 2 Success Criteria and ARCHITECTURE.md § Design decision 2. Confirm the method is public and synchronous, no constructor/`start()`/signature change, existing tests unedited, `ScanProgressScreen`/`home.py` untouched by Task 2, no comments/docstrings. Run full `uv run pytest` and `uv run ruff check`.

### What, How & Why
Reviewed `git diff` on both files. Production change is exactly 3 added lines: `def run_blocking(self) -> None: self._run()`, placed after `start()` — public, synchronous, delivers results through the existing callbacks; `__init__` and `start()` unchanged. Test file adds only a `TestScanRunnerRunBlocking` class (2 tests) at the end, reusing the existing `_FakeRunner` + monkeypatched `check_network_connectivity` harness; no existing test edited. No comments/docstrings in new code. Confirmed the `scan_progress.py` and `home.py` diffs on this branch are spec-011 import-path moves (`agent.tui.config` → `agent.paths`), not Task 2 work; run_blocking is additive with no new constructor parameter, so the CLAUDE.md integration-threading rule does not apply.
Ran (from `hardware-agent/`): scoped `uv run pytest tests/unit/test_scan_runner_events.py tests/unit/test_scan_progress_screen.py -q` → 47 passed; full `uv run pytest -q` → 468 passed; `uv run ruff check src/agent/tui/scanner.py tests/unit/test_scan_runner_events.py` → All checks passed. Grepped for `# ponytail:` markers across hardware-agent — none present, nothing to strip.

### Decisions Made
APPROVE. All four Success Criteria met: `run_blocking()` exists, is public, runs the pipeline synchronously via `_run()`, and delivers results through the existing callbacks; `__init__` signature unchanged and `ScanProgressScreen`/`home.py` untouched by this task; all existing `test_scan_runner_*` and `test_scan_progress_screen.py` tests pass with zero edits; pytest and ruff both green. Change is surgical and confined to the new method per the spec-011 coordination note.

### Code Reviewed
- hardware-agent/src/agent/tui/scanner.py
- hardware-agent/tests/unit/test_scan_runner_events.py

## agent-developer — Task 3

### Order Given
Task 3 from `specs/012-headless-agent-entrypoint/TASKS.md`: create `hardware-agent/src/agent/headless.py` per ARCHITECTURE.md § Design decision 3 / § Data model: `InvalidScanInput(ValueError)`, `HeadlessScanResult` dataclass, `EXIT_CODES`/`INVALID_INPUT_EXIT`, `validate_inputs(mode, subnet)`, `StderrReporter`, `run_headless_scan(mode, subnet, *, workspace_root=None, reporter=None, runner=None) -> HeadlessScanResult`. Must not import `textual` or any `agent.tui` module beyond `agent.tui.scanner.ScanRunner` and `agent.tui.results.write_scan_result`; workspace default from `agent.paths`. No forked scan logic. Do not write tests (test-engineer follows) and do not touch `cli.py` (Task 4).

### What, How & Why
Created `headless.py` as pure glue over the existing pipeline. `validate_inputs` checks `mode in config.SCAN_MODES` then requires `"/"` in `subnet` before parsing with `ipaddress.IPv4Network(subnet, strict=False)`, raising `InvalidScanInput` with a descriptive message at each failure point — validation runs before any workspace resolution or scan construction, so invalid input never touches disk or `discover_hosts`. `run_headless_scan` resolves `workspace_root` via a small `_resolve_workspace_root` helper (`load_config().results_dir` if a config file exists, else `agent.paths.default_results_dir()`, matching `scan_progress.py`'s `_start_scan` pattern one level down since headless needs a concrete path, not `None`), pre-creates `workspace_root/results` and returns `outcome="fatal"` on `OSError` before constructing any runner. It then builds a `ScanRunner(subnet, mode, reporter=..., on_complete=<closure>, on_error=<closure>, workspace_root=..., runner=...)` — matching `ScanRunner.__init__`'s actual positional/keyword signature in `tui/scanner.py` — and calls the Task-2 `run_blocking()`. On a captured payload it calls `write_scan_result` (same function `home.py` uses) and classifies `outcome` from `payload.metadata["partial_result"]`; on a captured error instead, `outcome="fatal"` with no JSON write. `StderrReporter.emit` is a one-line `print(event.message, file=sys.stderr)` satisfying the `ScanReporter` protocol structurally (no explicit inheritance needed).

### Decisions Made
- Resolved workspace to a concrete `Path` (never `None`) unlike `ScanProgressScreen._start_scan`, because headless (unlike the TUI, which lets `ScanRunner`/`build_runner` silently fall back to an in-memory `NmapRunner` with no logging) must have a real directory to pre-create `results/` in and to pass to `write_scan_result` — `_resolve_workspace_root` centralizes that one difference.
- Used two small closures (`_on_complete`/`_on_error`) with `nonlocal` captures rather than a small capturing class, since the capture is a single value each and matches the plain-function style already used for callbacks elsewhere in this module's neighborhood (`ScanRunner`'s own callback params are plain `Callable`s, not an object protocol).
- Did not special-case `mode`'s type as the `Literal` `ScanRunner` expects internally; `validate_inputs` already guarantees membership in `config.SCAN_MODES` before `mode` reaches `ScanRunner`, so no `cast`/`assert` was added — the runtime check *is* the type guarantee here.
- No comments or docstrings added, per project preference.

### Verification
- `uv run python -c "import agent.headless as h; print(h.EXIT_CODES, h.INVALID_INPUT_EXIT)"` → `{'completed': 0, 'partial': 10, 'fatal': 20} 2`.
- Confirmed `'textual' not in sys.modules` after `import agent.headless` in a fresh interpreter → `True`.
- Smoke-tested `validate_inputs`: bad mode, no-slash subnet, and malformed CIDR (`/99`) each raise `InvalidScanInput`; a valid `192.168.1.0/24` passes.
- End-to-end smoke: monkeypatched `agent.tui.scanner.check_network_connectivity`/`discover_hosts` (zero hosts, mirroring `test_scan_runner_partial.TestZeroHosts`) and drove `run_headless_scan("quick", "192.168.1.0/24", workspace_root=<tmp>, runner=<fake NmapRunner>)` → `outcome="completed"`, a `<ts>_<subnet-slug>.json` written under `<tmp>/results`, and `ScanPayload.model_validate` on the loaded JSON succeeded.
- `uv run ruff check src/agent/headless.py` → All checks passed.
- `uv run pytest -q` (full suite, no new test file yet) → 468 passed, unchanged from before this task — proves the new module doesn't perturb any existing TUI or config test.

### Code Changed
- Created: hardware-agent/src/agent/headless.py

## test-engineer — Task 3

### Order Given
Write `hardware-agent/tests/unit/test_headless.py` covering the Task 3 Success Criteria / ARCHITECTURE.md § Testing expectations rows for `agent/headless.py`: same-shape (headless JSON vs. a direct `ScanRunner` run), programmatic `HeadlessScanResult`, failure semantics (post-discovery fatal → partial with JSON, pre-discovery fatal → fatal with no JSON), one-pipeline (monkeypatching `stages.run_port_stage` changes the headless result; `headless` imports the shared `ScanRunner`/`write_scan_result`), input validation (unknown mode, no-slash subnet, malformed CIDR each raise `InvalidScanInput` with `discover_hosts` never called and no `results/` dir created), and the ADR-012 exit-code contract (`EXIT_CODES`, `INVALID_INPUT_EXIT`). Mirror `test_scan_runner_partial.py`'s harness (`_FakeRunner(NmapRunner)`, monkeypatched `agent.tui.scanner.check_network_connectivity`/`discover_hosts`, `stages.run_port_stage` for failures). No production-file edits; no comments/docstrings.

### What, How & Why
Created `test_headless.py` with a `_FakeRunner(NmapRunner)` (stub `run_xml` returning `<nmaprun/>`) and a `_patch_discovery` helper wrapping the two monkeypatches every test needs, plus `_one_host()` returning a single `HostInfo`, all copied from `test_scan_runner_partial.py`'s pattern.
- `TestSameShape`: drives `headless.run_headless_scan(..., workspace_root=tmp_path, runner=_FakeRunner())` with zero discovered hosts (deterministic, no thread-pool port/NSE stage variability), asserts exactly one `<ts>_<subnet-slug>.json` exists under `tmp_path/results` matching the documented filename pattern via regex, loads and `ScanPayload.model_validate`s it, asserts it equals `headless_result.payload` (round-trip fidelity), then separately drives `ScanRunner(...)._run()` directly with the same subnet/mode/fake-runner/discovery patch and asserts the two payloads' `subnet`, `scan_mode`, `devices`, `findings`, and `metadata` key-set/`partial_result`/`terminated_by` match — proving identical shape from both front doors.
- `TestProgrammaticResult`: asserts the return value is `HeadlessScanResult(outcome="completed", payload=<ScanPayload>, result_path=<written Path>, error=None)` and that `result_path` is literally the file under `tmp_path/results`.
- `TestFailureSemantics`: `test_post_discovery_fatal_yields_partial` monkeypatches `stages.run_port_stage` to raise `FatalScanError` with one discovered host (mirroring `TestPostDiscoveryFatal`), asserts `outcome="partial"` and the written JSON's `metadata` has `partial_result is True`, `terminated_by == "error"`, `interrupted_stage == "ports"`. `test_pre_discovery_fatal_yields_fatal_no_json` monkeypatches `discover_hosts` itself to raise `FatalScanError` (mirroring `TestFatalBeforeDiscovery`), asserts `outcome="fatal"`, `payload`/`result_path` are `None`, `error` is the `FatalScanError`, and no JSON file exists under `results/`.
- `TestOnePipeline`: a baseline test (one host, no patch) asserts `outcome="completed"`; a second test re-applies the `run_port_stage` fatal patch and asserts `outcome="partial"` for the identical inputs, proving the outcome tracks the shared stage function rather than being hardcoded; a third test asserts `headless.ScanRunner is ScanRunner` and `headless.write_scan_result is write_scan_result` (imported, not reimplemented).
- `TestInputValidation`: three tests (unknown mode, subnet without `/`, malformed octets) each monkeypatch `agent.tui.scanner.discover_hosts` to a call-recording stub, assert `InvalidScanInput` is raised, the stub was never called, and `tmp_path/results` was never created — proving validation happens before any workspace/scan side effect.
- `TestExitCodeContract`: asserts `headless.EXIT_CODES == {"completed": 0, "partial": 10, "fatal": 20}` and `headless.INVALID_INPUT_EXIT == 2`, the ADR-012 drift guard.

### Decisions Made
- Used zero discovered hosts for the same-shape comparison (rather than one host) to keep the port/NSE thread-pool stages out of the comparison entirely — `TestZeroHosts` in `test_scan_runner_partial.py` already establishes that path is deterministic and fully exercises normalization; the one-host case is exercised separately in `TestOnePipeline`/`TestFailureSemantics` where the port-stage behavior itself is under test.
- Compared payload fields selectively (`subnet`, `scan_mode`, `devices`, `findings`, metadata key-set + two terminal-state keys) rather than full equality between the headless and direct-runner payloads, since `scan_id`/`timestamp`/`elapsed_seconds` are run-specific by design (ARCHITECTURE.md: "Only run-specific values... differ") and asserting those equal would be a false expectation, not a stronger test.
- Did not add a separate "pre-discovery unexpected (non-Fatal) error" case — out of the Task 3 Success Criteria table, which only requires the `FatalScanError` pre/post-discovery pair; `test_scan_runner_partial.py`'s own `TestPostDiscoveryUnexpected` already covers that at the `ScanRunner` layer headless reuses verbatim.
- Reused the private `runner._run()` call in `TestSameShape` (rather than `run_blocking()`) to exactly mirror `test_scan_runner_partial._build_runner`'s established pattern, which the ARCHITECTURE doc explicitly names as the mirror target.
- No production code touched; no comments/docstrings in the test file.
- Ran (from `hardware-agent/`): `uv run pytest tests/unit/test_headless.py -q` → 11 passed; `uv run ruff check tests/unit/test_headless.py` → All checks passed; full `uv run pytest -q` → 479 passed (up from 468 pre-task by exactly the 11 new tests), confirming zero edits to any existing test broke anything.

### Code Changed
- Created: hardware-agent/tests/unit/test_headless.py

## code-reviewer — Task 3

### Order Given
Review gate for Task 3 of spec 012 (DMI-51): verify `hardware-agent/src/agent/headless.py` (new module) and `hardware-agent/tests/unit/test_headless.py` (11 tests) against the Task 3 Success Criteria and ARCHITECTURE.md § Design decision 3 / § Data model / § Testing expectations and ADR-012's exit-code contract. Confirm validate-first, workspace via `agent.paths`, results/ pre-create with OSError→fatal-before-scan, `ScanRunner` reuse via `run_blocking()`, `write_scan_result` reuse, partial/completed classification from metadata, error→fatal with no JSON, exact public surface, no textual/tui imports beyond scanner+results, no forked scan logic, no comments/docstrings. Verify no existing file was edited for Task 3. Run full `uv run pytest` and `uv run ruff check`.

### What, How & Why
Read `headless.py` fully and checked § Design decision 3 point by point: `run_headless_scan` calls `validate_inputs` first (line 71) before any workspace resolution or scan — invalid input never touches disk or `discover_hosts`; workspace resolves via `agent.paths.load_config`/`default_results_dir` (not `tui`); `results/` pre-created with `OSError → outcome="fatal"` returned before constructing the runner (lines 74-79); `ScanRunner(...)` constructed with the exact signature in `tui/scanner.py` and driven by `run_blocking()`; `write_scan_result(payload, str(workspace_root))` reused; outcome classified from `metadata["partial_result"]`; captured error → `outcome="fatal"` with no JSON. Public surface matches § Data model exactly: `HeadlessScanResult` (outcome/payload/result_path/error), `InvalidScanInput(ValueError)`, `EXIT_CODES = {"completed":0,"partial":10,"fatal":20}`, `INVALID_INPUT_EXIT = 2`, `StderrReporter.emit` printing `event.message` to stderr, `validate_inputs`. Imports are clean — no `textual`, only `agent.tui.scanner` (ScanRunner) and `agent.tui.results` (write_scan_result) from the tui package; no forked scan logic; no comments/docstrings. `test_headless.py` mirrors `test_scan_runner_partial.py`'s harness (`_FakeRunner(NmapRunner)` stub XML, monkeypatched `check_network_connectivity`/`discover_hosts`, `stages.run_port_stage` for failures) and covers every ARCHITECTURE Testing-expectations row for Task 3: same-shape (vs. a direct `ScanRunner._run()`), programmatic result, post-discovery-fatal→partial (partial_result True / terminated_by "error" / interrupted_stage "ports"), pre-discovery-fatal→fatal-no-JSON, one-pipeline (patching `run_port_stage` flips the outcome; `headless.ScanRunner is ScanRunner`, `headless.write_scan_result is write_scan_result`), input validation (unknown mode / no-slash / malformed each raise with `discover_hosts` never called and no `results/` dir), and the ADR-012 exit-code drift guard.
`git status` confirms Task 3 added exactly two new files (`headless.py`, `test_headless.py`); no existing file was edited for this task (the other diffs on the branch are Tasks 1/2 and the prerequisite `tui/config.py → paths.py` refactor, out of scope). Ran (from `hardware-agent/`): full `uv run pytest -q` → 479 passed; `uv run ruff check src/agent/headless.py tests/unit/test_headless.py` → All checks passed. Grepped for `# ponytail:` markers across `hardware-agent` — none present, nothing to strip.

### Decisions Made
APPROVE. Every Task 3 Success Criterion is met and verified against ARCHITECTURE.md § Design decision 3 / § Data model / § Testing expectations and ADR-012: validate-first fail-fast, `agent.paths` workspace resolution, OSError-before-scan fatal, single shared pipeline via `run_blocking()` with no fork, correct public surface and exit-code constants, clean imports, no comments/docstrings. The CLAUDE.md integration rule does not apply — Task 3 adds a new `ScanRunner` *caller*, not a new constructor parameter, so there is nothing to thread through `ScanRunner`/`ScanProgressScreen`. Full suite (479) and ruff both green; no existing files edited for this task.

### Code Reviewed
- hardware-agent/src/agent/headless.py
- hardware-agent/tests/unit/test_headless.py

## agent-developer — Task 4

### Order Given
Task 4 from `specs/012-headless-agent-entrypoint/TASKS.md`: add a `dmitri agent <mode> <subnet>` branch to `hardware-agent/src/agent/cli.py`'s hand-rolled dispatch (no argparse); reuse `_check_nmap()` (missing → existing guidance, exit 20); call `run_headless_scan(mode, subnet, reporter=StderrReporter())`; on `InvalidScanInput` print message to stderr, exit 2; on success print one JSON line (`outcome`/`result_path`/`scan_id`, both null on fatal) to stdout and exit per `EXIT_CODES`; update the usage string; align existing exits (`_run_tui` nmap-missing `1→20`, top-level unknown-command `1→2`); update `test_cli_nmap_missing`/`test_cli_unknown_command` in `tests/integration/test_tui_flows.py`; do not write `test_cli_agent.py` (test-engineer follows). Also update spec-000 contract docs (`contracts/cli.md`, `checklists/requirements.md`) and add superseded-by-spec-012 notes to `BUG-004` and `plans/01-cli-entry-and-skeleton.md`.

### What, How & Why
Added an `agent` elif branch in `main()` that dispatches to a new `_run_agent(args[1:])`, and updated the top-level unknown-command path to exit `2` with a usage string mentioning both subcommands. `_run_agent` enforces exactly two positional args (usage + exit 2 otherwise), reuses the existing `_check_nmap()` guard (now exiting `20` on both the `start` and `agent` paths), then lazily imports `agent.headless` (matching the file's existing lazy-import-of-`DmitriApp` style) and calls `headless.run_headless_scan(mode, subnet, reporter=headless.StderrReporter())`. `InvalidScanInput` is caught and printed to stderr with exit `2`. On a returned `HeadlessScanResult`, `scan_id`/`result_path` are read off `result.payload`/`result.result_path` (both `None` → JSON `null` on a fatal outcome, since no payload was captured), serialized as one `json.dumps(...)` line to stdout, and the process exits via `headless.EXIT_CODES[result.outcome]`.
Found, on reading them, that `specs/000-agent-tui/contracts/cli.md`, `checklists/requirements.md`, `bugs/004-nmap-missing-not-fatal.md`, and `plans/01-cli-entry-and-skeleton.md` already carried the exact superseded-by-spec-012 exit-code notes and updated code table this task calls for (`specs/000-agent-tui/` is gitignored per `.gitignore` line 218 `specs/00[0-9]-*/`, so no git history exists to show when/how they were written — they were already correct on disk before this task started). Verified their content line-by-line against ARCHITECTURE.md §4 and ADR-012's table and made no further edits since they already matched.

### Decisions Made
- Kept `_run_agent` as a small dedicated function (mirroring `_run_tui`) rather than inlining the branch in `main()`, matching the file's one-function-per-subcommand shape.
- Read `scan_id` off `result.payload.scan_id` (a `UUID`) and `str()`-cast it for JSON serialization, rather than adding a `scan_id` field to `HeadlessScanResult` itself — Task 3's dataclass is out of this task's scope and already exposes the payload needed.
- Left `main()`'s and `_check_nmap()`'s existing docstrings untouched (surgical-edit rule; no adjacent cleanup) and added no docstrings/comments to the new `_run_agent` function.
- Did not re-edit the four spec-000 docs since they already matched the required superseded-by-spec-012 wording; verified rather than assumed.
- Did not write `tests/unit/test_cli_agent.py` (test-engineer's task).

### Verification
- `uv run pytest tests/integration/test_tui_flows.py -q` → 8 passed.
- `uv run ruff check src/agent/cli.py` → All checks passed.
- Full `uv run pytest -q` → 479 passed (unchanged from Task 3 baseline, since only two existing assertions were value-flipped, no test added).
- Smoke: `sys.argv=['dmitri','agent']` → prints `Usage: dmitri agent <mode> <subnet>` to stderr, exits `2`.
- Smoke: `sys.argv=['dmitri','agent','bogus','10.0.0.0/24']` (nmap present) → prints `Unknown scan mode 'bogus'; must be one of (...)` to stderr, exits `2`.

### Code Changed
- Modified: hardware-agent/src/agent/cli.py
- Modified: hardware-agent/tests/integration/test_tui_flows.py

## test-engineer — Task 4

### Order Given
Create `hardware-agent/tests/unit/test_cli_agent.py` driving `cli.main()` with monkeypatched `sys.argv` and a stubbed `run_headless_scan` (and `_check_nmap` where relevant), mirroring the existing `test_cli_*` harness in `tests/integration/test_tui_flows.py`: outcome "completed"/"partial"/"fatal" → SystemExit 0/10/20; bad arity (`dmitri agent`, `dmitri agent quick`, `dmitri agent quick x y`) → exit 2 with usage on stderr; stubbed `run_headless_scan` raising `InvalidScanInput` → exit 2, message on stderr; `_check_nmap` stubbed False → exit 20 and `run_headless_scan` never called; stdout JSON line parsed and asserted for keys `outcome`/`result_path`/`scan_id` (populated on completed/partial, both null on fatal); exit codes asserted equal to `headless.EXIT_CODES` values. Do not edit production code or the two already-updated `test_cli_*` tests in `test_tui_flows.py`.

### What, How, and Why
Wrote `test_cli_agent.py` as flat `test_*` functions (matching the flat-function style of the existing `test_cli_unknown_command`/`test_cli_nmap_missing` in `test_tui_flows.py`, rather than the class-grouped style used in `test_headless.py`/`test_scan_mode_scripts.py`, since this file's nearest sibling is the CLI harness, not the headless-module harness). Each test patches `sys.argv` via `patch.object`, patches `agent.cli._check_nmap` to a fixed boolean so the test is independent of whether nmap is actually installed on the runner, and patches `agent.headless.run_headless_scan` (by its `agent.headless` attribute path, which `cli.py`'s lazy `from agent import headless` + `headless.run_headless_scan(...)` call resolves correctly at call time) to return/raise a stub. A minimal `_StubPayload` class carrying only `.scan_id` stands in for `ScanPayload` since `cli.py` only ever reads `result.payload.scan_id`. `_stub_result` builds real `headless.HeadlessScanResult` instances so the tests exercise the actual dataclass shape rather than a hand-rolled duck-type. `capsys` captures stdout (parsed as JSON) and stderr (substring-checked for usage/error text). Bad-arity tests use `@pytest.mark.parametrize` over the three under/over-arity argv shapes named in the task. The nmap-missing test asserts `run_headless_scan` was never invoked by making the stub raise `AssertionError` if called and asserting no call was recorded, catching a coder regression where the nmap gate is checked after the headless call rather than before.

### Decisions Made
- Mocking boundary: `agent.cli._check_nmap` and `agent.headless.run_headless_scan` are the only patched seams — this exercises `cli.main()`'s real dispatch/exit-code/JSON-serialization logic end-to-end while stubbing out the two things Task 4 doesn't own (nmap detection, the headless pipeline itself).
- Used real `headless.HeadlessScanResult` instances (not a hand-rolled stand-in) as the stub return value so the test stays honest to the actual dataclass contract; `_StubPayload` is deliberately minimal (only `.scan_id`) since that's the only attribute `cli.py` reads off `payload`.
- Compared `result_path` in the completed/partial tests against `str(Path("tmp") / "results" / "scan.json")` rather than a hardcoded POSIX string, after an initial run failed on Windows (`\` vs `/` path separators) — this is a test-only fix, no production code touched.
- Did not add a test for `_check_nmap` behavior itself (real PATH lookup) — out of scope, already covered by existing `test_cli_nmap_missing`.
- Did not touch `test_cli_nmap_missing`/`test_cli_unknown_command` in `test_tui_flows.py` — confirmed already updated to 20/2 by the coder.
- No bugs found in `cli.py`: arity check precedes the nmap check precedes the headless call, in the order the architecture and task description require.

### Code Changed
- Created: hardware-agent/tests/unit/test_cli_agent.py

## code-reviewer — Task 4

### Order Given

Review Task 4 (CLI `dmitri agent` branch + exit-code alignment) of spec 012 as the
approval gate: verify the new `agent` branch (`_run_agent`), aligned exits (`_run_tui`
nmap 1→20, unknown-command 1→2), updated usage string, `test_cli_agent.py`, the two
updated `test_tui_flows.py` expectations, and the spec-000 doc alignment (cli.md,
requirements.md, BUG-004, plans/01). Run `uv run pytest` + `uv run ruff check`. Emit
`[APPROVE]`/`[REJECT]` on the first line.

### What, How & Why

Read TASKS.md/ARCHITECTURE.md §4/ADR-012/TRUTH.md for the checklist. Diffed cli.py and
test_tui_flows.py, read headless.py and test_cli_agent.py, and read all four spec-000
docs. cli.py logic verified correct: arity→2, `_check_nmap` reuse→20 with existing
guidance text, `InvalidScanInput`→stderr+2, one JSON line `{outcome,result_path,scan_id}`
(null on fatal) exiting via `headless.EXIT_CODES`, usage string covers `agent`,
hand-rolled dispatch preserved, no comments/docstrings. Docs all carry the aligned codes
and superseded notes. No TUI screen edits. `uv run pytest` → 487 passed. But
`uv run ruff check` on the changed files FAILS: `I001` in `tests/integration/
test_tui_flows.py:3` — the relocated import `from agent.paths import DmitriConfig,
save_config` (line 19) sits after `from agent.tui.app import DmitriApp` (line 18) and is
out of alphabetical sort order. `uv run ruff check` passing is an explicit Task 4 success
criterion, so the gate cannot pass.

### Decisions Made

REJECT. Every functional criterion is met and the full pytest suite is green, but the
mandatory `uv run ruff check` gate fails on a file in this task's diff. Per the behavioral
guideline, work with a failing required command is rejected, not approved. Fix is
mechanical (reorder the import / `ruff check --fix`), then re-run both gates.

### Code Reviewed

- hardware-agent/src/agent/cli.py
- hardware-agent/src/agent/headless.py
- hardware-agent/tests/unit/test_cli_agent.py
- hardware-agent/tests/integration/test_tui_flows.py
- specs/000-agent-tui/contracts/cli.md
- specs/000-agent-tui/checklists/requirements.md
- specs/000-agent-tui/bugs/004-nmap-missing-not-fatal.md
- specs/000-agent-tui/plans/01-cli-entry-and-skeleton.md

## agent-developer — Task 4 (fix, rejection 1)

### Order Given
Fix the single review rejection on Task 4 of spec 012: `hardware-agent/tests/integration/test_tui_flows.py:19` has `from agent.paths import DmitriConfig, save_config` placed after `from agent.tui.app import DmitriApp`, an I001 unsorted-import-block ruff failure. Re-sort the import block only; touch no other file or line.

### What, How & Why
Swapped the two import lines so `from agent.paths import DmitriConfig, save_config` sits above `from agent.tui.app import DmitriApp`, restoring alphabetical order (`agent.paths` sorts before `agent.tui.*`). This is the exact mechanical fix the reviewer named.

### Decisions Made
Made the two-line swap by hand rather than running `ruff check --fix`, to guarantee the diff touches only these two lines and nothing else in the file.

### Code Changed
- Modified: hardware-agent/tests/integration/test_tui_flows.py

## code-reviewer — Task 4 (re-review)

### Order Given
Re-review Task 4 of spec 012 (DMI-51) after the fix for the sole prior rejection: ruff I001 un-sorted import block at hardware-agent/tests/integration/test_tui_flows.py:19. Confirm the import block is now sorted with nothing else changed beyond the two already-approved exit-code expectations, run the full pytest suite and full ruff check (both must pass), then APPROVE or REJECT.

### What, How & Why
Read TASKS.md Task 4 success criteria. Diffed hardware-agent/tests/integration/test_tui_flows.py: the import block is now sorted (`from agent.paths import DmitriConfig, save_config` precedes `from agent.tui.app import DmitriApp`, restoring alphabetical order); the only other changes are the two prior-approved exit-code expectation updates (test_cli_unknown_command 1→2, test_cli_nmap_missing 1→20) plus their docstrings. No logic or other lines touched. Ran from hardware-agent/: `uv run ruff check` → All checks passed; `uv run pytest -q` → 487 passed in ~31s. Grepped for `# ponytail:` markers across the touched files and hardware-agent — none present, nothing to strip.

### Decisions Made
APPROVE. The single rejection reason is resolved (ruff clean), the full suite is green, and the diff contains no scope creep beyond the previously verified changes. All other Task 4 criteria were verified met in the prior review and are unchanged.

### Code Reviewed
- hardware-agent/tests/integration/test_tui_flows.py

## agent-developer — Task 5

### Order Given
Implement Task 5 of spec 012 (DMI-69 follow-up): contain `OSError` raised by `Path.unlink` inside `prune_results` (`hardware-agent/src/agent/scanner/workspace.py`) so a pruning failure can no longer propagate out of `write_scan_result` and turn a fully successful write into a reported total failure. Do not touch `write_scan_result`'s own `mkdir`/`write_text` — those must keep raising, since after this task an `OSError` escaping `write_scan_result` must mean exactly "no result file exists" (Task 6 depends on that invariant). Scope fence: `prune_results` only, ~2-line change, no retry, no broad exception handling, no bare `except`.

### What, How & Why
Wrapped the existing `for f in files[:excess]: f.unlink()` loop in `prune_results` with `try: ... except OSError: pass`. This is the narrowest possible containment: it catches only `OSError` (never a bare `except`), it wraps only the unlink loop (not the `mkdir`/`write_text` calls a few lines earlier in `write_scan_result`, which are untouched and still propagate), and it matches the "contain around the unlink loop" instruction literally rather than adding per-file try/except (unnecessary — pruning is opportunistic housekeeping, not a per-file guarantee; if `unlink` starts failing partway through, e.g. a permissions change mid-loop, giving up on the rest of the prune pass is fine since the next successful write will retry pruning anyway).

Checked the precedent (`prune_logs`, same file) referenced in TASKS.md: it does not itself contain a try/except around `shutil.rmtree` at the point I read it, so I did not try to mirror a specific try/except shape from it — I matched the spirit (never let housekeeping deletion raise past the caller) using the plain `except OSError: pass` idiom already used elsewhere in this file (`_read_run_meta`'s `except (OSError, ValueError, AttributeError)`).

Added one minimal test, `test_unlink_oserror_does_not_propagate` in `TestPruneResults` (`hardware-agent/tests/unit/test_workspace.py`), that monkeypatches `Path.unlink` to raise `OSError` and asserts `prune_results` returns normally. Kept it to a single assertion-free-call test (the "does not raise" behavior is the whole point) since the test-engineer builds out the full suite next.

### Decisions Made
- Single `try/except OSError: pass` around the whole loop rather than per-file try/except inside the loop body — simpler, and the task description says "contain around the unlink loop," singular, not "make each deletion independently resilient." Nothing in the success criteria requires partial-progress guarantees (e.g., "delete as many as possible even if one fails"), so the simpler wrap is the correct stopping point per ponytail scope fence (~2-line change).
- Left `write_scan_result`'s `mkdir`/`write_text` and the `prune_results(dir_path)` call site completely untouched, per the explicit invariant instruction — verified by running the full test file and the existing `TestPruneResults` + `test_prunes_to_10_after_writing` tests unedited, all green.
- Did not touch `prune_logs`, `ARCHITECTURE.md`, or any Task 6/7 file, per the fence in the task prompt.

### Code Changed
- Modified: hardware-agent/src/agent/scanner/workspace.py
- Modified: hardware-agent/tests/unit/test_workspace.py

## test-engineer — Task 5

### Order Given
Add tests for Task 5 of spec 012 (DMI-69 follow-up) covering the success criteria not yet exercised by the agent-developer's single test (`test_unlink_oserror_does_not_propagate`): (1) when pruning fails, `write_scan_result` still returns the written path and the new file exists on disk with valid `ScanPayload` JSON; (2) `OSError` from `write_scan_result`'s own `mkdir` still propagates; (3) `OSError` from its own `write_text` still propagates. No `chmod`-based tests. Do not duplicate the coder's existing test. Do not touch Task 6/7 scope.

### What, How & Why
Added three module-level tests in `hardware-agent/tests/unit/test_workspace.py`, placed directly after `test_prunes_to_10_after_writing` (the last existing `write_scan_result` test), matching that section's flat-function style rather than the `TestPruneResults` class style:

- `test_returns_path_and_writes_file_when_pruning_fails` — seeds 12 old result files, monkeypatches `Path.unlink` to raise `OSError` (same technique as the coder's `TestPruneResults` test), calls `write_scan_result`, and asserts the returned path exists and its contents parse as valid JSON with the expected `subnet`/`scan_mode` fields. This is the criterion that actually matters per the orchestrator's brief: proving the *caller-visible* contract (`write_scan_result`'s return value and on-disk file) survives a pruning failure, not just that `prune_results` itself doesn't raise (already covered by the coder's test).
- `test_mkdir_oserror_propagates` — monkeypatches `Path.mkdir` to raise `OSError` and asserts `write_scan_result` lets it escape via `pytest.raises(OSError)`. Regression guard for the Task 6 invariant that an `OSError` escaping `write_scan_result` means no file was written.
- `test_write_text_oserror_propagates` — same pattern, monkeypatching `Path.write_text`.

Chose global `monkeypatch.setattr(Path, ...)` (auto-reverted per test by the fixture) over `chmod`, per the explicit constraint that a chmod-based test silently passes when run as root in CI, and because it mirrors the exact technique already used by the existing `test_unlink_oserror_does_not_propagate`.

### Decisions Made
- Mocking boundary: monkeypatch the stdlib `Path` methods (`unlink`, `mkdir`, `write_text`) directly rather than mocking `agent.scanner.workspace` internals — this is the same boundary the coder's test already established, so no new pattern was introduced.
- Did not add a test asserting the *count* of remaining files after a failed prune (e.g., that all 13 files are still present) — out of scope per the orchestrator's stated criteria, which only ask for the returned-path/on-disk/valid-JSON behavior of `write_scan_result`, and `TestPruneResults` already covers prune-result-set assertions.
- Did not edit or duplicate the coder's `test_unlink_oserror_does_not_propagate`; left `TestPruneResults` untouched.
- Ran `uv run ruff check --fix` after adding the `import pytest` line, which the linter resolved into a single unsorted-import-block fix (merged `import pytest` and the `agent.*` imports into one correctly ordered block, dropping the blank line between them) — noted as the unavoidable testability/lint touch, no production code changed.
- Verified all 6 pre-existing `TestPruneResults` tests and `test_prunes_to_10_after_writing` pass with zero edits; full file run is 73 passed.

### Code Changed
- Modified: hardware-agent/tests/unit/test_workspace.py

## code-reviewer — Task 5

### Order Given
Review Task 5 of spec 012 (DMI-69 follow-up): "Contain OSError in prune_results" — verify the
`unlink`-loop containment in `hardware-agent/src/agent/scanner/workspace.py` and the four new tests
in `hardware-agent/tests/unit/test_workspace.py`, confirm the invariant that `mkdir`/`write_text`
still raise while only pruning is contained, run `uv run pytest` / `uv run ruff check` (and `black
--check` if available), confirm the six pre-existing `TestPruneResults` tests plus
`test_prunes_to_10_after_writing` pass unedited, confirm the ruff-reordered import block is
whitespace-only, confirm no scope leak into Task 6/7 files, and render explicit judgment on whether
containing the *whole* unlink loop (vs. per-file) is acceptable simplicity or a real defect. The
known-stale `tui/results.py` references in ARCHITECTURE.md are explicitly out of scope (Task 7's
job) and not a finding here.

### What, How & Why
Read `TASKS.md` (Task 5 section + the six DMI-69 decisions), diffed
`hardware-agent/src/agent/scanner/workspace.py` and `hardware-agent/tests/unit/test_workspace.py`
against `HEAD`, and read the full `write_scan_result`/`prune_results`/`prune_logs` neighborhood to
verify the fatal-invariant boundary.

Confirmed:
- `prune_results` wraps only its `unlink` loop in `try/except OSError: pass`; `write_scan_result`'s
  `mkdir` (line 167) and `write_text` (line 175) are untouched and sit outside any try/except, so an
  `OSError` there still propagates — the Task 6 invariant holds.
- The four new tests (`test_unlink_oserror_does_not_propagate`,
  `test_returns_path_and_writes_file_when_pruning_fails`, `test_mkdir_oserror_propagates`,
  `test_write_text_oserror_propagates`) monkeypatch `Path.unlink`/`Path.mkdir`/`Path.write_text`
  directly — no `chmod`, matching the CI-as-root constraint.
- `git diff` confirms zero edits to any pre-existing test in `test_workspace.py`; only additions.
  The `import pytest` line ruff reordered is a pure import-block addition, no logic touched.
- `git diff --stat` shows only `workspace.py`, `test_workspace.py`, `POOP.md`, `TASKS.md` changed —
  no leakage into `headless.py`, `cli.py`, ADRs, or other docs (Task 6/7 scope untouched).
- Only `OSError` is caught, no bare `except`, no `Exception`, no retry, no alternate storage —
  matches scope fence.

Commands run (inside `hardware-agent/`):
- `uv run pytest -q` → 492 passed.
- `uv run ruff check .` → All checks passed.
- `uv run black --check .` and `uv run black --check hardware-agent` (from repo root) → both fail
  with `error: Failed to spawn: black — No such file or directory`; `black` is not installed in
  this environment. Stating explicitly per instructions rather than skipping silently — this gate
  could not be run.

Design judgment on whole-loop vs. per-file containment (explicitly requested): **this is a real
defect, not acceptable simplicity.** Reasoning:
- The two forms are the same line count (5 lines either way — moving the `try/except` one
  indentation level inward costs nothing). There is no simplicity trade-off being made here, so the
  "simpler wrap" justification in the coder's POOP.md entry does not hold up — nothing is actually
  simpler.
- `files` is sorted oldest-first by name (`key=lambda f: f.name`) and pruning always attempts
  `files[:excess]` starting from the oldest. If the oldest stuck file's `unlink` fails once (locked
  file, permission/ACL anomaly, one bad inode) and remains stuck, whole-loop containment means
  *every future call* to `prune_results` aborts at that same file on its first iteration, and no
  file older-or-equal is ever pruned again — `results/` grows unbounded for the life of the
  appliance. Per-file containment prunes everything after the stuck file on every call, bounding
  growth to the one stuck entry.
- This is precisely the "long-running Pi appliance" scenario the task's own framing (and DMI-69
  generally) is trying to make robust against — a silent, permanent regression rather than a
  transient one.
- The task description's "opportunistic housekeeping, not part of the persistence contract" reads
  as "best effort, do what you can," not "give up entirely on first failure." No success criterion
  or DMI-69 decision endorses whole-loop specifically; the literal criterion ("does not propagate")
  is satisfied by both forms, so this isn't a criterion-text violation but a genuine behavioral gap
  the criteria didn't anticipate spelling out.
- No test in the suite exercises "one stuck old file, rest still prune" — the gap in behavior has a
  corresponding gap in test coverage, which is itself evidence the scenario wasn't validated.

### Decisions Made
[REJECT]. Required fix: nest the `try/except OSError: pass` inside the `for` loop body in
`prune_results` (`hardware-agent/src/agent/scanner/workspace.py:142-146`) so a failing `unlink` on
one file does not abort pruning of the remaining files in the same pass:
```python
for f in files[:excess]:
    try:
        f.unlink()
    except OSError:
        pass
```
Everything else in the diff is correct: the `mkdir`/`write_text` invariant holds, scope is clean,
tests are additive and unedited where required, `chmod` is correctly avoided, `pytest` (492 passed)
and `ruff check` (clean) both pass. `black` could not be run — not installed in this environment,
stated explicitly rather than skipped. Because this is a `[REJECT]`, no `# ponytail:` marker strip
was performed (none were present in the touched files regardless) and no re-run of `ruff check`
post-strip was needed.

### Code Reviewed
- hardware-agent/src/agent/scanner/workspace.py
- hardware-agent/tests/unit/test_workspace.py

## Task 5 — Developer (Rejection 1)

### Order Given
Fix Task 5 of spec 012 (DMI-69 follow-up) after code review `[REJECT]`. The single finding: the
try/except in `prune_results` wrapped the whole unlink loop, so the first `OSError` aborted pruning
of every remaining file for that call — and since `files` is sorted oldest-first, a permanently
stuck old file would be first in line on every subsequent call, growing `results/` unbounded.
Required fix: nest the try/except inside the loop body, per file. Also add the missing test the
reviewer flagged: "one old file fails to unlink, the rest still get pruned." Do not touch anything
else — `mkdir`/`write_text` in `write_scan_result` stay outside any try/except, and everything else
in Task 5 was already approved.

### What, How, and Why
Moved the `try/except OSError: pass` from wrapping the entire `for f in files[:excess]: f.unlink()`
loop to wrapping only the single `f.unlink()` call inside the loop body, in
`hardware-agent/src/agent/scanner/workspace.py`. This is the exact fix specified in the rejection —
same line count, same imports, no new code paths. Reused the existing `TestPruneResults` /
`_make_result_files` pattern to add `test_one_stuck_file_does_not_block_rest`, monkeypatching
`Path.unlink` to raise only for one specific file (delegating to the real `unlink` for the rest via
a captured `original_unlink` reference) and asserting the stuck file survives while its siblings are
pruned.

### Decisions Made
- Kept the monkeypatch style already used by `test_unlink_oserror_does_not_propagate` (no `chmod`)
  and made it selective by comparing `self == stuck` inside the patched method, delegating to the
  original `Path.unlink` for every other file so the test exercises real filesystem deletion for the
  non-stuck files rather than mocking all of them away.
- Did not touch `write_scan_result`'s `mkdir`/`write_text`, the six pre-existing `TestPruneResults`
  tests, or any other file — the rejection named a single line-level fix and one missing test; no
  other scope was reopened.

### Code Changed
- hardware-agent/src/agent/scanner/workspace.py (modified)
- hardware-agent/tests/unit/test_workspace.py (modified)

## Task 5 — Code Reviewer (Rejection 1)

### Order Given
Re-review Task 5 of spec 012 (DMI-69 follow-up) after the prior `[REJECT]` was addressed by a
fresh developer. Scope: verify both prior findings are fixed (per-file try/except instead of
whole-loop; the missing "one stuck file, rest still pruned" test) and confirm nothing regressed —
in particular that the invariant Task 6 depends on still holds: `write_scan_result`'s `mkdir` and
`write_text` remain outside any try/except and still raise `OSError`, so an `OSError` escaping
`write_scan_result` means no result file exists. Previously-approved points (mkdir/write_text
invariant, existing tests unedited, monkeypatch-not-chmod, no scope leak, OSError-only) were not
to be re-litigated, only re-verified.

### What, How, and Why
Read `hardware-agent/src/agent/scanner/workspace.py` in full. Confirmed `prune_results` now nests
the `try/except OSError: pass` inside the `for f in files[:excess]:` loop body, around the single
`f.unlink()` call — a 3-line diff from the original single-line `f.unlink()`, nothing else in the
function changed. Confirmed `write_scan_result`'s `dir_path.mkdir(parents=True, exist_ok=True)`
and `file_path.write_text(...)` remain unguarded (lines 167 and 175), with `prune_results(dir_path)`
called afterward on line 176 — since `prune_results` itself no longer raises for any per-file
`OSError`, the invariant holds: an `OSError` escaping `write_scan_result` can only come from
`mkdir`/`write_text`, meaning no result file was written.

Read `hardware-agent/tests/unit/test_workspace.py` in full. Confirmed the six pre-existing
`TestPruneResults` tests (`test_no_op_under_limit`, `test_no_op_at_exactly_limit`,
`test_prunes_oldest_when_over_limit`, `test_prunes_to_exact_count`, `test_no_op_on_empty_dir`,
`test_ignores_non_json_files`) are byte-for-byte unedited, plus `test_unlink_oserror_does_not_propagate`
unedited. Confirmed the new `test_one_stuck_file_does_not_block_rest` monkeypatches `Path.unlink`
to raise only for one designated file (`stuck = files[0]`) while delegating to the captured
`original_unlink` for all others, then asserts the stuck file survives (`stuck.exists()`), its
next-oldest sibling is pruned (`not files[1].exists()`), and everything newer survives
(`files[2:]` all exist) — this is exactly the "one file stuck, rest still pruned" case the prior
rejection demanded, and it would have failed under the old whole-loop try/except (which would have
left `files[1]` un-pruned too). Also re-confirmed `test_prunes_to_10_after_writing` and
`test_returns_path_and_writes_file_when_pruning_fails` in the `write_scan_result` test block are
unedited and still pass.

Ran `git status`/`git diff --stat`: only `hardware-agent/src/agent/scanner/workspace.py` and
`hardware-agent/tests/unit/test_workspace.py` changed under `hardware-agent/` (plus TASKS.md/POOP.md
process files) — matches Task 5's Target Files exactly, no scope leak.

Ran `uv run pytest` inside `hardware-agent/`: 493 passed, full suite, no regressions anywhere
(includes `test_scan_runner_*`, `test_scan_progress_screen.py`, etc. — unaffected by this change).
Ran `uv run pytest tests/unit/test_workspace.py -v`: all 74 tests pass, including the new
`test_one_stuck_file_does_not_block_rest`.
Ran `uv run ruff check src/agent/scanner/workspace.py tests/unit/test_workspace.py`: all checks
passed.
`black` was confirmed unavailable in this environment last cycle (`error: Failed to spawn: black`
— re-confirmed, not retried per instruction) — noted, not run.

Grepped both touched files for `# ponytail:` markers — none present, so no stripping was needed.

The fix itself is the minimal possible diff for the requirement: moving `try/except OSError: pass`
from around the loop to around the single `f.unlink()` call inside it. No new abstraction, no
helper function, no configurability added — a `for` loop with a per-iteration guard is the
smallest correct shape for "don't let one bad file block the rest." Nothing to flag under
ponytail-ultra.

### Decisions Made
`[APPROVE]`. Both prior findings are fixed: containment is now per-file (a stuck old file no longer
blocks pruning of newer excess files, so `results/` cannot grow unbounded from one wedged file),
and the missing test now exists and correctly distinguishes the old (whole-loop) behavior from the
new (per-file) behavior. The Task 6 invariant (`mkdir`/`write_text` outside any try/except, still
raise) is confirmed intact and covered by `test_mkdir_oserror_propagates` /
`test_write_text_oserror_propagates`, both unedited and passing. All previously-approved points
(monkeypatch-not-chmod style, OSError-only catch, no scope leak, existing tests unedited) still
hold on re-verification. Full test suite green, ruff clean on the changed files, diff is minimal.

### Code Reviewed
- hardware-agent/src/agent/scanner/workspace.py
- hardware-agent/tests/unit/test_workspace.py

## Task 6: Fatal outcome when the result write fails + stderr visibility

### Order Given
Implement Task 6 of spec 012 (DMI-69 follow-up): wrap the unguarded
`write_scan_result(captured_payload, str(workspace_root))` call in `headless.py` in a narrow
`try/except OSError`, returning a `fatal` `HeadlessScanResult` with `payload=captured_payload`
(not `None`, per decision 3), `result_path=None`, and an `OSError` whose message states the scan
completed and the result could not be written. In `cli.py`'s `_run_agent`, print `result.error` to
stderr when not `None`, before `raise SystemExit(...)`, without altering the frozen stdout JSON
shape (`outcome`, `result_path`, `scan_id` only). Task 5 (contain `OSError` in `prune_results`) was
already COMPLETED and is the invariant this task depends on. Task 7 (doc/ADR alignment) is
explicitly out of scope for this agent.

### What, How, and Why
`headless.py`: wrapped only the `write_scan_result(...)` call itself in `try/except OSError`,
mirroring the shape of the existing pre-scan `mkdir` fatal a few lines above. On catch, returns
`HeadlessScanResult(outcome="fatal", payload=captured_payload, result_path=None, error=OSError(...))`
with a two-line f-string (split for the 88-col ruff limit) stating the scan completed and naming
`workspace_root` and the original `exc` text. Left the `partial`/`completed` branch and everything
above the write call untouched.

`cli.py`: added a two-line `if result.error is not None: print(str(result.error), file=sys.stderr)`
immediately after the stdout JSON `print(...)` and before `raise SystemExit(...)`. `scan_id` needed
no code change — it was already derived from `result.payload.scan_id`, so once `payload` carries
the captured payload on this fatal path, `scan_id` is non-null automatically, satisfying the
"scan_id non-null on this fatal path" criterion for free.

Why this shape: matches the task's prescribed code verbatim (mirrors the existing early-return
fatal, `OSError` only, no new exception class, no retry/alternate storage). The CLAUDE.md
integration rule (thread new orchestrator params through `ScanRunner`/`ScanProgressScreen`) does
not apply here — no new parameter was added to any orchestrator/runner, only a narrower exception
boundary and an existing-field print, so no threading through the TUI runner or scan-progress
screen was needed.

### Decisions Made
- Caught `OSError` only, scoped to the single `write_scan_result` call — not the whole
  `if captured_payload is not None:` block — so the `partial`/`completed` outcome logic below it is
  unreachable on failure but nothing else changes shape.
- Reused the field ordering/shape of the existing pre-scan fatal return literally (keyword args in
  the same order) for readability/consistency, per the task's explicit "mirror the shape" instruction.
- Left `hardware-agent/src/agent/tui/screens/home.py`'s own direct `write_scan_result` call
  unguarded — Task 6's Target Files list only `headless.py`/`cli.py`/their tests; the TUI path is a
  separate call site not mentioned in TASKS.md Task 6 and out of scope for this task.
- Did not touch the existing fatal test asserting `payload is None` (pre-discovery `FatalScanError`
  path) — left for the test-engineer, per explicit instruction not to edit it.
- Split the `OSError(...)` f-string across two lines to satisfy ruff's 88-column limit (E501) rather
  than shortening the message text, to keep the full required wording ("scan completed", workspace
  root, original exc) intact.

### Code Changed
- hardware-agent/src/agent/headless.py (modified)
- hardware-agent/src/agent/cli.py (modified)

## test-engineer — Task 6

### Order Given
Add tests covering Task 6's success criteria: `write_scan_result` raising `OSError` after a
completed/partial scan yields `outcome="fatal"`, `result_path is None`, `payload is` the captured
payload (not `None`), and an `OSError` message stating the scan completed and the result could not
be written; the exception must not escape `run_headless_scan`; writable-workspace behavior stays
unchanged; and on the CLI side, exit `20` with the error printed to stderr while stdout still
carries exactly one JSON line with keys `outcome`/`result_path`/`scan_id` and `scan_id` non-null.
Monkeypatch `agent.headless.write_scan_result` only, no `chmod`, don't touch the existing
`payload is None` fatal test or `test_headless_imports_shared_runner_and_writer`.

### What, How, and Why
`test_headless.py`: added `TestResultWriteFailure` with two cases. The first patches discovery to
zero hosts (mirrors `TestProgrammaticResult`'s completed path) and monkeypatches
`headless.write_scan_result` with a `boom` closure that appends the payload it received to a
`captured` list before raising `OSError("disk full")`; asserting `result.payload is captured[0]`
proves identity with what `run_headless_scan` actually captured, not just "payload is truthy" or
"payload is a ScanPayload instance" — the exact regression Task 6 decision 3 guards against (the
Linear issue's now-superseded `payload=None` claim). The second case repeats the same write-failure
patch after also forcing `stages.run_port_stage` to raise `FatalScanError` (the existing
`test_post_discovery_fatal_yields_partial` pattern), so the payload reaching the failed write is the
*partial* payload, covering "partial scan, then write fails" as well as "completed scan, then write
fails." Both tests assert on the returned `HeadlessScanResult` only — since `run_headless_scan`
returns normally rather than raising, "the exception does not escape" is verified by the test
completing without `pytest.raises`. Writable-workspace unchanged behavior (criterion 3) needed no
new test: `TestProgrammaticResult.test_returns_completed_result_with_written_path` and
`TestFailureSemantics.test_post_discovery_fatal_yields_partial` already exercise the real
(non-monkeypatched) `write_scan_result` for the completed and partial outcomes respectively, and
both still pass unmodified — that is the regression guard.

`test_cli_agent.py`: extended `_stub_result` with an optional `error` parameter (default `None`,
backward compatible with all existing calls) since the existing helper hardcoded `error=None` and
had no way to construct the new fatal-with-payload-and-error shape. Added
`test_cli_agent_write_failure_fatal_exits_20_and_prints_stderr`, which stubs a `fatal` result with a
non-null `scan_id` (payload present) and a realistic `OSError` message, patches
`headless.run_headless_scan` to return it, and asserts: exit code `20`; `str(error)` appears in
`capsys` stderr; stdout has exactly one non-blank line; that line's JSON key set is exactly
`{"outcome", "result_path", "scan_id"}` (the ADR-012 §3 frozen-shape assertion the task calls for,
using `set(out.keys())` rather than checking for absence of extra keys individually); and
`scan_id == "ghi-789"` (non-null), satisfying criterion 6.

### Decisions Made
- Covered both the "completed scan, write fails" and "partial scan, write fails" branches in
  `test_headless.py`, even though the task's numbered criteria only require the completed case,
  because the same `try/except` wraps both entry paths into the `if captured_payload is not None:`
  block and a regression narrowing the catch to only fire after `outcome == "completed"` would slip
  past a completed-only test.
- Used identity assertions (`result.payload is captured[0]`) instead of equality or
  `isinstance(result.payload, ScanPayload)` specifically because the task flags this as a decision
  that "will look wrong against the Linear issue" — identity is the strongest assertion available
  that the same object survived the failed write, not a copy or a fresh `None`.
- Did not add a test for "OSError from `write_scan_result`'s own `mkdir`/`write_text` still
  propagates" since that regression guard belongs to Task 5's `test_workspace.py` scope (already
  COMPLETED), not Task 6's target files.
- Skipped a dedicated "exception does not escape" test as a separate case — every
  `TestResultWriteFailure` test already demonstrates this implicitly by returning a value instead of
  raising; a third test asserting only non-escape with no other assertions would be redundant per
  the ultra-ponytail YAGNI framing.
- No `chmod`-based test added, per the explicit constraint — the suite has none and it silently
  passes as root in CI.
- Extending `_stub_result`'s signature is a test-helper change, not a production-code change; no
  CLAUDE.md "surgical changes" concern applies since it only adds an optional keyword argument that
  every existing call site ignores by default.
- Ran `uv run pytest tests/unit/test_headless.py tests/unit/test_cli_agent.py` (22 passed) and
  `uv run ruff check` on both files (clean) before finishing.

### Code Changed
- hardware-agent/tests/unit/test_headless.py
- hardware-agent/tests/unit/test_cli_agent.py

## Task 6 — Code Reviewer

### Order Given
Review Task 6 of spec 012 (DMI-69 follow-up): "Fatal outcome when the result write fails + stderr
visibility" in `hardware-agent/src/agent/headless.py` and `hardware-agent/src/agent/cli.py`, plus
their tests. Judge against Task 6's success criteria and the DMI-69 preamble's six settled
decisions — explicitly not against ADR-012/ADR-010/ARCHITECTURE.md's stale wording (Task 7 amends
those separately) and not against the Linear issue text (which is wrong on `payload=None`).

### What, How & Why
Read `TASKS.md`'s Task 6 section and the DMI-69 preamble (six decisions). Diffed the four target
files against HEAD:
- `headless.py`: `write_scan_result(...)` call now wrapped in `try/except OSError`, returning
  `HeadlessScanResult(outcome="fatal", payload=captured_payload, result_path=None, error=OSError(...))`
  with the exact message shape from the task description. The `try` wraps only the write call — the
  `partial` classification logic below it is outside the `try`, and the pre-existing pre-scan
  `mkdir` fatal branch (payload=None) is untouched.
- `cli.py`: two added lines in `_run_agent` — `if result.error is not None: print(str(result.error),
  file=sys.stderr)` — placed after the stdout JSON print and before `raise SystemExit(...)`.
- `test_headless.py`: new `TestResultWriteFailure` class, two tests (write failure after completed,
  after partial via `FatalScanError` in `run_port_stage`), monkeypatching
  `agent.headless.write_scan_result` directly — no `chmod`. Confirmed
  `test_pre_discovery_fatal_yields_fatal_no_json` (the `payload is None` test) is byte-for-byte
  unedited in the diff.
- `test_cli_agent.py`: `_stub_result` gained an `error: Exception | None = None` keyword-only-by-
  default param, all existing call sites unaffected since it's optional; new
  `test_cli_agent_write_failure_fatal_exits_20_and_prints_stderr` asserts exit 20, `str(error) in
  captured.err`, exactly one stdout line, and `set(out.keys()) == {"outcome", "result_path",
  "scan_id"}` (key-set check, not just presence) with `scan_id` non-null.

Ran, inside `hardware-agent/`:
- `uv run pytest tests/unit/test_headless.py tests/unit/test_cli_agent.py -v` → 22 passed.
- `uv run pytest` (full suite) → 496 passed.
- `uv run ruff check src/agent/headless.py src/agent/cli.py tests/unit/test_headless.py
  tests/unit/test_cli_agent.py` → All checks passed.
- `black` not installed in this environment (confirmed, not retried).
- `grep -n "ponytail:"` on the four touched files → no markers found, nothing to strip.

Confirmed via `git status`/`git diff` that `scanner/workspace.py` and `test_workspace.py` (Task 5,
approved last cycle) were not touched again in this diff, and that no `docs/` or `ARCHITECTURE.md`/
`ADR-*` files (Task 7 scope) were modified — no leak across task boundaries.

### Decisions Made
Approved. Every Task 6 success criterion is met exactly as specified:
- `OSError` only, narrow `try` around the single write call, no bare `except`/`Exception`, no retry,
  no alternate storage.
- Payload is returned (not `None`) per decision 3 — deliberately diverges from the stale Linear
  issue text, which the task explicitly instructs to disregard.
- `error` is a real `OSError` (not a new exception subclass, not a bare string), `str(exc)` embedded
  in the message — satisfies decision 5 / CLAUDE.md §2 (no single-use abstraction).
- ADR-012 §3's frozen stdout contract intact: JSON line keys are exactly `{outcome, result_path,
  scan_id}`, verified via a key-set assertion in the new test, not just key presence; the error goes
  to stderr only.
- Exception does not escape `run_headless_scan` — returns a value in both new tests.
- Writable-workspace behavior (completed/partial) is provably unchanged — pre-existing tests in
  `TestProgrammaticResult` and `TestFailureSemantics` still pass untouched.
- The pre-discovery fatal test asserting `payload is None` was not edited, remains valid under
  decision 3's rule (payload = what the scan found, or `None` if it never found anything).
- `EXIT_CODES`/`INVALID_INPUT_EXIT` drift guards and `test_headless_imports_shared_runner_and_writer`
  still green in the full run.
- No `chmod`-based test; tests monkeypatch `agent.headless.write_scan_result` directly.
- `_stub_result`'s new optional `error` param didn't break any existing caller (full suite green).
- Nothing under this diff touches Task 7's doc/ADR scope.
- No overengineering found: no new exception class, no retry/backoff, no config knob, no
  abstraction beyond the one `try/except` the task asked for. Nothing to reject under ultra
  ponytail strictness.
- No `# ponytail:` markers present to strip.

### Code Reviewed
- hardware-agent/src/agent/headless.py
- hardware-agent/src/agent/cli.py
- hardware-agent/tests/unit/test_headless.py
- hardware-agent/tests/unit/test_cli_agent.py

## agent-developer — Task 7

### Order Given
Resume Task 7 of spec 012 and align only the listed documentation with the DMI-69 result-write
failure decisions. Keep Task 7 `IN_PROGRESS`, preserve Task 4's completed entry while adding its
superseding note, correct the stale persistence-module references, avoid every forbidden path and
all application code, verify the required wording with read-only searches, and do not run
application tests.

### What, How & Why
Updated ADR-012 and the spec outcome table so `fatal` is anchored on the truthful invariant that no
result JSON was written, including the case where scanning produced a completed or partial payload
but persistence failed. Documented the result-write `OSError` as an I/O failure layered on the
runner's existing terminal classification, with the payload retained in memory and no
`result_path`.

Added the Portuguese result-write failure row and preservation-channel exception to ADR-010.
Updated the live CLI reference with the corrected exit-20 meaning, the completed-but-unwritten
stdout JSON shape, and the corresponding stderr message. Added the daemon-facing `fatal` to
`failed` mapping in ADR-011 and the no-upload exception in the Pi roadmap.

Aligned spec 012's architecture and truth documents with the headless-only persistence failure,
added the persistence-failure testing expectation, and corrected every stale persistence reference
from `tui/results.py` to `scanner/workspace.py`. Added the required Task 4 superseding note without
changing its `COMPLETED` state, and left Task 7 `IN_PROGRESS`.

Verified the required phrases and references with read-only searches, confirmed no
`tui/results.py` reference remains in spec 012 ARCHITECTURE.md, ran `git diff --check`, and applied
the roadmap-sync consistency check to PI.md's sibling roadmap documents. No application tests were
run because Task 7 is docs-only.

### Decisions Made
- Treated result-write failure as a headless outcome-layer exception, not a new runner terminal
  state or a new outcome vocabulary.
- Preserved the distinction between pre-scan fatal (`payload=None`, null `scan_id`) and
  completed/partial-but-unwritten fatal (payload retained, non-null `scan_id`, null `result_path`).
- Updated the architecture narrative to reflect DMI-68's writer relocation while retaining the
  original decision to leave `ScanRunner` in the TUI package.
- Kept roadmap sibling documents unchanged because their existing `failed` definition already
  covers a Pi that accepted a command and then broke; no milestone or security posture changed.
- Did not modify application code, dated field records, spec 011, or spec 000.

### Code Changed
- docs/adr/ADR-012-headless-exit-code-contract.md
- docs/adr/ADR-010-scan-contingency-policy.md
- docs/adr/ADR-011-pi-command-channel.md
- docs/CLI.md
- docs/roadmap/PI.md
- specs/012-headless-agent-entrypoint/ARCHITECTURE.md
- specs/012-headless-agent-entrypoint/TRUTH.md
- specs/012-headless-agent-entrypoint/TASKS.md
- specs/012-headless-agent-entrypoint/POOP.md

## test-engineer — Task 7

### Order Given
Validate every Task 7 documentation-alignment success criterion with read-only searches and
diffs, confirm forbidden paths have no Task 7 delta, distinguish the existing Task 5–6
hardware-agent changes, run lightweight documentation checks only, and append one test-engineer
ledger section without editing target documentation or application code.

### What, How & Why
PASS. Reviewed all eight target-document diffs against Task 7 and the DMI-69 decisions. Verified
that the fatal contract is anchored on no result JSON, the result-write I/O carve-out is explicit,
the Portuguese contingency row matches its document, the CLI reference includes the
completed-but-unwritten stdout and stderr example, the spec truth and architecture describe the
headless-only persistence failure, Task 4 retains its completed entry with the superseding note,
and the daemon-facing ADR and Pi roadmap map this fatal path to failed with no upload.

Read-only searches found no stale persistence-module reference in the spec architecture and
confirmed every writer reference there uses the shared scanner workspace module. Forbidden-path
diffs were empty for the dated NSPi records, spec 011, and spec 000. The six modified
hardware-agent files are exactly the prior Task 5 and Task 6 target files recorded in the ledger;
there is no additional Task 7 application-code path. The roadmap-sync check found the new Pi note
consistent with the existing backend failed-state definition and requiring no sibling roadmap
change. `git diff --check` passed. No application tests or linters were run.

### Decisions Made
PASS with no defects. Treated append-only ledger entries as the orchestrator-required exception to
Task 7's documentation scope fence; no target documentation, forbidden documentation, or
hardware-agent file was edited during this test-engineer pass.

### Code Reviewed
- docs/adr/ADR-012-headless-exit-code-contract.md
- docs/adr/ADR-010-scan-contingency-policy.md
- docs/adr/ADR-011-pi-command-channel.md
- docs/CLI.md
- docs/roadmap/PI.md
- specs/012-headless-agent-entrypoint/ARCHITECTURE.md
- specs/012-headless-agent-entrypoint/TRUTH.md
- specs/012-headless-agent-entrypoint/TASKS.md

## Task 7 — Code Reviewer

### Order Given
Act as the fresh authoritative reviewer for Task 7 of spec 012. Review every target-document
change and the developer/test-engineer ledger entries against the task's success criteria, confirm
that Task 7 added no hardware-agent scope beyond the approved Task 5–6 delta, run the full
hardware-agent test and lint gates plus documentation checks, and do not edit implementation or
target documentation.

### What, How & Why
Reviewed all eight target-document diffs against Task 7 and the DMI-69 decisions. Confirmed the
fatal contract is consistently anchored on no result JSON, the result-write failure is explicitly
an I/O layer over an already-classified payload, the Portuguese contingency row distinguishes a
failed preservation channel, and the CLI example accurately separates its stdout JSON line from
the stderr error. Verified the architecture's persistence branches, outcome table, testing row,
and writer-module references; the truth document's headless-only carve-out; Task 4's surgical
superseding note; and the daemon-facing ADR and roadmap wording.

Compared the six hardware-agent diffs with the approved Task 5–6 reviewer records and found the
same six files and recorded changes, with no additional Task 7 application scope. Confirmed the
forbidden dated-test, spec 011, and spec 000 paths have empty diffs. Applied the roadmap cross-doc
check to BACKEND.md, SECURITY.md, FRONTEND.md, README.md, ADR-011, and the architecture reference;
their existing lifecycle, failure, auth, UX, and sequencing statements remain compatible, so no
sibling roadmap edit is required.

From hardware-agent, `uv run pytest` passed all 496 tests and `uv run ruff check` passed. Repository
`git diff --check` passed. Focused searches found no stale `tui/results.py` reference in spec 012
ARCHITECTURE.md and no surviving universal claim in a target document that fatal can only occur
before preservable data exists.

### Decisions Made
Approved. Every Task 7 success criterion is satisfied, the target-document edits are accurate and
surgical, Task 4 remains completed and otherwise unchanged, forbidden documentation paths are
untouched, and Task 7 introduced zero additional hardware-agent scope. The append-only POOP entries
are treated as the workflow-required ledger exception to the task's documentation scope fence.

### Code Reviewed
- docs/adr/ADR-012-headless-exit-code-contract.md
- docs/adr/ADR-010-scan-contingency-policy.md
- docs/adr/ADR-011-pi-command-channel.md
- docs/CLI.md
- docs/roadmap/PI.md
- specs/012-headless-agent-entrypoint/ARCHITECTURE.md
- specs/012-headless-agent-entrypoint/TRUTH.md
- specs/012-headless-agent-entrypoint/TASKS.md
- hardware-agent/src/agent/cli.py
- hardware-agent/src/agent/headless.py
- hardware-agent/src/agent/scanner/workspace.py
- hardware-agent/tests/unit/test_cli_agent.py
- hardware-agent/tests/unit/test_headless.py
- hardware-agent/tests/unit/test_workspace.py
