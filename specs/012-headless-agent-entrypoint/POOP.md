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
