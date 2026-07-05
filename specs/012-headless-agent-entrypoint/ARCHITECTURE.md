# ARCHITECTURE — Headless agent entrypoint (DMI-51)

## System context

Pipeline: discovery → port scan → NSE/deep inspection → normalization (`ScanPayload`) →
**persistence / front door**. Today there is exactly one front door onto that pipeline: the
TUI. An operator opens a screen, `ScanProgressScreen` constructs `ScanRunner`
(`tui/scanner.py`), the runner drives `discovery.discover_hosts` → `stages.run_port_stage` →
`stages.run_deep_inspection_stage` → `_build_payload` (normalization), and when the payload
comes back the **screen's owner** (`home.py:_on_scan_complete`) writes it to disk via
`tui/results.py:write_scan_result`.

This feature adds a **second front door** — a headless entrypoint — onto the **same** runner
and the **same** persistence function. It is a single-layer change under
`hardware-agent/src/agent/`. It is the foundation `docs/roadmap/PI.md` § "Pi runtime
(September Control)" names: the future daemon runs `dmitri agent` and, on command, runs the
same `ScanRunner`/stages → nmap pipeline the TUI runs. Transport (WebSocket), upload, and
systemd/daemonization are **explicitly out of scope** (ADR-011 concern); this spec delivers
only the callable pipeline the daemon will later sit on top of.

Two structural facts, verified in code, make this a small change:

- **`ScanRunner` is already Textual-free.** `tui/scanner.py` imports only `agent.config`,
  `agent.discovery`, `agent.normalize`, `agent.scanner.*`, and `agent.utils.network` — no
  `textual`, no screen. `agent/tui/__init__.py` is a bare docstring. So a non-TUI module can
  `from agent.tui.scanner import ScanRunner` without importing or constructing any screen.
- **Persistence is not inside `ScanRunner`.** `ScanRunner` produces the `ScanPayload` and
  hands it to `on_complete`; the JSON write lives in `tui/results.py:write_scan_result`, which
  imports no Textual either. Reusing that one function guarantees byte-identical JSON shape and
  location across both front doors.

## Design decisions

### 1. Keep `ScanRunner` and `write_scan_result` where they are — do not relocate

The task flagged the layering question: if the shared runner pulled in Textual, the headless
path would drag a screen into a daemon. It does not. `ScanRunner` (`tui/scanner.py`) and
`write_scan_result` (`tui/results.py`) are both import-clean of Textual (verified above). The
headless entrypoint therefore imports them in place.

**Rejected — relocate `ScanRunner`/`write_scan_result` down to the `scanner/` layer.** It is
the "tidier" package layout, but it is a larger, riskier move: it rewrites the imports in
`scan_progress.py`, `home.py`, and four `test_scan_runner_*.py` modules purely mechanically,
widening the blast radius against the hard requirement that the **TUI behave byte-for-byte
unchanged**, and it collides directly with the **pending sibling spec 011**, which is already
editing `tui/scanner.py` (relocating `ScanCancelled` into `scanner/errors.py`, adding the
cancel-before-spawn guard). Moving the whole class out from under 011's feet invites a merge
conflict for zero functional gain. Smallest correct move wins: leave them, import them.

### 2. Add one synchronous public method to `ScanRunner`; do not fork the pipeline

`ScanRunner.start()` spawns a daemon thread so the TUI stays responsive. A headless caller has
no UI to keep responsive — it wants to block until the scan finishes and then read the result.
The runner already exposes `_run()` (the whole pipeline), which the existing tests call
directly, but it is private and communicates only through the `on_complete`/`on_error`
callbacks.

**Decision:** add a thin **public** method `ScanRunner.run_blocking()` that runs `self._run()`
on the calling thread and returns `None` (results still delivered through the existing
callbacks). The headless entrypoint constructs a `ScanRunner` with capturing callbacks, calls
`run_blocking()`, then reads the captured payload/error. This reuses the single pipeline
implementation verbatim — same stages, same ordering, same budgets, same partial/fatal
finalization (ADR-010) — with **no forked scan logic**.

