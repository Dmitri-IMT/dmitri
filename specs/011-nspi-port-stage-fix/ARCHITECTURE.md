# ARCHITECTURE — Fix NSPi mode port stage (Stage 2)

## System context

Pipeline: discovery → **port scan** → NSE/deep inspection → normalization (`ScanPayload`) →
TUI / persistence. This feature is a repair of the **port-scan stage for `scan_mode="nspi"`**
plus three cross-cutting supports it depends on (progress, cancellation, log retention) and one
metadata correction. It is a single-layer change under `hardware-agent/src/agent/`.

Modules touched:

- `discovery/port_discovery.py` — `_scan_ports_batch_nspi` (the two-pass NSPi scan) — **completion fix**.
- `scanner/nmap.py` — `NmapRunner` / `LoggedNmapRunner` — **cancel-before-spawn guard**.
- `scanner/stages.py` — `nmap_arguments_summary` tells the truth for NSPi — **metadata fix**.
- `scanner/workspace.py` — `prune_logs` groups by scan and protects the last failed/partial run — **retention fix**.
- `scanner/errors.py` — `ScanCancelled` error the guard raises.
- `tui/screens/scan_progress.py` — port-stage **elapsed-time heartbeat** + responsive cancelling banner (see DESIGN.md) — **progress + cancel UX**.

Two scan drivers exist. Headless `ScanOrchestrator.run()` (legacy/dead per MEMORY) and the TUI's
`ScanRunner` (`tui/scanner.py`), which bypasses the orchestrator and calls the stages directly.
All production NSPi scans run through `ScanRunner` → `stages.run_port_stage`. Per the CLAUDE.md
integration rule, `ScanRunner` and `ScanProgressScreen` are listed in the naming table and were
checked: this feature adds **no new orchestrator/runner parameter and no new reporter event**, so
neither call site needs a new argument threaded (verified below). The port-stage progress fix is
entirely screen-side (an elapsed-time heartbeat), driven by the existing `port_stage_started` /
`port_batch_done` events already on the reporter contract.

## Design decisions

### 1. Completion fix — split the timing template between the two passes

Root cause (Stage 1, DMI-50): `_scan_ports_batch_nspi` runs two sequential nmap invocations, and
each is handed the same per-invocation timeout `subprocess_timeout_for("nspi", "ports") = 600.0`.
Pass 1 is a **polite `-T2` full top-1000 `-sV -O` sweep** across up to `host_batch_size = 8` IPs.
`-T2` forces `max_parallelism=1` + a 0.4 s scan delay, so pass 1's SYN floor alone (~400 s for a
single host, several × for an 8-host batch) exceeds the 600 s budget before `-sV`/`-O` — it can
never finish. Every batch hits `BudgetExceeded`, all hosts are skipped, and the circuit breaker
(threshold 0.5) then aborts the whole stage. Pass 2 (7 OT ports) is trivial.

**Decision (refine-specs, operator — chosen after explicitly weighing polite-but-slow
alternatives):** run **pass 1 (the broad top-1000 sweep) at `-T4`** and keep **pass 2 (the OT
ports) at polite `-T2`**.

**On PLC safety — the honest justification.** Pass 1 at `-T4` *does* sweep every host's top-1000,
PLCs included, at full rate — it is **not** the case that "pass 1 avoids the PLCs". `-T4` is
accepted here because (a) **Quick mode already runs exactly this** `-T4` top-1000 `-sV -O` sweep
against these same PLCs — it did so on the real NSPi network on 2026-07-03 with no reported device
harm (`docs/tests/nspi-september/results.md`) — so NSPi pass 1 is no more aggressive than the scan
the pilot already runs there; and (b) DMI-50 validates **in dev only**, no NSPi field retest, pilot
stays on Quick. Polite `-T2` is retained on pass 2, the OT-specific ports
(502/4840/44818/445/139/3389/5985) where ICS services actually live, so the OT-service probes stay
gentle. The alternatives — keep `-T2` everywhere and either raise the budget / shrink batches
(≈20–45 min scans) or trim to a known-port set — were considered and **rejected by the operator** in
favour of a fast, complete scan.

Concrete change in `_scan_ports_batch_nspi`:

