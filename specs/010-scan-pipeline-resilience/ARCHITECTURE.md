# ARCHITECTURE — Scan Pipeline Resilience & Contingency Policy

Implements the behaviour in `specs/010-scan-pipeline-resilience/TRUTH.md` and grounds it in the
audit `docs/implementation/SCAN-PIPELINE-RESILIENCE.md` (failure modes F1–F8, error taxonomy §4.1,
decision table §4.2, structural changes §5, config knobs §7, phasing §8). Related: ADR-004
(scan methodology). Single-layer Python app — **no INTEGRATION.md**; the partial-to-backend
contract question is explicitly out of scope (TRUTH "Out of scope (v1)", report §9).

> Note: the report cites paths under `scanner/scanner.py` (e.g. `:87`, `:174-175`). That module
> does not exist in the current tree — the live scan runner is `agent/tui/scanner.py` (`ScanRunner`).
> All references below use the real paths verified against the code.

## System context

Pipeline today (TUI scan, daemon worker thread owned by `ScanRunner._run`):

```
check_network_connectivity → discover_hosts → run_port_stage → run_deep_inspection_stage
  → extract_findings → build_metadata → ScanPayload → on_complete → ScanProgressScreen
```

Modules touched under `hardware-agent/src/agent/`:

- `scanner/nmap.py` — `NmapRunner.run_xml` / `run_streamed` / `LoggedNmapRunner.run_xml`. Today no
  subprocess timeout (F1), no live `Popen` tracking (F4), single bare `NmapExecutionError` (F6).
- `scanner/stages.py` — `run_port_stage`, `run_deep_inspection_stage` re-raise the first
  `future.result()` exception (F2); `build_metadata` already accepts `partial_result` /
  `interrupted_stage` but nothing sets them (F3).
- `scanner/workspace.py` — `TerminatedBy = Literal["completed","error","user_cancel","timeout"]`
  (L12) already supports the terminal states; `write_meta_json` writes `terminated_by`.
- `tui/scanner.py` — `ScanRunner._run`: builds a payload only on full success; on `ScanCancelled`
  it emits `failed` and `pass`es (loses everything, F3/F4); `_check_cancel` only fires *between*
  stages (F4); constructs `AgentSettings` inline (L72-76).
- `tui/screens/scan_progress.py` — `ScanProgressScreen`: `action_abort` dismisses `None` on cancel
  (discards partial); `_handle_error` only notifies. Constructs `ScanRunner` (L115).
- `config.py` — `AgentSettings`; gains the four contingency knobs (report §7).
- **New** `scanner/errors.py` — the `ScanError` taxonomy (report §4.1).

The feature sits across the **scan-step execution** (nmap.py), **stage orchestration** (stages.py),
and **finalization/cancellation** (tui/scanner.py) seams. No new pipeline path is introduced —
existing runner, executor loops, `merge_ports`, and `build_metadata` are reused.

## Data model / contracts

### Error taxonomy (new module `scanner/errors.py`, report §4.1)

A base `ScanError(Exception)` with subclasses carrying the stop/continue policy:

| Class | Maps to | Raised by |
|-------|---------|-----------|
| `FatalScanError` | STOP (decision table rows 1–2) | nmap binary missing, invalid args, permission denied, workspace not writable |
| `UnitScanError` | CONTINUE (skip unit) | one batch/host: non-zero exit, malformed XML, NSE crash |
| `TransientScanError` | RETRY once → demote to `UnitScanError` | temporary resolve / network blip |
| `BudgetExceeded(ScanError)` | STOP, keep partial (treat like cancel) | per-step subprocess timeout, scan wall-clock deadline |

- **Circuit breaker (refine-specs decision):** the unit-failure breaker raises
  `CircuitBreakerError(BudgetExceeded)` — a subclass, so the existing `except BudgetExceeded`
  "stop + keep partial" branch in `ScanRunner` catches it with no new handler. `ScanRunner` uses
  `isinstance(exc, CircuitBreakerError)` to set `terminated_by="error"` (badge "scan stopped early"),
  vs `"timeout"` for a real `BudgetExceeded`. Recorded in ADR-010.
