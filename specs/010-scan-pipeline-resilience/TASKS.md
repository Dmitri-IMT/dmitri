# TASKS — Scan Pipeline Resilience & Contingency Policy (spec 010)

Execution checklist for the feature-orchestrator. Sourced from `TRUTH.md`, `ARCHITECTURE.md`,
`DESIGN.md`. Tasks run sequentially in dependency order (one coder at a time). Each task: coder →
test-engineer → code-reviewer; a task is only `COMPLETED` on a reviewer `[APPROVE]`.

Phasing (ARCHITECTURE §8): P1 stop hangs → P2 stop losing data → P3 honest cancel → P4 policy
polish. The error taxonomy (report §4.1, labelled P4) is pulled to Task 1 because P1's `nmap.py`
changes raise the taxonomy classes directly.

## Dependency graph

```
1 (errors) ─┬─► 4 (nmap) ─► 5 (discovery call sites) ─► 6 (stages P1/P2/P3) ─► 7 (stages P4) ─► 8 (ScanRunner) ─► 9 (ScanProgressScreen)
2 (config) ─┤                                          ▲                       ▲                ▲
3 (events) ─┘                                          │                       │                │
            └──────────────────────────────────────────┴───────────────────────┴────────────────┘
```

## Status table

| Task | Phase | Title | Status |
|------|-------|-------|--------|
| 1 | (foundation) | Error taxonomy module | COMPLETED |
| 2 | P1/P4 | Config knobs + per-call timeout resolver | COMPLETED |
| 3 | P2 | ScanEvent skip-accounting fields | COMPLETED |
| 4 | P1/P3 | nmap.py timeout, taxonomy raising, Popen tracking | COMPLETED |
| 5 | P1 | Thread resolved timeout through discovery call sites | COMPLETED |
| 6 | P1/P2/P3 | stages.py isolation, accounting, cancel check, timeout wiring | COMPLETED |
| 7 | P4 | stages.py transient retry + circuit breaker | COMPLETED |
| 8 | P2/P3/P4 | ScanRunner partial finalization + real cancellation | COMPLETED |
| 9 | P2/P3 | ScanProgressScreen contingency states (DESIGN) | COMPLETED |

---