- **Rejected — `start()` then `self._thread.join()`.** Spawns a thread only to immediately
  join it, and forces the caller to reach into the private `_thread` attribute (or forces a
  new `join()` method anyway). `run_blocking()` is simpler and needs no thread.
- **Rejected — call the private `_run()` from the headless module.** Works (the tests do it),
  but reaching across a module boundary into a `_`-prefixed method is exactly the seam a
  one-line public method should cover.
- **TUI impact: none.** `run_blocking()` is additive; `ScanProgressScreen` keeps calling
  `start()`. No constructor parameter changes (see §CLAUDE.md verification).
- **Coordination with spec 011:** 011 edits the `ScanCancelled` import line and deletes the
  local `ScanCancelled` class in this same file; `run_blocking()` is a new method on different
  lines — no textual conflict. The headless v1 path does not cancel, so it neither depends on
  nor contradicts 011's cancel-before-spawn guard or its relocated `ScanCancelled`.

### 3. New front-door module `agent/headless.py` with a programmatic API + a CLI wrapper

A single new module owns the headless front door. It exposes the programmatic API the daemon
will call and is wrapped by the `dmitri agent` CLI. It does **not** re-implement any scan step;
it is glue: validate → build `ScanRunner` → `run_blocking()` → `write_scan_result` → map
outcome.

`run_headless_scan(mode, subnet, *, workspace_root=None, reporter=None, runner=None) ->
HeadlessScanResult`:

1. **Validate first (fail fast, no scan starts).** `validate_inputs(mode, subnet)`:
   - `mode` must be in `config.SCAN_MODES` (new tuple, §Data model) → else `InvalidScanInput`.
   - `subnet` must be CIDR: reject if `"/"` not present, then `ipaddress.IPv4Network(subnet,
     strict=False)` must parse → else `InvalidScanInput`. IPv4-only and CIDR-required matches
     both `network.py`'s existing use and the `ScanPayload.SubnetCIDR` contract, so a validated
     subnet is guaranteed to pass payload validation downstream.
2. **Resolve workspace.** `workspace_root` defaults to the TUI's own results dir so headless
   and TUI write to the **same place** in the same shape: `load_config()` → `results_dir` if a
   config exists, else `default_results_dir()` (both from `tui/config.py`). A caller (the
   future daemon, or tests) may pass an explicit `workspace_root`. Pre-create the
   `results/` subdir; if that raises `OSError`, return `outcome="fatal"` before scanning
   (ADR-010: "workspace não gravável" is Fatal-before-data).
3. **Run the shared pipeline.** Construct `ScanRunner(subnet, mode, reporter=reporter,
   on_complete=<capture>, on_error=<capture>, workspace_root=workspace_root, runner=runner)`
   and call `run_blocking()`. The `runner` passthrough mirrors `ScanRunner`'s own injection
   seam and exists for tests (inject a fake `NmapRunner`); production/daemon leaves it `None`
   so `build_runner` creates a `LoggedNmapRunner`.