- **Transient detection (refine-specs decision):** `TransientScanError` is raised **only** when
  nmap stderr matches a small explicit allow-list of known-transient markers (a module constant in
  `nmap.py`, e.g. `temporary failure in name resolution`, `connection reset`). Any other non-zero
  exit / malformed XML → `UnitScanError` (skip, no retry). A **timeout never retries** — it raises
  `BudgetExceeded` directly (an unresponsive host would just time out again). This keeps retry off
  the fragile path of guessing intent from arbitrary stderr, and avoids doubling the cost of
  deterministic failures. The `transient_retries` knob bounds retries of matched transients only.
- `ScanCancelled` (currently in `tui/scanner.py`) is re-parented to subclass `ScanError` so the
  `_run` handler and stage loops branch uniformly. Keep its name and import location to avoid
  churning `test_scan_runner_events.py`.
- `NmapExecutionError` (currently `scanner/nmap.py:24`, re-exported by `scanner/__init__.py` and
  asserted in `tests/unit/test_logged_runner.py:110`) is **removed** and fully replaced by the
  taxonomy — we do not keep it alive just to satisfy existing tests. `nmap.py` raises the precise
  class at each site (nmap-not-found → `FatalScanError`; non-zero exit / bad XML →
  `UnitScanError`; timeout → `BudgetExceeded`). Every call site and test that referenced
  `NmapExecutionError` (`scanner/__init__.py` export, `tests/unit/test_logged_runner.py:110`, and
  any other importers — grep `NmapExecutionError` before completing) is updated to the new class
  or deleted and rewritten against the taxonomy.

### Decision table wiring (report §4.2) — call-site behaviour

| Situation | Where enforced | Outcome |
|-----------|----------------|---------|
| `FatalScanError` before discovery | `ScanRunner._run` except branch | STOP, `on_error`, no payload |
| `FatalScanError` after discovery | `ScanRunner._run` except branch | STOP, finalize partial payload |
| `TransientScanError` on a unit | per-unit wrapper in `stages.py` | retry once, then demote |
| `UnitScanError` on a unit | per-unit wrapper in `stages.py` | record + skip, continue |
| unit failure ratio > threshold | per-stage accounting in `stages.py` | raise `CircuitBreakerError` → `ScanRunner` finalizes partial, `terminated_by="error"` |
| discovery 0 hosts | `ScanRunner._run` (already handled) | skip downstream, valid empty result |
| `ScanCancelled` | in-loop check + `ScanRunner` | kill subprocesses, finalize partial |
| `BudgetExceeded` | `nmap.py` (step) / `ScanRunner` (deadline) | finalize partial |

### Config knobs (report §7) — added to `AgentSettings` (`config.py`)

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `scan_deadline_s` | `int` | `0` | overall wall-clock budget; `0` = unlimited |
| `unit_failure_threshold` | `float` | `0.5` | circuit-breaker ratio of failed/total units per stage |
| `transient_retries` | `int` | `1` | retries per unit on `TransientScanError` |

These three stay flat scalars on the `@dataclass(slots=True)` `AgentSettings`, matching the existing
field style, and flow through the inline `AgentSettings(...)` in `tui/scanner.py`. The per-step nmap
timeout is **not** an `AgentSettings` scalar — see below.

### Per-call subprocess timeout — mode × stage (refine-specs decision)

The timeout is a **per-call parameter** (Option B), and its value varies by **scan mode × stage**.
It lives in `config.py` as a table + resolver, mirroring the existing `min_cvss_for_mode` /
`deep_stage_scripts` helpers — **not** an `AgentSettings` field. The resolver needs only `scan_mode`
(already on `settings`) and the stage name (known at each call site), so it adds **no** new value to
thread through `ScanRunner` / `ScanProgressScreen`.

```python
def subprocess_timeout_for(scan_mode: str, stage: str) -> float: ...
```

These are a **hang safety-net, not a duration SLA** — they fire only when a single nmap process is
genuinely stuck (filtered/unresponsive host, `-p-` deadlock), never during a normal slow scan. The
timeout is **per nmap process**, not per stage: the port/deep stages fan out many nmap calls in
parallel, so e.g. `nse=900` means *each host's* script run may take up to 900s.