## Task 1: Error taxonomy module
- **Description**: Create the `ScanError` taxonomy (ARCHITECTURE §4.1). Base `ScanError(Exception)` with `FatalScanError`, `UnitScanError`, `TransientScanError`, `BudgetExceeded(ScanError)`, and `CircuitBreakerError(BudgetExceeded)`. Export the new classes from `scanner/__init__.py` and **remove** the `NmapExecutionError` export. Re-parent the existing `ScanCancelled` (in `tui/scanner.py`) to subclass `ScanError`, keeping its name and import location.
- **Dependencies**: —
- **Target Files**: [`hardware-agent/src/agent/scanner/errors.py` (new), `hardware-agent/src/agent/scanner/__init__.py`, `hardware-agent/src/agent/tui/scanner.py` (ScanCancelled base only)]
- **Success Criteria**: `BudgetExceeded`, `UnitScanError`, `FatalScanError`, `TransientScanError` subclass `ScanError`; `CircuitBreakerError` subclasses `BudgetExceeded`; `ScanCancelled` subclasses `ScanError`. `NmapExecutionError` no longer exported from `scanner/__init__.py`. No-comments/no-docstrings style. (TRUTH "Failure taxonomy"; test mirror `test_scan_errors.py`.)
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 2: Config knobs + per-call timeout resolver
- **Description**: Add three flat fields to the `@dataclass(slots=True)` `AgentSettings` in `config.py`: `scan_deadline_s: int = 0`, `unit_failure_threshold: float = 0.5`, `transient_retries: int = 1`. Add the `TIMEOUTS` mode×stage table and `subprocess_timeout_for(scan_mode: str, stage: str) -> float` resolver beside `min_cvss_for_mode`/`deep_stage_scripts`. Values per ARCHITECTURE "Per-call subprocess timeout" table.
- **Dependencies**: —
- **Target Files**: [`hardware-agent/src/agent/config.py`]
- **Success Criteria**: `subprocess_timeout_for(mode, stage)` returns the documented table values for every (mode ∈ {quick,standard,extensive,nspi,max}, stage ∈ {discovery,ports,nse}) pair; the three new `AgentSettings` fields exist with the documented defaults and do not break existing construction sites. No-comments style.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: ScanEvent skip-accounting fields
- **Description**: Add optional `units_skipped` / `units_total` fields to `ScanEvent` in `scanner/progress.py` (report §6) so degraded `port_stage_done` / deep-stage-done events can carry skip counts. Absent/zero ⇒ clean finish line. Do not change existing event emission semantics beyond adding the optional fields.
- **Dependencies**: —
- **Target Files**: [`hardware-agent/src/agent/scanner/progress.py`]
- **Success Criteria**: `ScanEvent` accepts `units_skipped` and `units_total` with safe defaults (None/0); existing event construction in the codebase still works unchanged. No-comments style.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: nmap.py timeout, taxonomy raising, Popen tracking
- **Description**: (P1+P3) Add `timeout: float | None = None` to `NmapRunner.run_xml` / `run_streamed` (`subprocess.run(timeout=)` / `proc.wait(timeout=)`); on `TimeoutExpired` → `proc.kill()` + raise `BudgetExceeded`. `None` keeps current no-timeout behaviour for non-pipeline callers. Remove `NmapExecutionError` and raise taxonomy classes directly (nmap-not-found → `FatalScanError`; non-zero exit / bad XML → `UnitScanError`; timeout → `BudgetExceeded`). Add `TransientScanError` allow-list constant (e.g. `temporary failure in name resolution`, `connection reset`) and raise it only on a matched stderr marker. Track live `Popen` handles in a lock-guarded `_active_procs` set (distinct from `_active_run_dirs`) and expose `terminate_active()` that `proc.kill()`s each; `run_streamed` registers its `Popen` before `proc.wait()` and removes it in `finally`. `LoggedNmapRunner.run_xml` writes `terminated_by="timeout"` on a killed/timed-out step (and `"user_cancel"` on a cancel-kill).
- **Dependencies**: 1
- **Target Files**: [`hardware-agent/src/agent/scanner/nmap.py`]
- **Success Criteria**: A slow fake-nmap called with a short `timeout` is killed and raises `BudgetExceeded`; `LoggedNmapRunner` writes `terminated_by="timeout"`. `timeout=None` is unchanged behaviour. `run_xml`/`run_streamed` raise `FatalScanError`/`UnitScanError`/`TransientScanError`/`BudgetExceeded` at the correct sites; `NmapExecutionError` is gone. `terminate_active()` kills tracked procs; `run_streamed` registers/deregisters its Popen. No-comments style. (Tests: `test_nmap_timeout.py`; grep `NmapExecutionError` shows no live references except updated tests.)
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 5: Thread resolved timeout through discovery call sites
- **Description**: (P1) Add `timeout: float | None = None` to `discover_hosts` (`network_discovery.py`), `scan_ports_batch` (`port_discovery.py`, forward to both pass1/pass2 `run_xml`), and `run_nse_vulnerability_scan` (`vulnerability_detection.py`), each forwarding to its `runner.run_xml(...)`. `service_detection` is left unchanged (keeps `timeout=None`).
- **Dependencies**: 4
- **Target Files**: [`hardware-agent/src/agent/discovery/network_discovery.py`, `hardware-agent/src/agent/discovery/port_discovery.py`, `hardware-agent/src/agent/discovery/vulnerability_detection.py`]
- **Success Criteria**: Each of the three functions accepts a `timeout` param and forwards it to its `run_xml` calls; default `None` preserves existing behaviour; `service_detection` untouched. No-comments style.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6: stages.py isolation, accounting, cancel check, timeout wiring
- **Description**: (P1+P2+P3) In `run_port_stage` / `run_deep_inspection_stage`: resolve `subprocess_timeout_for(settings.scan_mode, "ports"|"nse")` and pass it into `scan_ports_batch` / `run_nse_vulnerability_scan`; resolve discovery timeout is Task 8's job. Add `cancel_event: threading.Event | None = None` (keyword-defaulted, preserving current positional signature) to both stage fns and check it inside the `as_completed` loop, ceasing to read further futures once set. Wrap each unit in try/except so a `UnitScanError` records+skips the unit and the stage continues (never re-raises the first future exception). Maintain per-stage failed/total accounting; thread skipped/total counts into `build_metadata` and into the `port_stage_done` / deep-stage-done `ScanEvent` (`units_skipped`/`units_total`); emit per-unit skip events (ip + timeout vs failed) for the `↳` log lines. Add `terminated_by: str | None = None` param to `build_metadata` so the scan-level end cause rides in `payload.metadata["terminated_by"]`.
- **Dependencies**: 2, 3, 4, 5
- **Target Files**: [`hardware-agent/src/agent/scanner/stages.py`, `hardware-agent/src/agent/scanner/progress.py` (new event kinds: a `deep_stage_done` and a per-unit skip signal carrying ip + timeout-vs-failed)]
- **Success Criteria**: One unit raising `UnitScanError` leaves other units' data intact and the stage does not raise (TRUTH "Unit failure is isolated"); a per-step `BudgetExceeded` (single-unit timeout) skips that unit with reason "timeout" and the stage continues; failed/timed-out ip recorded and surfaced via per-unit skip events; `cancel_event` set mid-loop stops reading further futures; `port_stage_done` and the new `deep_stage_done` carry `units_skipped`/`units_total` (host-counted); `build_metadata(..., terminated_by=...)` writes `metadata["terminated_by"]`; resolved per-call timeouts (`subprocess_timeout_for(settings.scan_mode, "ports"|"nse")`) are passed to `scan_ports_batch`/`run_nse_vulnerability_scan`; `target_pct` handles the new kinds (deep_stage_done → d+p+i; skip events → None). Existing positional call sites and `test_stage_reporter.py` still pass. No-comments style. (Tests: `test_stage_isolation.py`.)
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 7: stages.py transient retry + circuit breaker
- **Description**: (P4) In the per-unit wrapper: on `TransientScanError`, retry the unit up to `settings.transient_retries` times; if it still fails, demote to a `UnitScanError` (record+skip). A `BudgetExceeded`/timeout unit is **never** retried. Maintain failure accounting and, when failed/total in a stage exceeds `settings.unit_failure_threshold`, raise `CircuitBreakerError` (subclass of `BudgetExceeded`) after preserving everything gathered so far.
- **Dependencies**: 6, 1, 2
- **Target Files**: [`hardware-agent/src/agent/scanner/stages.py`]
- **Success Criteria**: A unit raising `TransientScanError` once then succeeding is retried `transient_retries` times and its data kept; raising twice demotes to a unit failure; a `BudgetExceeded`/timeout unit is not retried (TRUTH "Transient retried once"). When failed/total > `unit_failure_threshold` the stage raises `CircuitBreakerError`; below threshold it continues (TRUTH "Circuit breaker stops scan"). No-comments style. (Tests: `test_stage_isolation.py`, `test_circuit_breaker.py`.)
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 8: ScanRunner partial finalization + real cancellation
- **Description**: (P2+P3+P4) Refactor `ScanRunner._run` (`tui/scanner.py`) so payload build + `on_complete` is reachable from cancel / timeout / post-discovery-fatal with `partial_result=True` + `interrupted_stage` + `terminated_by` set per the §4.2 decision table: `FatalScanError` before discovery → `on_error`, no payload; after discovery → finalize partial (`terminated_by="error"`); `BudgetExceeded` → finalize partial (`terminated_by="timeout"`, but `CircuitBreakerError` → `"error"` via `isinstance`); `ScanCancelled` → finalize partial (`terminated_by="user_cancel"`); zero hosts → valid non-partial empty (`terminated_by="completed"`). Stash the built runner on `self._active_runner` (lock-guarded, set right after `build_runner`, cleared in `finally`); `request_cancel()` does `self._cancel_event.set()` **and** `self._active_runner.terminate_active()`. Pass `self._cancel_event` into both stage fns. Resolve `subprocess_timeout_for(self.scan_mode, "discovery")` and pass it to `discover_hosts`. Enforce `scan_deadline_s` between stages/units. Confirm the inline `AgentSettings(...)` (L72-76) carries the three new knobs (defaults, not shadowed) — CLAUDE.md integration rule.
- **Dependencies**: 1, 2, 4, 6, 7
- **Target Files**: [`hardware-agent/src/agent/tui/scanner.py`]
- **Success Criteria**: On cancel/timeout/post-discovery-fatal, `on_complete` receives a payload with `metadata["partial_result"] is True`, `metadata["interrupted_stage"]` set, and `metadata["terminated_by"]` ∈ {user_cancel, timeout, error} matching the cause; fatal-before-discovery yields `on_error` and no payload; zero hosts yields a valid non-partial empty result (`terminated_by="completed"`). `request_cancel()` calls `runner.terminate_active()`; in-loop cancel stops reading further futures. Inline `AgentSettings` carries the new knob defaults. (TRUTH ACs "Partial result on late fatal", "Cancel keeps partial and halts work", "Fatal before data stops cleanly", "Zero hosts finishes valid", "Config knobs honored from TUI".) Tests: `test_scan_runner_partial.py`, `test_scan_runner_cancel.py`; regression `test_scan_runner_events.py`/`test_scan_runner_timing.py` pass. No-comments style.
- **Dependencies note**: This task adds behaviour reachable from the TUI; Task 9 must thread any consequent screen change. Grep `ScanRunner(` and verify `scan_progress.py` + runner tests still construct correctly.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 9: ScanProgressScreen contingency states (DESIGN)
- **Description**: (P2+P3, DESIGN.md) Add the `#scan-badge` `Static` widget under the header and its CSS block in `app.tcss`. Implement the Partial, Fatal, and Cancelling states: spinner hides on every terminal state; only Completed sets the bar to 100%; Partial/Fatal/Cancelling hold the last real value. `action_abort` while running enters **Cancelling** (request cancel, do not dismiss) and resolves to Partial (data exists, `dismiss((payload, True/False))`) or Aborted (`dismiss(None)`); a second Ctrl+X while cancelling is ignored. `_handle_error` distinguishes Fatal (no payload → error badge, only `#btn-back-home`) from Partial (routed through `on_complete`). Degraded/timeout/partial activity-log line templates, outcome badge strings, and end-action labels exactly per DESIGN Copy (do not reword). Generalize the `_done` guard to a terminal predicate covering Completed|Partial|Fatal (Cancelling is not terminal). Verify `home.py:74` `ScanProgressScreen(subnet, scan_mode)` needs no new constructor param (CLAUDE.md integration rule).
- **Dependencies**: 8
- **Target Files**: [`hardware-agent/src/agent/tui/screens/scan_progress.py`, `hardware-agent/src/agent/tui/app.tcss`, `hardware-agent/src/agent/tui/screens/home.py` (verify only)]
- **Success Criteria**: `#scan-badge` hidden while running/on success, shown with the exact Partial/Fatal strings in those states; `#btn-view-scan` hidden in Fatal, shown labelled `View partial scan` in Partial; bar non-100% in Partial/Fatal; Cancelling appends the stop line and ignores a second Ctrl+X until the runner callback; degraded finish lines render only when `units_skipped > 0`. Existing `test_scan_progress_screen.py` patterns pass. No-comments style.
- **Status**: COMPLETED
- **Review Rejections**: 0