| Pass | Before | After | Rationale |
|------|--------|-------|-----------|
| 1 (broad top-1000) | `-Pn -T2 -n -sV -O <ips>` | `-Pn -T4 -n -sV -O <ips>` | == Quick's proven port-stage timing, already run against these PLCs (see PLC-safety note) |
| 2 (OT ports) | `-Pn -T2 -n -p <NSPI_PORTS> -sV <ips>` | **unchanged** | polite `-T2` retained on the OT-service probes |

`-n` (skip DNS — the NSPi lab has no resolver) stays on both passes.

**004 contract drift:** `specs/004-nspi-scan-mode/contracts/nspi-constants.md` documents "Timing &
flags = `-T2 -n`" for the whole NSPi port stage. That is now only true of pass 2; pass 1 is `-T4 -n`.
Update that note when implementing so the contract matches (this spec supersedes it for pass 1).

**Budget:** `TIMEOUTS["ports"]["nspi"]` **stays 600.0 — no config change.** Justification: after
the fix pass 1 is timing-identical to Quick's port stage (`-T4`, top-1000, `-sV -O`, batch of 8),
which already fits and passes under the same 600 s per-invocation budget (Quick pass 1 additionally
runs `--script vulners`, so NSPi pass 1 is *lighter*). Pass 2's `-T2` math is tiny: 7 ports ×
0.4 s ≈ 2.8 s SYN per host, ~22 s for an 8-host batch plus `-sV`, far inside its own 600 s. Each
pass gets its own 600 s subprocess timeout, so no combined-budget accounting is needed. This keeps
the change surgical and leaves Quick/Standard/Extensive/MAX budgets untouched. Deriving a smaller
`-T2`-math budget was considered and rejected: pass 1 is no longer `-T2`, so that math no longer
applies, and reducing the number would only add risk with no benefit.

### 2. Progress fix — screen-side elapsed-time heartbeat (no pipeline change)

Today the port stage emits only `port_stage_started`, then one `port_batch_done` per batch. With
a batch of 8 the first batch event is minutes away, and the screen's active "Scanning ports…" line
only cycles a spinner glyph with no substantive change — the multi-minute silent gap (spinner
animating, "zero new information") that Stage 1 identified and TRUTH forbids.

A pipeline-side `port_progress` heartbeat sourced from nmap's `--stats-every` output was designed
and **rejected** (refine-specs, operator decision): the port stage runs up to `max_workers = 4`
batches concurrently through one shared `LoggedNmapRunner`, so a single progress sink would
interleave the per-invocation percentages of several live nmap processes (and reset each pass),
producing a number that jumps and runs backwards — incoherent next to a `batch N/M` count, and
costing a new event kind, a new `ScanEvent` field, an nmap stdout parser, and a runner sink.

**Decision:** close the gap entirely on the TUI side with a monotonic **elapsed-time heartbeat**,
and make **no pipeline change**. `ScanProgressScreen` records a timestamp when it receives
`port_stage_started` and, on its existing `_tick` interval (already repainting spinner glyphs),
appends a live `mm:ss`/`Nm Ss` elapsed counter to the active `ports` line, e.g.
`⠙ Scanning ports… (batch 3/8 · 1m20s)`. The timer increments every tick (~1 s) — far more often
than once per host-batch, with no silent gap — is always increasing (coherent, race-free), and
needs no `ScanEvent`, no `progress.py` change, no nmap parsing, and no runner sink. The coarse
`(batch N/M)` structure still comes from `port_batch_done`, which remains the **only** event that
advances `#progress-bar`. Rendering details (copy, widget ids, reset-per-batch behaviour) are
owned by DESIGN.md / `ScanProgressScreen`.

This keeps `scanner/progress.py`, `scanner/nmap.py` (except the cancel guard, decision 3), and
`scanner/stages.py` (except the metadata fix, decision 5) untouched — the smallest change that
satisfies TRUTH's "updates arrive more than once per host-batch, no multi-minute silent gap".

### 3. Cancellation fix — check `_cancelled` before spawning a new subprocess