| Stage \ Mode | quick | standard | extensive | nspi | max |
|--------------|-------|----------|-----------|------|-----|
| discovery (one `-sn` over whole subnet) | 600 | 600 | 600 | 600 | 600 |
| ports (per batch) | 600 | 900 | 1800 | 600 | 3600 |
| deep / nse (per host) | 900 | 1200 | 2400 | 1200 | 3600 |

Notes (values are seconds, lenient on purpose per the refine-specs call, tunable):

- **Discovery is one nmap call over the entire subnet** and its args (`-sn -PE -T4`) do not change
  with mode — its duration scales with **subnet size (host count)**, not mode. A "quick" scan on a
  large subnet still does a big ping sweep, so discovery is uniformly lenient (600s) across modes,
  tripping only on a true hang. (This is the "many hosts takes time" case the operator raised.)
- **Many hosts** stretches discovery (one call) and multiplies the *count* of port/deep calls (run in
  parallel, bounded by `max_workers`) — it does **not** lengthen any single port/deep call, so the
  per-call timeouts above need not grow with host count. The whole-scan ceiling is the separate
  optional `scan_deadline_s` (default `0` = unlimited, so it never prematurely kills).
- `run_xml(arguments, timeout=None)` keeps `None` = no timeout (current behaviour) so non-pipeline
  callers (`service_detection`) are unchanged; the pipeline call sites pass a resolved value.

### Partial-result contract (reuse existing hooks — do not invent terminal states)

- `build_metadata` already takes `partial_result: bool` and `interrupted_stage: str | None`
  (`stages.py:216-248`). Wire `ScanRunner` to pass them. **Add one parameter** `terminated_by: str | None = None`
  so the scan-level end cause (`"user_cancel"` / `"timeout"` / `"error"` / default `"completed"`)
  rides in `payload.metadata["terminated_by"]`. Today that literal only lives in each per-nmap-run
  `meta.json`, not in the payload — without this the partial badge cannot distinguish cancel from
  timeout. `ScanProgressScreen` (DESIGN.md) already reads `metadata["terminated_by"]` to pick the
  badge reason; this addition makes the two specs consistent and the timeout AC observable at the
  scan level. The values reuse the existing `TerminatedBy` literal — no new terminal state.
- `ScanPayload.metadata` is `dict[str, str | int | float | bool] | None`
  (`normalize/contracts.py:57`) — `partial_result` / `interrupted_stage` ride in `metadata`.
  **No `ScanPayload` schema change.**
- `write_meta_json` uses `TerminatedBy` which already includes `"timeout"` and `"user_cancel"`
  (`workspace.py:12`). On a killed/timed-out step, `LoggedNmapRunner.run_xml` writes
  `terminated_by="timeout"`; on cancel-kill, `"user_cancel"`. **No new literal.**
- `on_complete` becomes the single finalization path, called with `partial_result=True` payloads on
  cancel / timeout / post-discovery fatal. `ScanProgressScreen` offers that payload instead of
  dismissing `None`.

### Cancellation contract

- `NmapRunner`/`LoggedNmapRunner` track live `Popen` handles in a lock-guarded set (new
  `_active_procs`, distinct from `_active_run_dirs`) and expose `terminate_active()` that
  `proc.kill()`s each (mirrors the existing `_run_lock` / `_active_run_dirs` pattern). `run_streamed`
  registers its `Popen` before `proc.wait()` and removes it in a `finally`.
- **Wiring gap closed:** today the runner is a **local** in `ScanRunner._run` (built by
  `build_runner`), unreachable from the UI thread. `_run` must stash it on `self._active_runner`
  (lock-guarded; set right after `build_runner`, cleared in `finally`). `ScanRunner.request_cancel()`
  then does `self._cancel_event.set()` **and**, if `self._active_runner` is set,
  `self._active_runner.terminate_active()`. Without this, "real cancellation" (F4/P3) cannot fire —
  setting the event alone never interrupts the blocking `proc.wait()`.
