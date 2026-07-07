# TASKS — Fix NSPi mode port stage (Stage 2)

Execution checklist for spec 011. Derived from `ARCHITECTURE.md` (decisions 1–5 + the
`ScanCancelled` relocation decision 3 depends on) and `DESIGN.md` (S4 progress + cancel UX).
Driven by the feature-orchestrator: each task runs agent-developer → test-engineer →
code-reviewer, and is only `COMPLETED` on a reviewer `[APPROVE]`.

## Dependency graph

```
Task 1 (completion fix)      — independent
Task 2 (relocate ScanCancelled) — independent
Task 3 (cancel-before-spawn guard) — depends on Task 2
Task 4 (retention fix)       — independent
Task 5 (metadata fix)        — independent
Task 6 (S4 progress + cancel UX) — depends on Task 3 (responsive-cancel pair)
```

## Status table

| Task | Name | Status | Review Rejections |
|------|------|--------|-------------------|
| 1 | Completion fix — pass 1 `-T4` | COMPLETED | 0 |
| 2 | Relocate `ScanCancelled` to `scanner/errors.py` | COMPLETED | 1 |
| 3 | Cancel-before-spawn guard in nmap runner | COMPLETED | 0 |
| 4 | Retention fix — `prune_logs` per-scan grouping | COMPLETED | 1 |
| 5 | Metadata fix — honest NSPi `nmap_arguments_summary` | COMPLETED | 0 |
| 6 | S4 elapsed-time heartbeat + responsive cancelling | COMPLETED | 0 |

---

## Task 1: Completion fix — NSPi pass 1 runs at `-T4`
- **Description**: In `_scan_ports_batch_nspi`, change pass 1 (the broad top-1000 `-sV -O` sweep)
  from `-T2` to `-T4`; leave pass 2 (the OT-ports `-p <NSPI_PORTS> -sV` probe) at polite `-T2`.
  Keep `-n` on both passes and the existing two-pass + `merge_ports` structure. Update the 004
  contract note (`specs/004-nspi-scan-mode/contracts/nspi-constants.md`) so "Timing & flags" reads
  `-T4 -n` for pass 1 / `-T2 -n` for pass 2 (this spec supersedes it for pass 1). No config/budget
  change. See ARCHITECTURE.md decision 1.
- **Dependencies**: —
- **Target Files**: [`hardware-agent/src/agent/discovery/port_discovery.py`,
  `specs/004-nspi-scan-mode/contracts/nspi-constants.md`]
- **Success Criteria**: pass 1 nmap args contain `-T4` (not `-T2`) and still `-n`, `-sV`, `-O`,
  top-1000; pass 2 args unchanged (`-T2 -n -p <NSPI_PORTS> -sV`); no other mode's branch touched;
  `merge_ports` dedup behaviour unchanged; 004 contract note updated.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Relocate `ScanCancelled` into `scanner/errors.py`
- **Description**: Move the single `class ScanCancelled(ScanError)` from `tui/scanner.py:29` into
  `scanner/errors.py`, and change `tui/scanner.py` to import it from there (add to its existing
  `from agent.scanner.errors import (...)` block; delete the local class). This corrects layering
  (`scanner` must not depend on `tui`) so the nmap guard (Task 3) and `ScanRunner` share one class.
  No behaviour change; `ScanRunner`'s existing catch at `scanner.py:317` and `_check_cancel` still
  work against the same type. See ARCHITECTURE.md decision 3 ("reuse, do not duplicate").
- **Dependencies**: —
- **Target Files**: [`hardware-agent/src/agent/scanner/errors.py`,
  `hardware-agent/src/agent/tui/scanner.py`]
- **Success Criteria**: exactly one `ScanCancelled(ScanError)` exists, defined in
  `scanner/errors.py`; `tui/scanner.py` imports it from `agent.scanner.errors` and no longer defines
  it locally; no other definition remains; existing cancel tests still pass.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 3: Cancel-before-spawn guard in the nmap runner
- **Description**: Add `if self._cancelled: raise ScanCancelled(...)` at the top of
  `NmapRunner.run_xml`, `NmapRunner.run_streamed`, and `LoggedNmapRunner.run_xml` — **before** any
  run folder or subprocess is created. Import `ScanCancelled` from `scanner/errors.py` (Task 2). Do
  not add any progress sink / stats callback / stream hook. Do not reorder
  `ScanRunner.request_cancel()` (it must keep setting `_cancel_event` before `terminate_active()`);
  the guard only makes in-flight batch threads finish fast so `shutdown(wait=True)` returns
  promptly. See ARCHITECTURE.md decision 3.