4. **Persist + classify.** If a payload was captured, `write_scan_result(payload,
   str(workspace_root))` (the same function the TUI uses) and classify from
   `payload.metadata["partial_result"]`: `True` → `"partial"`, else `"completed"`. If an error
   was captured instead (runner's `on_error`), `outcome="fatal"`, no JSON. Return
   `HeadlessScanResult(outcome, payload, result_path, error)`.

**Reporter contract.** `ScanRunner` guards `None` reporters (`_emit` is a no-op when
`reporter is None`), so the **programmatic API defaults to `reporter=None`** — the daemon will
supply its own later. The **CLI** passes a minimal `StderrReporter` (implements the
`ScanReporter` protocol: one `emit(event)` printing `event.message` to `stderr`) so a developer
sees stage progress. No new event kinds, no `progress.py` change — TRUTH forbids new progress
UI beyond what invocation requires.

**Rejected — headless writes JSON inside `ScanRunner`.** Would change the TUI path (which
writes in `home.py`) and risk double-writes; keeping the write in the front door leaves the TUI
byte-for-byte unchanged and still shares one persistence function.

### 4. `dmitri agent <mode> <subnet>` CLI, machine-readable outcome

`cli.py` gains an `agent` branch (name per `docs/roadmap/PI.md`). Style matches the existing
hand-rolled `sys.argv` dispatch — no argparse rewrite.

- `dmitri agent <mode> <subnet>` — exactly two positional args after `agent`; wrong arity →
  usage error, exit `2`.
- Reuse `_check_nmap()` (as `dmitri start` does); if nmap is missing, print the existing
  install guidance and exit `20` (fatal — no scan possible).
- Call `run_headless_scan(mode, subnet, reporter=StderrReporter())`.
- On `InvalidScanInput`: print the message to `stderr`, exit `2`.
- On success: print one machine-readable JSON line to `stdout`
  (`{"outcome": ..., "result_path": ..., "scan_id": ...}`) and exit per the outcome→code map.

**Machine-readable outcome (pinned).** Both front doors report outcome machine-readably: the
programmatic API returns `HeadlessScanResult.outcome`; the CLI encodes it in the exit code
(and echoes the JSON line).

| Outcome | Meaning | Exit code | JSON result written? |
|---------|---------|-----------|----------------------|
| `completed` | scan finished, `partial_result` false | `0` | yes |
| `partial` | scan preserved partial work (ADR-010: cancel / timeout / circuit-breaker / post-discovery fatal) | `10` | yes |
| `fatal` | fatal before any preservable data (nmap missing, unwritable workspace, pre-discovery fatal) | `20` | no |
| invalid input | unknown mode or malformed subnet — nothing ran | `2` | no |

The `completed`/`partial`/`fatal` split is exactly the runner's own terminal classification
(`terminated_by` ∈ `{"completed","user_cancel","timeout","error"}` + `partial_result`), so the
outcome the daemon reads matches the terminal state the TUI runner records for the same run.

## Data model / contracts

- **`config.py` — add `SCAN_MODES: tuple[str, ...] = ("quick", "standard", "extensive",
  "nspi", "max")`.** Single enumerable source of truth for the mode set that is currently only
  a repeated `Literal`. Used by `validate_inputs`. Must stay in lockstep with the `AgentSettings.scan_mode` /
  `ScanPayload.scan_mode` `Literal`s (asserted in tests). No other config change — no new
  timeout, budget, or knob.
- **`ScanPayload` / `DevicePayload` / `FindingPayload` — unchanged.** Headless produces the
  same `ScanPayload` (`ScanRunner._build_payload`) and serializes it with the same
  `write_scan_result` (`model_dump(mode="json")`), so the on-disk JSON is identical in schema,
  fields, and filename pattern (`<ISO-ts>_<subnet-slug>.json` under `<workspace>/results/`).
  Only run-specific values (timestamps, hosts, `scan_id`) differ.
- **`terminated_by` / `partial_result` / `interrupted_stage` — reused, not extended.** No new
  terminal states; ADR-010 vocabulary only.
- **`ScanRunner` — new method `run_blocking(self) -> None`.** No constructor-signature change.
- **`scanner/progress.py` — no change.** No new `ScanEvent` kind or field; the `StderrReporter`
  consumes the existing `ScanReporter` protocol.
- **New public surface in `agent/headless.py`:**
  - `HeadlessScanResult` dataclass: `outcome: Literal["completed","partial","fatal"]`,
    `payload: ScanPayload | None`, `result_path: Path | None`, `error: Exception | None`.
  - `class InvalidScanInput(ValueError)`.
  - `EXIT_CODES: dict[str, int] = {"completed": 0, "partial": 10, "fatal": 20}` and
    `INVALID_INPUT_EXIT = 2`.
  - `SCAN_MODES` re-used from `config`.
  - `validate_inputs(mode, subnet) -> None`; `run_headless_scan(...) -> HeadlessScanResult`;
    `class StderrReporter`.

## New files and naming (mandatory)

All paths under `hardware-agent/src/agent/` (source) and `hardware-agent/tests/` (tests).

| Layer | Path | New/Touch | Responsibility of the change |
|-------|------|-----------|------------------------------|
| Headless front door | `hardware-agent/src/agent/headless.py` | **New** | `run_headless_scan` (programmatic API), `validate_inputs`, `HeadlessScanResult`, `InvalidScanInput`, `EXIT_CODES`/`INVALID_INPUT_EXIT`, `StderrReporter`. New **`ScanRunner` call site**. |
| CLI | `hardware-agent/src/agent/cli.py` | Touch | Add `dmitri agent <mode> <subnet>` branch; reuse `_check_nmap()`; map outcome→exit code; print machine-readable JSON line. Update usage string. |
| Config | `hardware-agent/src/agent/config.py` | Touch | Add `SCAN_MODES` tuple (mode-validation source). No timeout/budget change. |
| TUI runner | `hardware-agent/src/agent/tui/scanner.py` (`ScanRunner`) | Touch | Add public `run_blocking()` (calls `self._run()`). **No constructor parameter added.** Coordinate with spec 011 (same file). |
| Persistence (reused) | `hardware-agent/src/agent/tui/results.py` (`write_scan_result`) | **Reused, no change** | Shared JSON write; imported by `headless.py`. Verified Textual-free. |
| TUI screen | `hardware-agent/src/agent/tui/screens/scan_progress.py` (`ScanProgressScreen`) | **No change** | Existing `ScanRunner(...)` call site at line 131 — unchanged (no new constructor arg to thread). |
| TUI owner | `hardware-agent/src/agent/tui/screens/home.py` (`_on_scan_complete`) | **No change** | Existing `ScanProgressScreen(...)` call site at line 74 — unchanged. |

## CLAUDE.md integration-rule verification

The rule: any new parameter on the shared runner must be threaded through `ScanRunner` **and**
`ScanProgressScreen`; every constructor/call site must be accounted for before marking
architecture complete.

**This feature adds no new `ScanRunner` or `ScanProgressScreen` constructor parameter** — only
an additive method (`run_blocking()`) and a new *caller* (`headless.py`). So there is nothing
to thread. Grep of every constructor/call site, with the per-site verdict:

`ScanRunner(...)`:

| Site | Type | Change |
|------|------|--------|
| `tui/screens/scan_progress.py:131` | production | **Unchanged** — same args (`reporter`, `on_complete`, `on_error`, `workspace_root`). |
| `agent/headless.py` | production | **New call site** — constructs with `reporter`, `on_complete`, `on_error`, `workspace_root`, `runner`; drives via `run_blocking()`. |
| `tests/unit/test_scan_runner_events.py` (8×) | test | Unchanged — constructor signature unchanged. |
| `tests/unit/test_scan_runner_cancel.py` (5×) | test | Unchanged. |
| `tests/unit/test_scan_runner_partial.py` (3×) | test | Unchanged. |
| `tests/unit/test_scan_runner_timing.py` (1×) | test | Unchanged. |

`ScanProgressScreen(...)`:

| Site | Type | Change |
|------|------|--------|
| `tui/screens/home.py:74` | production | **Unchanged** — no new arg. |
| `tests/unit/test_scan_progress_screen.py:49` | test | Unchanged. |

Conclusion: the integration rule is satisfied — no parameter to thread, the one new `ScanRunner`
call site (`headless.py`) is listed, and both TUI call sites are confirmed unchanged.

## Constraints (scope fence)

- **One pipeline, no fork.** Headless reuses `ScanRunner._run()` (via `run_blocking()`), the
  `scanner.stages` functions, and `write_scan_result` — no duplicated discovery/port/deep/
  normalize/persist logic. A future pipeline fix applies to both front doors automatically.
- **TUI byte-for-byte unchanged.** No screen, flow, copy, or output change; the only edit to a
  TUI-package file is the additive `run_blocking()` method on `ScanRunner`.
- **No transport, no upload, no daemonization/systemd/reconnect, no WebSocket** (ADR-011 /
  later issues). `dmitri agent` v1 runs one scan and exits.
- **No new scan modes; no new config surface** beyond `SCAN_MODES` (needed to validate the
  mode input) and the workspace default already used by the TUI.
- **Do not resurrect the discontinued env-driven path** (`load_settings`, `_parse_scan_mode`,
  `ScanOrchestrator.run()`). They stay inert; removing them is issue #64's job.
- **No `HUMAN_INFRA_REQUIRED`.** No new hardware, daemon, external tool, or nmap script — nmap
  is already a dependency and is preflight-checked by `_check_nmap()`.

## Testing expectations

Tests under `hardware-agent/tests/unit/`, mirroring the named existing test. Run
`uv run pytest` and `uv run ruff check` from `hardware-agent/`. No comments/docstrings in tests.
Mirror `test_scan_runner_partial.py`'s harness: a `_FakeRunner(NmapRunner)` returning stub XML,
`monkeypatch` of `agent.tui.scanner.check_network_connectivity` and
`agent.tui.scanner.discover_hosts`, and (for failure cases) `monkeypatch` of
`stages.run_port_stage`. Drive headless through `run_headless_scan(..., runner=_FakeRunner(),
workspace_root=tmp_path)`.

| Acceptance criterion (TRUTH) | Test | Mirror / notes |
|------------------------------|------|----------------|
| Same shape | new `test_headless.py` | Run headless with a fake runner into `tmp_path`; assert a `<ts>_<subnet-slug>.json` exists under `tmp_path/results`, load it, `ScanPayload.model_validate(...)` succeeds. Run `ScanRunner` directly (mirror `test_scan_runner_partial._build_runner`) with the same inputs and assert the two payloads' structure/fields match (only ts/scan_id differ). |
| Programmatic result | `test_headless.py` | Assert `run_headless_scan(...)` returns `HeadlessScanResult(outcome="completed", payload=<ScanPayload>, result_path=<Path>)` and the returned `result_path` is the written file. |
| Failure semantics match | `test_headless.py` | Monkeypatch `stages.run_port_stage` to raise `FatalScanError` (as `test_scan_runner_partial.TestPostDiscoveryFatal` does). Assert `outcome="partial"`, written JSON has `metadata.partial_result is True`, `terminated_by == "error"`, `interrupted_stage == "ports"` — identical to what `ScanRunner` yields for the same failure. Also cover a pre-discovery fatal → `outcome="fatal"`, no JSON. |
| TUI untouched | existing `test_scan_progress_screen.py`, `test_scan_runner_*` | Must remain green with zero edits — proves the additive `run_blocking()` and the new module changed nothing in the TUI path. |
| One pipeline | `test_headless.py` | Assert the headless run goes through the shared stages: monkeypatching `stages.run_port_stage` changes the headless result (it is not a duplicated code path), and assert `headless` imports `ScanRunner`/`write_scan_result` (no private scan reimplementation). |
| Input validation | `test_headless.py` | `run_headless_scan("bogus", "192.168.1.0/24")` raises `InvalidScanInput`; `run_headless_scan("quick", "not-a-subnet")` and `run_headless_scan("quick", "192.168.1.5")` (no `/`) raise; assert `discover_hosts` was never called and no `results/` dir was created. |
| CLI exit codes | new `test_cli_agent.py` | Drive `cli.main()` with monkeypatched `sys.argv` and a stubbed `run_headless_scan`; assert `SystemExit` code = `0`/`10`/`20` per outcome, `2` for bad arity and `InvalidScanInput`, `20` when `_check_nmap()` is stubbed False. Mirror any existing cli test harness; if none, this is the first. |
| Modes source in sync | extend `test_config_timeouts.py` (or new `test_config_modes.py`) | Assert `config.SCAN_MODES == ("quick","standard","extensive","nspi","max")` and equals `typing.get_args(...)` of the `ScanPayload.scan_mode` `Literal` so the validation list can't drift. |
| Suites green | full run | `uv run pytest` + `uv run ruff check` pass. |