- `run_port_stage` / `run_deep_inspection_stage` gain a cancellation token (the existing
  `threading.Event`, passed as `cancel_event: threading.Event | None = None`) and check it inside the
  `as_completed` loop, ceasing to read further futures once set.

## New files and naming (mandatory)

| Layer | Path | Change |
|-------|------|--------|
| Errors (new) | `hardware-agent/src/agent/scanner/errors.py` | Define `ScanError` base + `FatalScanError`, `UnitScanError`, `TransientScanError`, `BudgetExceeded`, and `CircuitBreakerError(BudgetExceeded)`. |
| Errors re-export | `hardware-agent/src/agent/scanner/__init__.py` | Export the new taxonomy classes; remove the `NmapExecutionError` export. |
| Step exec | `hardware-agent/src/agent/scanner/nmap.py` | Add `timeout: float \| None = None` to `run_xml`/`run_streamed` (`subprocess.run(timeout=)` / `proc.wait(timeout=)`; on `TimeoutExpired` → `proc.kill()` + raise `BudgetExceeded`); track live `Popen` + `terminate_active()`; remove `NmapExecutionError` and raise taxonomy classes directly; `LoggedNmapRunner` writes `terminated_by="timeout"`/`"user_cancel"`. |
| Discovery (call site) | `hardware-agent/src/agent/discovery/network_discovery.py` | `discover_hosts` gains `timeout: float \| None = None` and forwards it to `runner.run_xml`. |
| Port scan (call site) | `hardware-agent/src/agent/discovery/port_discovery.py` | `scan_ports_batch` accepts/forwards the resolved `timeout` to its `run_xml` calls (pass1/pass2). |
| Deep/NSE (call site) | `hardware-agent/src/agent/discovery/vulnerability_detection.py` | `run_nse_vulnerability_scan` accepts/forwards the resolved `timeout` to `run_xml`. |
| Stage orchestration | `hardware-agent/src/agent/scanner/stages.py` | Per-unit try/except wrapper (isolation), transient retry-once, failure accounting + circuit breaker, in-loop cancel check; thread failed/skipped counts into `build_metadata` and into stage-done events. Add `cancel_event` param to both stage fns. Resolve `subprocess_timeout_for(settings.scan_mode, "ports"\|"nse")` and pass it into `scan_ports_batch` / `run_nse_vulnerability_scan`. |
| Workspace | `hardware-agent/src/agent/scanner/workspace.py` | No code change — `TerminatedBy` (L12) already covers `"timeout"`/`"user_cancel"`; confirm consumed. |
| Config | `hardware-agent/src/agent/config.py` | Add three fields to `AgentSettings`: `scan_deadline_s`, `unit_failure_threshold`, `transient_retries`. Add the `subprocess_timeout_for(scan_mode, stage)` resolver + `TIMEOUTS` mode×stage table (above), beside `min_cvss_for_mode`/`deep_stage_scripts`. |
| Progress events | `hardware-agent/src/agent/scanner/progress.py` | Optional: add `units_skipped` / `units_total` to `ScanEvent` for degraded `port_stage_done` / deep-stage-done (report §6). Display copy lives in DESIGN.md. |
| **TUI runner (call site)** | `hardware-agent/src/agent/tui/scanner.py` (`ScanRunner`) | Refactor `_run` so payload build + `on_complete` is reachable from cancel / timeout / post-discovery-fatal with `partial_result=True` + `interrupted_stage`; branch on the taxonomy per §4.2; pass `_cancel_event` into both stage fns; stash the built runner on `self._active_runner` (lock-guarded) so `request_cancel()` can call `self._active_runner.terminate_active()`. **AgentSettings is constructed inline here (L72-76) — every new `AgentSettings` knob is threaded through this construction.** Resolve `subprocess_timeout_for(self.scan_mode, "discovery")` and pass it to `discover_hosts`. Enforce `scan_deadline_s` between stages/units. |
| **TUI screen (call site)** | `hardware-agent/src/agent/tui/screens/scan_progress.py` (`ScanProgressScreen`) | `action_abort` on cancel must offer the finalized partial payload (`dismiss((partial, True))` semantics) instead of `dismiss(None)`; `_handle_error` distinguishes fatal (nothing to keep) from partial (offer "View partial"). Constructs `ScanRunner` (L115) — verify it threads any new `ScanRunner` constructor param. |
| TUI screen (call site) | `hardware-agent/src/agent/tui/screens/home.py` (L74) | Constructs `ScanProgressScreen(subnet, scan_mode)` — re-check if `ScanProgressScreen.__init__` gains a param. |