`request_cancel()` → `runner.terminate_active()` kills only the subprocesses registered at that
instant and sets `_cancelled`, but nothing checks `_cancelled` before launching the **next** nmap.
A batch thread sitting between pass 1 and pass 2 (or in a transient-retry loop) starts a fresh
600 s nmap after cancellation, and the port stage's `ThreadPoolExecutor.__exit__` →
`shutdown(wait=True)` then blocks the worker for up to 600 s (the source of the "frozen while
cancelling" symptom on the worker side).

**Decision:** add a cancel-before-spawn guard. At the top of `NmapRunner.run_xml`,
`NmapRunner.run_streamed`, and `LoggedNmapRunner.run_xml` (before any run folder or subprocess is
created), `if self._cancelled: raise ScanCancelled(...)`.

**`ScanCancelled` — reuse, do not duplicate.** A `class ScanCancelled(ScanError)` **already exists**
at `tui/scanner.py:29` and is caught by `ScanRunner` at line 317. Do **not** define a second one:
`scanner/nmap.py` must not import from `tui` (layering — `scanner` is below `tui`). **Relocate** the
single `ScanCancelled(ScanError)` into `scanner/errors.py` and have `tui/scanner.py` import it from
there (add to its existing `from agent.scanner.errors import (...)` block, delete the local class).
One class, correct layering, no name collision, and the guard raises exactly the type `ScanRunner`
already handles.

No stage-loop change is required, and this rests on a **cancellation ordering invariant** that must
be preserved: `ScanRunner.request_cancel()` sets `self._cancel_event` (`scanner.py:63`) **before**
calling `runner.terminate_active()` (`:67`), which is what sets `runner._cancelled`. So by the time
the guard can raise `ScanCancelled`, `cancel_event` is already set, and `run_port_stage`'s
`as_completed` loop — which `break`s at the top of each iteration when `cancel_event.is_set()` —
never calls `.result()` on a future holding `ScanCancelled`. The exception is simply abandoned in an
unretrieved future; the guard's only job is to make in-flight batch threads finish fast so
`ThreadPoolExecutor.shutdown(wait=True)` returns promptly. **Do not reorder `request_cancel()`** (set
`_cancel_event` first) or the loop could `.result()` an uncaught `ScanCancelled`. `_run_unit_with_retry`
catches only `TransientScanError`, so `ScanCancelled` is **not** retried (no re-spawn, no retry sleep)
and does **not** count toward the circuit-breaker failure ratio. `ScanRunner`'s existing
`_check_cancel()` at the stage boundary still raises `ScanCancelled` →
`_finalize_partial(terminated_by="user_cancel")`, so the partial result is saved with the correct
terminal state. (The TUI-thread input-lockout during "cancelling" is DESIGN.md's concern; this doc
covers the runner/worker side. Coordinate: the guard is what makes the worker unblock quickly.)

### 4. Retention fix — group by scan, protect the last failed/partial run

`prune_logs(logs_dir, max_count=10)` keeps a flat global FIFO of 10 run **folders** sorted by name,
run in the `finally` of every `run_xml`. One Quick scan writes ~11+ folders, so it deterministically
evicts a prior failed NSPi run's folders — the evidence is gone.

**Decision:** rewrite `prune_logs` to count **scans, not folders**, and never evict the most recent
failed/partial scan:

- Read each run folder's `meta.json` (already written by `write_meta_json`) for `parent_scan_id`
  and `terminated_by`. Folders lacking a `parent_scan_id` (legacy) are treated as singleton groups.
- Group folders by `parent_scan_id`; order groups by newest folder name (time-sortable).
- Keep the newest `max_scans` groups (default `10`); delete all folders of older groups.
- **Always retain the most recent group containing a failed/partial run** (any folder with
  `terminated_by` in `{"timeout", "error", "user_cancel"}`), even if it falls outside the newest-N
  window.
- `protected` (in-flight run dirs) is still never deleted — unchanged.
- **Robustness (this runs in a `finally`):** a missing or malformed `meta.json` (a folder mid-write,
  a partial/empty JSON, or a concurrent sibling that has not yet written meta) must be treated as an
  ungrouped singleton, and `prune_logs` must **never raise** — it executes in the `finally` of every
  `run_xml`, so an exception here would mask the run's real result/exception. Wrap each per-folder
  meta read in `try/except` and skip-on-failure. Folder basenames are timestamp-prefixed local
  wall-clock (`make_run_folder_name`), so name-sort ≈ time-sort for group ordering.

Signature becomes `prune_logs(logs_dir, max_scans=10, *, protected=frozenset())`. Sole production
caller is `LoggedNmapRunner.run_xml` (`prune_logs(self.logs_dir, protected=protected)`), which is
unaffected by the rename. `prune_results` is out of scope (unchanged).

### 5. Metadata fix — honest `nmap_arguments_summary` for NSPi

`nmap_arguments_summary` builds the `ports=` clause from `discovery_arguments("nspi")`, which
returns `-sV -O --script <NSPI scripts>` and then appends `-Pn -T4` — reporting scripts and `-T4`
that the NSPi batch path (`_scan_ports_batch_nspi`) never runs. `discovery_arguments("nspi")` is
only reached here for NSPi (the batch path branches to `_scan_ports_batch_nspi` before it, and the
single-host `scan_ports` is not used by the stages), so the fix is local to the summary.

**Decision:** special-case NSPi in `nmap_arguments_summary` to describe the two passes it actually
runs, e.g.:

```
ports=pass1:-Pn -T4 -n -sV -O (top-1000); pass2:-Pn -T2 -n -p 502,4840,44818,445,139,3389,5985 -sV
```

Other modes' `ports=` clause is unchanged.

## Data model / contracts

- **`_scan_ports_batch_nspi` pass 1 args:** `-T2` → `-T4` (pass 2 unchanged). No signature change.
- **`config.py`:** no change. `TIMEOUTS["ports"]["nspi"]` stays `600.0`; all other modes untouched.
- **`scanner/progress.py`:** **no change** — no new event kind, no new `ScanEvent` field. The
  progress fix is screen-side (decision 2) and reuses the existing `port_stage_started` /
  `port_batch_done` events.
- **`scanner/errors.py`:** new `class ScanCancelled(ScanError)`.
- **`scanner/nmap.py`:** cancel-before-spawn guard raising `ScanCancelled` in
  `run_xml`/`run_streamed`/`LoggedNmapRunner.run_xml` (decision 3). No progress sink / stats
  callback / stream hook.
- **`scanner/workspace.py`:** `prune_logs(logs_dir, max_scans=10, *, protected=frozenset())` with
  per-scan grouping semantics.
- **`tui/screens/scan_progress.py`:** renders an elapsed-time heartbeat on the active `ports` line
  and the cancelling banner (DESIGN.md). No new event consumed; no constructor change.
- **`ScanPayload` / `PortInfo` / normalize contracts:** unchanged. `terminated_by` values reused
  (`"timeout"`, `"user_cancel"`, `"error"`, `"completed"`) — no new terminal states, per ADR-010.

## New files and naming (mandatory)

No new files. All edits are to existing modules under `hardware-agent/src/agent/`.

| Layer | Path | Responsibility of the change |
|-------|------|------------------------------|
| Discovery | `hardware-agent/src/agent/discovery/port_discovery.py` | **Completion fix**: `_scan_ports_batch_nspi` pass 1 `-T2`→`-T4`; pass 2 unchanged (polite `-T2`) |
| Config | `hardware-agent/src/agent/config.py` | **No change** — anchor: `TIMEOUTS["ports"]["nspi"]` stays 600.0; other modes untouched |
| Progress contract | `hardware-agent/src/agent/scanner/progress.py` | **No change** — no new event kind or field; progress fix is screen-side |
| Errors | `hardware-agent/src/agent/scanner/errors.py` | **Relocate** `ScanCancelled(ScanError)` here (moved from `tui/scanner.py`) so the nmap guard and `ScanRunner` share one class |
| Nmap runner | `hardware-agent/src/agent/scanner/nmap.py` | Cancel-before-spawn guard raising `ScanCancelled` in `run_xml`/`run_streamed`/`LoggedNmapRunner.run_xml` (before any run folder or subprocess is created) |
| Stages | `hardware-agent/src/agent/scanner/stages.py` | `nmap_arguments_summary` honest for NSPi (metadata fix only) |
| Workspace | `hardware-agent/src/agent/scanner/workspace.py` | `prune_logs` per-scan grouping, count scans, protect last failed/partial |
| TUI runner | `hardware-agent/src/agent/tui/scanner.py` (`ScanRunner`) | Import `ScanCancelled` from `scanner/errors.py` and delete the local class (decision 3). **No orchestrator/runner parameter or reporter-event change** — nothing to thread per CLAUDE.md |
| TUI screen | `hardware-agent/src/agent/tui/screens/scan_progress.py` (`ScanProgressScreen`) | **Progress fix (screen-side)**: elapsed-time heartbeat on the active `ports` line via the existing `_tick`; responsive cancelling banner (DESIGN.md). Constructs `ScanRunner` (line 131) — **no new arg to pass** |

### CLAUDE.md integration-rule verification

Grepped every constructor/call site of the changed classes:

- **`ScanRunner(...)`** — production: `tui/screens/scan_progress.py:131` only (plus tests). Its
  signature and the `reporter=self._ScreenReporter(self)` it passes are **unchanged**; no new
  parameter, no new event flows through it.
- **`ScanProgressScreen(...)`** — production: `tui/screens/home.py:74`
  (`ScanProgressScreen(subnet=subnet, scan_mode=mode)`) only (plus tests). Its signature is
  unchanged; the elapsed-time heartbeat is rendered from data it already has (`port_stage_started`
  / `port_batch_done` via the existing `ProgressUpdated` message path) plus a local timestamp.

Conclusion: this feature adds **no** orchestrator/runner parameter, budget, or reporter-event
change. The cancel guard (decision 3) is internal to the nmap runner. Both TUI call sites are
therefore already correct with nothing to thread — the CLAUDE.md integration rule is satisfied
vacuously, and is recorded here so the orchestrator does not re-open it.

## Constraints

- No new infrastructure — no new hardware, daemon, external tool, or nmap script. **No
  `HUMAN_INFRA_REQUIRED`.**
- Reuse the existing `NmapRunner`/`LoggedNmapRunner` and `merge_ports` — do not add a parallel scan
  path. The two-pass NSPi structure and `merge_ports` dedup stay as-is.
- Do **not** alter Quick / Standard / Extensive / MAX timing, port scope, budgets, or outputs
  (TRUTH business rule + acceptance "Other modes untouched"). The completion fix touches only the
  `scan_mode == "nspi"` branch; the metadata fix only the NSPi `ports=` clause; the retention and
  cancellation fixes are mode-agnostic but change only when-logs-are-evicted / when-to-stop-spawning,
  not any mode's scan behaviour.
- No new terminal states — reuse ADR-010's `terminated_by` values and `partial_result` /
  `interrupted_stage` fields.

## Testing expectations

Add unit tests under `hardware-agent/tests/unit/`, mirroring the named existing test. Run
`uv run pytest` and `uv run ruff check` (from `hardware-agent/`); no comments/docstrings in tests.

| Acceptance criterion (TRUTH) | Test | Mirror / notes |
|------------------------------|------|----------------|
| NSPi completes; OT politeness preserved | `test_nspi_two_pass_merge.py` (extend) | Existing `test_both_passes_use_t2_and_n` must change: assert **pass 1 uses `-T4`** (not `-T2`) and **pass 2 still uses `-T2`**; keep merge/dedup assertions |
| Budget fits runtime | `test_config_timeouts.py` (extend) | Assert `TIMEOUTS["ports"]["nspi"] == 600.0` unchanged; document that pass 1 now matches Quick's fitting timing (assert `subprocess_timeout_for("nspi","ports") == subprocess_timeout_for("quick","ports")`) |
| Other modes untouched | `test_config_timeouts.py`, `test_nmap_arguments_summary.py` | Assert quick/standard/extensive/max `ports=` clauses and budgets are byte-for-byte unchanged |
| Sub-batch progress (no silent gap) | extend `hardware-agent/tests/unit/test_scan_progress_screen.py` | Drive `ScanProgressScreen`: send `port_stage_started`, advance the `_tick` clock past a threshold with **no** `port_batch_done`, assert the active `ports` line's text changed (elapsed counter advanced) — proving updates arrive more than once per batch with no new pipeline event. Also assert `#progress-bar` did **not** move on those ticks (only `port_batch_done` advances it) |
| Responsive cancel | new `test_cancel_before_spawn.py` | Mirror `test_scan_runner_cancel.py`: set `runner._cancelled`, assert `run_xml`/`run_streamed` raise `ScanCancelled` before any subprocess/run folder is created; assert no `logs/` dir is written |
| Logs survive next scan | `test_workspace.py` (extend `TestPruneLogs`) | Build folders across two `parent_scan_id`s with a failed run (`terminated_by="error"`), then simulate a later completed scan's folders; assert the failed scan's folders survive and pruning counts **scans**, not folders |
| Honest metadata | `test_nmap_arguments_summary.py` (add) | Assert NSPi summary contains `pass1:-Pn -T4` and `pass2:-Pn -T2 -n -p 502,4840,44818,445,139,3389,5985 -sV`, and does **not** contain `--script` |
| Suites green | full run | `uv run pytest` + `uv run ruff check` pass |