- **Dependencies**: Task 2
- **Target Files**: [`hardware-agent/src/agent/scanner/nmap.py`]
- **Success Criteria**: when `runner._cancelled` is set, `run_xml`/`run_streamed`/
  `LoggedNmapRunner.run_xml` raise `ScanCancelled` before any subprocess spawns and before any
  `logs/` run folder is written; when not cancelled, behaviour is unchanged; `ScanCancelled` is not
  caught by `_run_unit_with_retry` (not a `TransientScanError`), so no re-spawn/retry.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: Retention fix — `prune_logs` groups by scan
- **Description**: Rewrite `prune_logs` in `scanner/workspace.py` to count scans, not folders, and
  protect the most recent failed/partial run. New signature
  `prune_logs(logs_dir, max_scans=10, *, protected=frozenset())`. Read each run folder's `meta.json`
  for `parent_scan_id` / `terminated_by`; group by `parent_scan_id` (legacy folders lacking it =
  singleton groups); order groups by newest folder name; keep newest `max_scans` groups; delete
  older; **always retain** the most recent group containing any folder with `terminated_by ∈
  {"timeout","error","user_cancel"}` even if outside the window; never delete `protected` dirs. Must
  **never raise** (runs in a `finally`): wrap each per-folder meta read in try/except, skip on
  failure, treat missing/malformed meta as an ungrouped singleton. Sole production caller
  `LoggedNmapRunner.run_xml` (`prune_logs(self.logs_dir, protected=protected)`) is unaffected by the
  rename. `prune_results` out of scope. See ARCHITECTURE.md decision 4.
- **Dependencies**: —
- **Target Files**: [`hardware-agent/src/agent/scanner/workspace.py`]
- **Success Criteria**: signature is `prune_logs(logs_dir, max_scans=10, *,
  protected=frozenset())`; grouping counts scans by `parent_scan_id`; a failed/partial scan's
  folders survive a later unrelated completed scan that exceeds the window; malformed/missing
  `meta.json` never raises and is treated as a singleton; `protected` dirs never deleted;
  `prune_results` untouched.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 5: Metadata fix — honest `nmap_arguments_summary` for NSPi
- **Description**: Special-case `scan_mode == "nspi"` in `nmap_arguments_summary`
  (`scanner/stages.py`) so the `ports=` clause describes the two passes actually run, e.g.
  `pass1:-Pn -T4 -n -sV -O (top-1000); pass2:-Pn -T2 -n -p 502,4840,44818,445,139,3389,5985 -sV`.
  Must NOT contain `--script` for NSPi. Every other mode's `ports=` clause is byte-for-byte
  unchanged. See ARCHITECTURE.md decision 5.
- **Dependencies**: —
- **Target Files**: [`hardware-agent/src/agent/scanner/stages.py`]
- **Success Criteria**: NSPi `ports=` clause contains `pass1:-Pn -T4` and
  `pass2:-Pn -T2 -n -p 502,4840,44818,445,139,3389,5985 -sV` and does not contain `--script`;
  quick/standard/extensive/max `ports=` clauses unchanged.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6: S4 elapsed-time heartbeat + responsive cancelling banner
- **Description**: In `tui/screens/scan_progress.py` (only): (a) on `port_stage_started` record
  `self._port_stage_started_at = monotonic()` and store the mode-aware base label; have the `_tick`
  path (`_refresh_active_stage_lines`) append a live `{m}m {s}s` (or `{s}s` < 60s) elapsed counter
  to the active `ports` line; add a `port_batch_done` branch to
  `on_scan_progress_screen_progress_updated` for the coarse `(batch N/M)` structure — the bar
  advances **only** on `port_batch_done`, never on a tick; (b) extend `_enter_cancelling` to show
  `#scan-badge` with `[black on yellow] CANCELLING [/] saving partial results…` and write the new
  activity line `[yellow]● Stopping scan — saving partial results, no new probes will start…[/yellow]`,
  leaving `_active_stages` populated so the spinner keeps animating; a second `ctrl+x` stays an
  idempotent no-op. No new event, field, id, binding, or CSS. See DESIGN.md changes 1 & 2 and
  ARCHITECTURE.md decision 2.
- **Dependencies**: Task 3
- **Target Files**: [`hardware-agent/src/agent/tui/screens/scan_progress.py`]
- **Success Criteria**: after `port_stage_started` + several `_tick`s with no `port_batch_done`,
  the active `ports` line's elapsed counter advances and `#progress-bar.progress` is unchanged;
  after `port_batch_done` the line contains `batch N/M` and the bar advanced; on cancel `#scan-badge`
  `display is True` and its text contains `CANCELLING` and `saving partial results…`, the activity
  log shows the new stopping line, and the spinner keeps animating; no new pipeline event/field/id/
  binding added; `ScanRunner` (`scan_progress.py:131`) and `ScanProgressScreen` (`home.py:74`)
  signatures unchanged.
- **Status**: COMPLETED
- **Review Rejections**: 0