### CLAUDE.md integration rule (mandatory, do not mark complete until done)

The TUI bypasses any orchestrator and runs through `ScanRunner`, which builds its **own**
`AgentSettings` inline. Therefore:

- **Every new `AgentSettings` field** (`scan_deadline_s`, `unit_failure_threshold`,
  `transient_retries`) MUST flow into the inline `AgentSettings(...)` construction in
  `tui/scanner.py:72-76` so a TUI scan honours them exactly as a non-TUI scan (TRUTH AC "Config
  knobs honored from TUI"). With defaults on the dataclass this is automatic, but the implementer
  MUST confirm the inline construction does not shadow/override them. The per-call nmap timeout is
  **not** an `AgentSettings` field — it is resolved from `scan_mode` (already threaded everywhere) +
  the stage name via `subprocess_timeout_for`, so it needs no extra threading; just verify each
  pipeline call site (`discover_hosts`, `scan_ports_batch`, `run_nse_vulnerability_scan`) passes the
  resolved value.
- **Every new `ScanRunner` constructor parameter** MUST be threaded through `ScanProgressScreen`
  (`tui/screens/scan_progress.py:115`), and any new `ScanProgressScreen` parameter through
  `home.py:74`. Prefer NOT adding redundant `ScanRunner` knob params (simplicity) — let the knobs
  live on `AgentSettings`. If a TUI override is added, it MUST appear in both call sites.
- Before marking architecture/implementation complete, **grep every constructor and call site**:
  `ScanRunner(` → `scan_progress.py:115` + `tests/unit/test_scan_runner_events.py` +
  `test_scan_runner_timing.py`; `ScanProgressScreen(` → `home.py:74` +
  `tests/unit/test_scan_progress_screen.py:45`; `run_port_stage(` / `run_deep_inspection_stage(` →
  `tui/scanner.py:114,117` + `tests/unit/test_stage_reporter.py`. Verify each passes the new
  `cancel_event` / honours the new behaviour.

## Constraints

- No new infrastructure, daemon, or external tooling — all changes are in-process Python. No
  `HUMAN_INFRA_REQUIRED` flag.
- Reuse the existing `NmapRunner`/`LoggedNmapRunner`, the `ThreadPoolExecutor` loops, `merge_ports`,
  `build_metadata`, and the `TerminatedBy` literal. Do not invent a parallel scan path or new
  terminal states.
- Match the project **no-comments / no-docstrings** style in new code, including tests.
- Out of scope (TRUTH): backend ingest contract for partial payloads, mid-scan connectivity
  re-checks (F8) beyond breaker + timeouts, new scan modes / timing-profile changes.

### New ADR?

The contingency policy (stop-vs-continue, error taxonomy, circuit breaker) is a durable
architectural decision that extends ADR-004's methodology. Recorded in
**`docs/adr/ADR-010-scan-contingency-policy.md`** (approved at the planning gate) — §4.1 taxonomy
and §4.2 decision table. (ADR-005 was already taken by the security model; the new ADR is 010.)

## Testing expectations

New unit tests under `hardware-agent/tests/unit/`. Mirror existing patterns:
`test_nmap_streaming.py` (fake-nmap = `sys.executable` subprocess), `test_scan_runner_events.py`
(`_FakeRunner`/`_BoomRunner` + `_FakeReporter`), `test_stage_reporter.py` (stage fns with fake
runner). Assert behaviour, not snapshots.

| Area (phase) | Test file | What to assert | Mirror |
|--------------|-----------|----------------|--------|
| Step timeout (P1) | `test_nmap_timeout.py` | A slow fake-nmap (`-c "import time; time.sleep(5)"`) called via `run_xml(args, timeout=0.2)` is killed; `BudgetExceeded` raised; `LoggedNmapRunner` writes `terminated_by="timeout"`. Separately assert `subprocess_timeout_for(mode, stage)` returns the table values. | `test_nmap_streaming.py` |
| Per-unit isolation (P2) | `test_stage_isolation.py` | A runner failing one batch/host (`UnitScanError`) leaves other units' data intact; stage does not raise; failed ip/batch recorded. | `test_stage_reporter.py` |
| Transient retry (P4) | `test_stage_isolation.py` | `run_xml` raises `TransientScanError` on an allow-list stderr marker and `UnitScanError` otherwise; a unit raising `TransientScanError` once then succeeding is retried `transient_retries` times and its data kept; raising twice demotes to a unit failure; a `BudgetExceeded`/timeout unit is **not** retried. | `test_stage_reporter.py` |
| Circuit breaker (P4) | `test_circuit_breaker.py` | When failed/total exceeds `unit_failure_threshold`, the stage raises `CircuitBreakerError` and `ScanRunner` finalizes a partial with `terminated_by="error"`; below threshold it continues. `CircuitBreakerError` is caught by `except BudgetExceeded`. | `test_stage_reporter.py` |
| Partial finalization (P2) | `test_scan_runner_partial.py` | On cancel, timeout, and post-discovery fatal, `on_complete` receives a payload with `metadata["partial_result"] is True`, `metadata["interrupted_stage"]` set, and `metadata["terminated_by"]` in `{user_cancel, timeout, error}` matching the cause; fatal-before-discovery yields `on_error` and no payload; zero hosts still yields a valid non-partial empty result (`terminated_by="completed"`). | `test_scan_runner_events.py` |
| Real subprocess termination (P3) | `test_scan_runner_cancel.py` | `request_cancel()` calls `runner.terminate_active()` (spy/fake asserts kill invoked); in-loop cancel stops reading further futures; the cancel path finalizes a partial. | `test_scan_runner_events.py` (`TestScanRunnerAbort`) |
| Config knobs honored from TUI (P1–P4) | `test_scan_runner_partial.py` | The inline `AgentSettings` built by `ScanRunner._run` carries the new knob values (defaults applied); a TUI scan exercises the same timeout/threshold/retry behaviour. | `test_scan_runner_events.py` |
| Taxonomy (P4) | `test_scan_errors.py` | Subclass relationships: `BudgetExceeded`/`UnitScanError`/`FatalScanError`/`TransientScanError` subclass `ScanError`; `CircuitBreakerError` subclasses `BudgetExceeded`; `ScanCancelled` subclasses `ScanError`. | new, plain pytest |

Regression: existing `test_scan_runner_events.py` and `test_stage_reporter.py` must still pass —
`ScanCancelled` keeps its import location and stage fns keep their current positional signature
(new `cancel_event` is keyword-defaulted). `test_logged_runner.py:110` asserts on the now-removed
`NmapExecutionError`; that assertion is rewritten against the taxonomy (`UnitScanError` /
`BudgetExceeded`) — old tests are updated or replaced, not preserved by keeping the class.

## Phasing (report §8 — sequence tasks in this order)

1. **P1 — Stop the hangs:** per-call `timeout` on `run_xml`/`run_streamed` + kill on expiry +
   `BudgetExceeded` + `terminated_by="timeout"`; add the `subprocess_timeout_for` mode×stage resolver
   and thread the resolved value through the discovery/stage call sites. (F1)
2. **P2 — Stop losing everything:** per-unit isolation in both stage loops + partial-result
   finalization in `ScanRunner._run` / `ScanProgressScreen`. (F2, F3)
3. **P3 — Honest cancellation:** live `Popen` tracking + `terminate_active()` + in-loop cancel
   checks; `request_cancel` kills subprocesses. (F4)
4. **P4 — Policy polish:** `scanner/errors.py` taxonomy, transient retry-once, circuit breaker,
   `scan_deadline_s` wall-clock budget. (F5, F6, F7)

P1+P2 alone resolve the bulk of the reported long-scan crashes/hangs.
