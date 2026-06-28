# POOP — Execution ledger (spec 010 Scan Pipeline Resilience)

Append-only ledger. Every coder, test-engineer, and reviewer appends one section before
returning. The orchestrator appends only `STRUCTURAL_REEVAL` blocks. Each entry: Order Given /
What, How & Why / Decisions Made / Code Changed (or Reviewed) — file paths only, no snippets.

---

## Task 1: Error taxonomy module — coder (agent-developer)

**Order Given**: Create `scanner/errors.py` with `ScanError(Exception)` base and subclasses
`FatalScanError`, `UnitScanError`, `TransientScanError`, `BudgetExceeded`, and
`CircuitBreakerError(BudgetExceeded)`. Export the new classes from `scanner/__init__.py` and
remove the `NmapExecutionError` re-export (class stays in `nmap.py`). Re-parent `ScanCancelled`
in `tui/scanner.py` to subclass `ScanError`, changing only its base class.

**What, How & Why**: Added the new `errors.py` module with the five-class hierarchy per
ARCHITECTURE §4.1 — `FatalScanError`/`UnitScanError`/`TransientScanError`/`BudgetExceeded` all
subclass `ScanError`; `CircuitBreakerError` subclasses `BudgetExceeded` so the planned
`except BudgetExceeded` branch in `ScanRunner` catches it without a new handler. Rewrote
`scanner/__init__.py` to import and export the six taxonomy classes plus `NmapRunner`, dropping
`NmapExecutionError` from both the import and `__all__`. In `tui/scanner.py` added
`from agent.scanner.errors import ScanError` and changed `ScanCancelled`'s base from `Exception`
to `ScanError`, leaving its name, location, and docstring untouched.

**Decisions Made**:
- `NmapExecutionError` definition left untouched in `nmap.py` (Task 4 removes it); only the
  package re-export surface was dropped, per task instruction.
- Kept the bodies as bare `pass` with no comments/docstrings to follow project no-comments style.
- Used package-relative imports (`from .errors import ...`) matching the existing
  `from .nmap import ...` style in `__init__.py`.

**Grep check**: `NmapExecutionError` appears in `scanner/nmap.py` (definition + raises, untouched)
and `tests/unit/test_logged_runner.py` (imports it directly from `agent.scanner.nmap`, NOT from
the package). No live importer used `from agent.scanner import NmapExecutionError`, so removing the
re-export breaks nothing. Verified import + subclass relationships and ruff pass.

**Code Changed**:
- created: `hardware-agent/src/agent/scanner/errors.py`
- modified: `hardware-agent/src/agent/scanner/__init__.py`
- modified: `hardware-agent/src/agent/tui/scanner.py`

---

## Task 1: Error taxonomy module — test-engineer

**Order Given**: Add pytest tests for Task 1. Create
`hardware-agent/tests/unit/test_scan_errors.py` mirroring existing unit-test style. Assert:
`FatalScanError`/`UnitScanError`/`TransientScanError`/`BudgetExceeded` subclass `ScanError`
(and `Exception`); `CircuitBreakerError` subclasses `BudgetExceeded` (caught by
`except BudgetExceeded`); `ScanCancelled` (from `tui/scanner.py`) subclasses `ScanError`; the
taxonomy is importable from the `agent.scanner` package; `NmapExecutionError` is no longer
exported from the package. Behavioural assertions, no comments/docstrings, run scoped pytest
green.

**What, How & Why**: Wrote `test_scan_errors.py` covering subclass relationships for the four
direct `ScanError` children; `CircuitBreakerError` → `BudgetExceeded` → `ScanError` lineage
proven by both `issubclass` and a raise-and-catch under `pytest.raises(BudgetExceeded)`;
`ScanCancelled` lineage proven by `issubclass` and raise-and-catch under
`pytest.raises(ScanError)`; package re-export verified by object identity
(`getattr(scanner, name) is cls`); removed re-export verified with
`not hasattr(scanner, "NmapExecutionError")`. Used catch semantics over snapshots because the
pipeline relies on `except BudgetExceeded`/`except ScanError` branches catching the subclasses.

**Decisions Made**:
- No mocking — pure class/identity assertions, no boundary to stub.
- Imported the taxonomy from the `agent.scanner` package (not `agent.scanner.errors`) to
  exercise the re-export surface, matching neighbouring tests' import style.
- Asserted only the package-level removal of `NmapExecutionError` per the order; did not assert
  against `agent.scanner.nmap`, which still defines it.
- Module docstring only, no in-body comments/docstrings (project no-comments style).

**Code Changed**:
- created: `hardware-agent/tests/unit/test_scan_errors.py`

---

## Task 1: Error taxonomy module — code-reviewer (gate)

**Order Given**: Authoritative review gate for Task 1. Verify the `ScanError` taxonomy, the
package re-export change (remove `NmapExecutionError`), the `ScanCancelled` re-parent in
`tui/scanner.py`, and the new `test_scan_errors.py` against Task 1 Success Criteria and
ARCHITECTURE §4.1 / "New files and naming" / Testing "Taxonomy" row. Run `uv run pytest` on the
relevant tests and `uv run ruff check` on changed files. Append a POOP entry. First line
APPROVE/REJECT.

**What, How & Why**: Read TASKS.md (Task 1) and ARCHITECTURE.md (§4.1, naming table, testing
expectations), then the four changed artifacts. Ran `uv run pytest tests/unit/test_scan_errors.py
tests/unit/test_logged_runner.py` → 22 passed. Ran `uv run ruff check` on the four changed files →
one error: I001 (un-sorted import block) in `tests/unit/test_scan_errors.py`. `ruff check --diff`
confirmed the fix removes the blank line between `import pytest` and the `agent.*` first-party
imports. Ran ruff against sibling test files (`test_scan_runner_events.py`, `test_stage_reporter.py`,
`test_logged_runner.py`) — all pass, confirming the new file diverges from the established
convention rather than the repo lacking the rule. Grepped `NmapExecutionError`: remaining
references are `nmap.py` (definition intact, removed by Task 4) and `test_logged_runner.py` which
imports from `agent.scanner.nmap` (not the package re-export), so no live importer was broken. Git
diff confirmed `tui/scanner.py` changed only the `ScanCancelled` base class plus the required
import — no collateral edits.

**Decisions Made**: REJECT. Functional criteria are all met (subclass graph, re-export removal,
surgical re-parent, tests green). The sole blocker is the required `uv run ruff check` gate failing
on the new test file (I001). Per the review contract the ruff gate must pass; a one-line
import-formatting fix is needed before COMPLETED.

**Code Reviewed**:
- `hardware-agent/src/agent/scanner/errors.py`
- `hardware-agent/src/agent/scanner/__init__.py`
- `hardware-agent/src/agent/tui/scanner.py`
- `hardware-agent/tests/unit/test_scan_errors.py`
- `hardware-agent/tests/unit/test_logged_runner.py` (regression check only)

---

## Test Engineer — Ruff I001 Fix (Task 1)

**Order Given**: Code review REJECTED Task 1 for a ruff `I001` failure in
`hardware-agent/tests/unit/test_scan_errors.py`. Apply the import-grouping fix only (no assertion
changes), confirm `uv run ruff check` is clean, confirm
`uv run pytest tests/unit/test_scan_errors.py` still passes.

**What, How, and Why**: Ran `uv run ruff check --fix tests/unit/test_scan_errors.py`, which removed
the blank line between `import pytest` and the first-party `from agent.scanner import (...)` block
so `pytest` and the `agent.*` imports sit in one contiguous group, matching sibling files
(`test_scan_runner_events.py`, `test_stage_reporter.py`, `test_logged_runner.py`). No assertions
touched.

**Decisions Made**: Used ruff autofix rather than a manual edit to guarantee the result matches
ruff's own expected grouping.

**Code Changed**: `hardware-agent/tests/unit/test_scan_errors.py`

**Results**: `uv run ruff check` → All checks passed. `uv run pytest tests/unit/test_scan_errors.py`
→ 10 passed.

---

## Task 1: Error taxonomy module — re-review after I001 fix (code-reviewer)

**Order Given**: Re-review Task 1 after a fix. Prior rejection was solely a ruff `I001`
import-grouping failure in `tests/unit/test_scan_errors.py` (blank line removed between
`import pytest` and the `from agent.scanner import (...)` block to match sibling test files).
Confirm the fix and re-run the gate: `uv run ruff check` clean, `uv run pytest
tests/unit/test_scan_errors.py` passing.

**What, How, and Why**: Re-read `errors.py`, `__init__.py`, `tui/scanner.py`, and
`test_scan_errors.py` to confirm the functional taxonomy was unchanged and the import-grouping
fix is in place (no blank line at test lines 5-6). Ran `uv run ruff check` on the four scoped
files → All checks passed. Ran `uv run pytest tests/unit/test_scan_errors.py` → 10 passed in
0.34s. Re-confirmed against the Task 1 rubric: `FatalScanError`/`UnitScanError`/
`TransientScanError`/`BudgetExceeded` subclass `ScanError`; `CircuitBreakerError` subclasses
`BudgetExceeded`; `ScanCancelled` (tui/scanner.py) subclasses `ScanError`; `NmapExecutionError`
absent from `scanner/__init__.py` re-exports; `errors.py` carries no comments/docstrings.

**Decisions Made**: APPROVE. Both gates green; every Success Criterion met; no collateral edits.
This is a foundation task with no orchestrator/runner parameter, so the CLAUDE.md threading rule
does not apply.

**Code Reviewed**:
- hardware-agent/src/agent/scanner/errors.py
- hardware-agent/src/agent/scanner/__init__.py
- hardware-agent/src/agent/tui/scanner.py
- hardware-agent/tests/unit/test_scan_errors.py

---

## Task 2: Config knobs + per-call timeout resolver — coder (agent-developer)

**Order Given**: Add three flat scalar fields to the `@dataclass(slots=True)` `AgentSettings` in
`config.py` (`scan_deadline_s: int = 0`, `unit_failure_threshold: float = 0.5`,
`transient_retries: int = 1`), plus a module-level `TIMEOUTS` mode×stage table and a
`subprocess_timeout_for(scan_mode: str, stage: str) -> float` resolver beside
`min_cvss_for_mode`/`deep_stage_scripts`, using the exact ARCHITECTURE table values.

**What, How & Why**: Added the three fields after `version_intensity` in `AgentSettings` with the
documented defaults, keeping `slots=True` valid (all defaulted, so existing keyword-only
construction sites are unaffected). Added a `TIMEOUTS` nested dict keyed `stage -> mode -> float`
holding the exact values from the ARCHITECTURE "Per-call subprocess timeout" table, and a
`subprocess_timeout_for` resolver immediately after `min_cvss_for_mode`. Mirrored the existing
mode-keyed helper convention of returning a safe fallback for an unknown mode/stage rather than
raising.

**Decisions Made**: Stored timeouts as floats directly in the table (resolver returns table value
unchanged, satisfying the `-> float` contract). Stage keys are `"discovery"`, `"ports"`, `"nse"`
(callers pass these). Unknown stage falls back to the `discovery` row; unknown mode falls back to
the `quick` column, mirroring `min_cvss_for_mode`'s constant-default convention. Confirmed all
`AgentSettings(` call sites pass keyword-only args, so the new defaulted fields shift nothing.

**Code Changed**:
- modified: `hardware-agent/src/agent/config.py`

---

## Task 2: Config knobs + per-call timeout resolver — test-engineer

**Order Given**: Add pytest tests for Task 2's `config.py` changes: assert `subprocess_timeout_for(mode, stage)` returns the exact documented float for all 15 (mode ∈ {quick,standard,extensive,nspi,max}) × (stage ∈ {discovery,ports,nse}) pairs via `pytest.mark.parametrize`, and assert the three new `AgentSettings` fields exist with their documented defaults (`scan_deadline_s == 0`, `unit_failure_threshold == 0.5`, `transient_retries == 1`). No comments/docstrings in test bodies; ruff clean.

**What, How & Why**: Created `tests/unit/test_config_timeouts.py` mirroring the sibling `test_scan_mode_scripts.py` layout (module docstring, `from __future__`, contiguous first-party `agent.config` import group, class-grouped tests). `TestSubprocessTimeoutFor` parametrizes the full 15-pair matrix from the ARCHITECTURE "Per-call subprocess timeout" table, asserting both the exact value and `isinstance(result, float)` so the `-> float` contract is behaviourally verified, not just numeric equality. `TestResilienceConfigDefaults` constructs a default `AgentSettings()` (same construction style as existing tests) and asserts each of the three new knob defaults independently.

**Decisions Made**: No mocking needed — the resolver and dataclass defaults are pure, so tests call them directly. Chose explicit value-per-pair tuples over deriving from the production `TIMEOUTS` table so the test is an independent oracle against the ARCHITECTURE doc rather than a tautology mirroring the source. Did not test unknown-mode/unknown-stage fallback paths since they were not in the Success Criteria scope (the criteria fix the 15 documented pairs); left as a noted gap if a reviewer wants fallback coverage.

**Code Changed**:
- created: `hardware-agent/tests/unit/test_config_timeouts.py`

---

## Task 2: Config knobs + per-call timeout resolver — reviewer (code-reviewer)

**Order Given**: Authoritative review gate for Task 2. Verify the three new `AgentSettings`
fields (`scan_deadline_s=0`, `unit_failure_threshold=0.5`, `transient_retries=1`), the `TIMEOUTS`
mode×stage table, and `subprocess_timeout_for(scan_mode, stage) -> float` against the
ARCHITECTURE "Per-call subprocess timeout" table; confirm no broken construction sites,
no-comments style, pytest + ruff green. Approve or reject.

**What, How & Why**: Read TASKS.md Task 2 and ARCHITECTURE §"Config knobs" + "Per-call subprocess
timeout" tables, then `config.py` and `test_config_timeouts.py`. Cross-checked every (mode×stage)
value in `TIMEOUTS`/resolver against the authoritative table: discovery uniformly 600; ports
600/900/1800/600/3600; nse 900/1200/2400/1200/3600 — all match and all returned as float.
Confirmed the three fields exist with documented defaults on the `slots=True` dataclass and that
every `AgentSettings(` construction site (scanner.py:73, load_settings, tests) uses keyword/no
args with the new defaulted fields appended last, so none break. Ran
`uv run pytest tests/unit/test_config_timeouts.py` → 18 passed; `uv run ruff check` on both
changed files → All checks passed. Resolver sits beside `min_cvss_for_mode`/`deep_stage_scripts`
with a sane fallback (unknown stage → discovery row, unknown mode → quick column). The test
module docstring is consistent with the codebase (15 of 21 unit test files carry one, including
the Task 1 sibling test_scan_errors.py).

**Decisions Made**: APPROVE. Every success criterion met; values exact; no construction-site
regressions; gates green.

**Code Reviewed**: hardware-agent/src/agent/config.py;
hardware-agent/tests/unit/test_config_timeouts.py; hardware-agent/src/agent/tui/scanner.py (inline
AgentSettings construction, verify only).

---

## Task 3 — ScanEvent skip-accounting fields (coder)

**Order Given** — Add two optional fields (`units_skipped`, `units_total`) to `ScanEvent` in
`scanner/progress.py` for degraded `port_stage_done` / deep-stage-done events, as the last fields
with defaults so existing positional constructions keep working. Do not touch emission logic,
reporters, or other files (Task 6 populates them).

**What, How & Why** — Appended `units_skipped: int = 0` and `units_total: int = 0` to the
`ScanEvent` frozen/slots dataclass after `ip`. Matched the existing field-default style (`int = 0`)
so absent/zero reads as a clean finish line per DESIGN.md item 1. Placed last to keep every
existing construction site (scanner.py, stages.py, tests) unaffected. No emission/reporter changes.

**Decisions Made** — Chose `int = 0` over `int | None = None` to mirror the existing counter fields
(`hosts_done`, `batches_total`, `ports_open`) so the dataclass stays homogeneous and "0 ⇒ clean"
holds without None-handling downstream.

**Code Changed** — modified: hardware-agent/src/agent/scanner/progress.py

---

## Task 3: ScanEvent skip-accounting fields — test-engineer

**Order Given** — Add a focused pytest test for the two new optional `ScanEvent` fields
(`units_skipped`, `units_total`) in `scanner/progress.py`: default-constructed event has both == 0;
keyword args are accepted and stored; existing-style construction without the new fields still works
(backward-compatible). Mirror existing `ScanEvent(` test style under `tests/unit/`.

**What, How & Why** — Added `tests/unit/test_scan_event_fields.py` with three behaviors: (1) a
minimal `ScanEvent(kind="port_stage_done")` exposes `units_skipped == 0` and `units_total == 0`;
(2) `ScanEvent(kind=..., units_skipped=2, units_total=5)` stores both; (3) a parametrized regression
over four existing-style constructions (hosts_found, port_batch_done, host_inspected, completed)
asserts each still constructs and applies the new defaults. Behavior assertions, no snapshots,
proving the additive change is backward-compatible per the Task 3 Success Criteria.

**Decisions Made** — New file rather than extending `test_progress_mapper.py`, since that suite is
scoped to mapper/weight math while these tests target the dataclass contract directly. Mirrored the
sibling import grouping (contiguous `pytest` + `agent.scanner.progress`, no module docstring). No
mocking needed — the dataclass is pure. Trimmed the `host_inspected` case to stay under the 88-col
ruff limit instead of adding a `noqa` comment (no-comments preference).

**Code Changed** — created: hardware-agent/tests/unit/test_scan_event_fields.py

---

## Task 3 — Code Review (code-reviewer) — [APPROVE]

**Order Given** — Authoritative review gate for Task 3 (ScanEvent skip-accounting fields). Verify
`ScanEvent` accepts `units_skipped`/`units_total` with safe defaults appended last; existing
construction unchanged; no emission logic changed; no-comments style. Run scoped pytest and ruff.

**What, How & Why** — Reviewed the two-line addition to `ScanEvent` (`units_skipped: int = 0`,
`units_total: int = 0` appended as the last two fields) and the new unit test. Grepped every
`ScanEvent(` call site across hardware-agent: all use keyword args and none set the new fields, so
appended-last optional defaults cannot break positional or keyword construction. Confirmed no
emission/reporter code changed (only the dataclass body widened). Confirmed no comments/docstrings
in changed files. Ran `uv run pytest tests/unit/ -k "progress or scan_runner or stage or event" -q`
→ 130 passed, 199 deselected. Ran `uv run ruff check` on both changed files → All checks passed.
Cross-checked ARCHITECTURE.md §190 and DESIGN "Reporter contract" item 1 (skip count + total on
stage-done; zero/absent ⇒ clean finish) — the int=0 defaults satisfy the absent/zero semantics.

**Decisions Made** — APPROVE. Every success criterion met: fields optional with safe defaults,
appended last, existing construction intact, no semantic change, tests green, ruff clean. No
integration-rule exposure (no orchestrator/runner parameter added by this shape-widening task).

**Code Reviewed** — hardware-agent/src/agent/scanner/progress.py;
hardware-agent/tests/unit/test_scan_event_fields.py

---

## Task 4 — nmap.py timeout, taxonomy raising, Popen tracking (agent-developer)

**Order Given** — Implement Task 4 in `hardware-agent/src/agent/scanner/nmap.py` only: add
`timeout: float | None = None` to `NmapRunner.run_xml`/`run_streamed` (TimeoutExpired → kill +
`BudgetExceeded`); remove `NmapExecutionError` and raise taxonomy classes (nmap-not-found →
`FatalScanError`; non-zero exit / bad XML → `UnitScanError`; matched-transient stderr →
`TransientScanError`; timeout → `BudgetExceeded`); add a lock-guarded `_active_procs` set +
`terminate_active()`; `run_streamed` registers/deregisters its `Popen`; `LoggedNmapRunner` writes
`terminated_by="timeout"` on timeout and `"user_cancel"` on cancel-kill. No comments/docstrings.

**What, How, and Why** — Imported the taxonomy from `agent.scanner.errors`. Added module constant
`TRANSIENT_STDERR_MARKERS = ("temporary failure in name resolution", "connection reset")` and helper
`_classify_nonzero(stderr) -> ScanError` returning `TransientScanError` only on a marker match, else
`UnitScanError`. `_resolve_nmap_path` now raises `FatalScanError`. `NmapRunner.__init__` gained
`_proc_lock` (dedicated lock mirroring `_run_lock`), `_active_procs: set[subprocess.Popen]`, and a
`_cancelled` flag. `run_xml` passes `timeout` to `subprocess.run` (TimeoutExpired → `BudgetExceeded`,
FileNotFoundError → `FatalScanError`), classifies non-zero exit via `_classify_nonzero`, and raises
`UnitScanError` on bad XML. `run_streamed` passes `timeout` to `proc.wait`; on TimeoutExpired it
`proc.kill()`s, joins reader threads, and raises `BudgetExceeded`; it registers the `Popen` in
`_active_procs` before `wait` and discards it in a `finally`. `terminate_active()` sets `_cancelled`
and `proc.kill()`s every tracked proc. `LoggedNmapRunner.run_xml` accepts `timeout`, wraps
`run_streamed` so a `BudgetExceeded` writes `meta.json` with `terminated_by="timeout"`
(`exit_code=None`) then re-raises; on a non-zero exit it picks `"user_cancel"` when `_cancelled` else
`"error"`, writes meta, then raises via `_classify_nonzero`/`UnitScanError`. `timeout=None`
preserves the exact prior no-timeout blocking behaviour for non-pipeline callers (`service_detection`).

**Decisions Made** — Dedicated `_proc_lock` rather than reusing `_run_lock` (Popen tracking lives on
the base `NmapRunner`, while `_run_lock`/`_active_run_dirs` are `LoggedNmapRunner`-only). Cancel vs
timeout distinguished by source: a timeout surfaces as `BudgetExceeded` from `run_streamed`; an
external `terminate_active()` kill returns a non-zero exit with `_cancelled` set. Transient
classification reused in both `run_xml` and `LoggedNmapRunner.run_xml` for consistency. Kept the
existing `TerminatedBy` literal — no new value. Verified manually that both `run_xml` and
`run_streamed` raise `BudgetExceeded` under a short timeout and that `terminate_active()` kills a
live streamed proc.

**Code Changed** — hardware-agent/src/agent/scanner/nmap.py (modified)

---

## Task 4: nmap.py timeout, taxonomy raising, Popen tracking — test-engineer

**Order Given**: (A) Create `tests/unit/test_nmap_timeout.py` mirroring `test_nmap_streaming.py`:
slow fake-nmap via `run_xml`/`run_streamed` with a short timeout is killed and raises
`BudgetExceeded`; `LoggedNmapRunner.run_xml` writes `terminated_by="timeout"` to `meta.json`;
`timeout=None` still completes; where feasible, non-zero exit → `UnitScanError`, nmap-not-found →
`FatalScanError`, transient stderr marker → `TransientScanError`. (B) Fix
`tests/unit/test_logged_runner.py` to drop the removed `NmapExecutionError` import/assertion and
use the taxonomy (`UnitScanError`).

**What, How & Why**: Mirrored the `sys.executable`-as-fake-nmap technique. Timeout paths use a
5s sleep script with `timeout=0.2` so the kill happens fast. `BudgetExceeded`, `FatalScanError`,
`TransientScanError`, `UnitScanError` imported from `agent.scanner.errors`. Taxonomy raising is
driven entirely through the subprocess fake: non-zero exit (`SystemExit(2)`), invalid stdout (bad
XML), bogus `nmap_path` (FileNotFoundError → `FatalScanError`), stderr containing `connection
reset` (transient marker → `TransientScanError`) vs other stderr (stays `UnitScanError`).
`terminate_active()` covered by running `run_streamed` on a sleeper in a worker thread, polling
`_active_procs` until registered, then killing and asserting `_cancelled`/empty `_active_procs`;
plus a no-proc no-op case. `LoggedNmapRunner` timeout meta read back through the workspace logs
dir exactly as `test_logged_runner.py` inspects `meta.json`.

**Decisions Made**: Mock boundary is the real subprocess (no mock of the runner) — the fake nmap
is the Python interpreter, matching the sibling test. All four taxonomy paths were feasible via
the fake, so none were skipped. Regression: Task 4's production change added `_proc_lock` /
`_active_procs` / `_cancelled`, used inside `run_streamed`; the existing `__new__`-based helpers
in `test_nmap_streaming.py` and `test_logged_runner.py` bypass `__init__` and broke with
`AttributeError`. Updated both helpers to seed those three attributes (test-only change, required
by the production change; no production code touched). Fixed the `NmapExecutionError` import +
`pytest.raises` in `test_logged_runner.py` to `UnitScanError`. The class-relationship coverage of
the taxonomy stays in `test_scan_errors.py` (untouched, still asserts `NmapExecutionError`
absence).

**Code Changed**: `hardware-agent/tests/unit/test_nmap_timeout.py` (new),
`hardware-agent/tests/unit/test_logged_runner.py`, `hardware-agent/tests/unit/test_nmap_streaming.py`.

---

## Review — Task 4 (nmap.py timeout, taxonomy raising, Popen tracking) — code-reviewer

**Order Given**: Authoritative review gate for Task 4 (spec 010). Verify timeout params on
run_xml/run_streamed with kill-on-timeout + BudgetExceeded; taxonomy raised at correct sites;
NmapExecutionError removed; lock-guarded _active_procs distinct from _active_run_dirs;
terminate_active() + Popen register/deregister; LoggedNmapRunner terminated_by="timeout"/"user_cancel";
workspace.py untouched; no-comments style. Run pytest + ruff gates.

**What, How & Why**: Reviewed nmap.py against TASKS.md Task 4 success criteria and ARCHITECTURE
§4.1 taxonomy / "Transient detection" / "Cancellation contract". Confirmed: run_xml uses
subprocess.run(timeout=) (kills child internally on TimeoutExpired) → BudgetExceeded; run_streamed
uses proc.wait(timeout=) with explicit proc.kill()+wait()+thread-join → BudgetExceeded; timeout=None
preserves old behaviour and all discovery callers (incl. service_detection) call run_xml without
timeout. Taxonomy: not-found→FatalScanError, non-zero/bad-XML→UnitScanError, transient marker
(allow-list only)→TransientScanError, timeout→BudgetExceeded (never transient). _active_procs is
lock-guarded (NmapRunner) and distinct from _active_run_dirs (LoggedNmapRunner); kill() happens
outside the lock — no deadlock; Popen registered before wait, discarded in finally (no leak on
timeout/cancel). LoggedNmapRunner writes terminated_by="timeout" on BudgetExceeded and "user_cancel"
via the _cancelled branch. Judgement call on __new__ test helpers: real instances are always built
via __init__ (NmapRunner.__init__ sets _proc_lock/_active_procs/_cancelled; LoggedNmapRunner calls
super().__init__()), so the seeded attrs are a pure test-harness artifact, not production fragility.
Gates: `uv run pytest tests/unit/test_nmap_timeout.py tests/unit/test_logged_runner.py
tests/unit/test_nmap_streaming.py` → 38 passed; broader `-k "nmap or logged or streaming or service"`
→ 51 passed; `uv run ruff check` on the 4 changed files → clean; grep NmapExecutionError → zero live
references (only a negative assertion in test_scan_errors.py). workspace.py confirmed unmodified in
the Task 4 working tree.

**Decisions Made**: APPROVE. Every success criterion met; gates green. New production code carries no
comments/docstrings; the new test file's single module docstring mirrors every sibling test file
(consistent existing style). The run_xml kill-on-timeout test asserts via subprocess.run's documented
internal kill (process not registered in _active_procs), which is acceptable.

**Code Reviewed**: `hardware-agent/src/agent/scanner/nmap.py`,
`hardware-agent/src/agent/scanner/errors.py`,
`hardware-agent/tests/unit/test_nmap_timeout.py`,
`hardware-agent/tests/unit/test_logged_runner.py`,
`hardware-agent/tests/unit/test_nmap_streaming.py`,
`hardware-agent/src/agent/discovery/service_detection.py`.

---

## Task 5: Thread resolved timeout through discovery call sites — coder (agent-developer)

**Order Given**: Add `timeout: float | None = None` to `discover_hosts` (`network_discovery.py`),
`scan_ports_batch` (`port_discovery.py`, forwarding to both pass1/pass2 `run_xml`), and
`run_nse_vulnerability_scan` (`vulnerability_detection.py`), each forwarding to its
`runner.run_xml(...)`. Leave `service_detection` unchanged (keeps `timeout=None`). Default `None`
preserves existing behaviour. No comments. Only the three discovery files.

**What, How & Why**: Added a keyword-defaulted `timeout` parameter to each of the three discovery
functions and forwarded it into every `runner.run_xml(...)` call. For `scan_ports_batch` this
meant forwarding into the non-nspi single `run_xml`, into the `_scan_ports_batch_nspi` helper
(which gained the same defaulted param), and into both the pass1 and pass2 `run_xml` calls inside
that helper. Placed the param last (after `scan_mode` for `scan_ports_batch`/`discover_hosts`,
after the keyword-only group for `run_nse_vulnerability_scan`) so existing positional callers in
`stages.py` and `tui/scanner.py` are unaffected. Task 4 already added `timeout` to
`NmapRunner.run_xml`, so `timeout=None` is a no-op against the real runner.

**Decisions Made**:
- `_scan_ports_batch_nspi` also takes `timeout: float | None = None` (positional-default,
  matching its existing non-keyword-only style) so both nspi passes receive the value.
- Did not touch `service_detection.py` per spec — it keeps calling `run_xml` with no timeout.
- The 27 currently-failing unit tests are all stale test doubles (fake `run_xml`/`_capture`
  stubs in `test_stage_reporter.py`, `test_quick_mode_argv.py`, `test_nspi_two_pass_merge.py`,
  `test_scan_runner_events.py`) that do not yet accept the `timeout` kwarg introduced in Task 4.
  Production positional call sites do not break. Updating those fakes is the test-engineer's
  scope; per the task constraint I edited only the three source files. `uv run ruff check` on the
  three files is clean.

**Code Changed**:
- Modified: `hardware-agent/src/agent/discovery/network_discovery.py`
- Modified: `hardware-agent/src/agent/discovery/port_discovery.py`
- Modified: `hardware-agent/src/agent/discovery/vulnerability_detection.py`

---

## Task 5: Thread resolved timeout through discovery call sites — test-engineer

**Order Given**: (A) Fix stale test doubles whose fake `run_xml`/`_run_xml`/`_capture` stubs do
not accept the new `timeout` kwarg now forwarded by `discover_hosts`, `scan_ports_batch`, and
`run_nse_vulnerability_scan`. (B) Add forwarding coverage asserting each of the three discovery
functions forwards the `timeout` value it receives into `run_xml` (explicit value and default
`None`), covering the non-nspi and nspi `scan_ports_batch` paths. Full unit suite green; ruff
clean on changed test files.

**What, How & Why**: Added `timeout: float | None = None` (keyword-defaulted) to every fake
runner stub that stands in for `NmapRunner.run_xml`, mirroring the real signature so the
discovery functions can pass `timeout=` without raising `TypeError`. Added a new spy-runner test
module that records the `timeout` kwarg per call and asserts: `discover_hosts(spy, subnet,
timeout=12.0)` → `[12.0]`; `scan_ports_batch(... "standard", timeout=34.0)` → `[34.0]`; nspi
two-pass → `[34.0, 34.0]`; `run_nse_vulnerability_scan(..., timeout=56.0)` → `[56.0]`; each with
a default-omitted counterpart asserting `[None]`. Behavior assertions on the recorded kwarg, no
snapshots.

**Decisions Made**: Mock boundary is the `NmapRunner.run_xml` seam — the same boundary the
sibling discovery tests already use. The real-runner tests (`test_logged_runner.py`,
`test_nmap_streaming.py`, `test_nmap_timeout.py`) were left untouched: they exercise the genuine
`NmapRunner.run_xml`, which already accepts `timeout` from Task 4. `scan_ports` (single-host) was
not exercised for forwarding because production deliberately does not forward a timeout there;
only the three batch/forwarding functions were covered. No production code changed.

**Code Changed**:
- Modified: `hardware-agent/tests/unit/test_stage_reporter.py`
- Modified: `hardware-agent/tests/unit/test_quick_mode_argv.py`
- Modified: `hardware-agent/tests/unit/test_nspi_two_pass_merge.py`
- Modified: `hardware-agent/tests/unit/test_scan_runner_events.py`
- Modified: `hardware-agent/tests/unit/test_scan_runner_timing.py`
- Added: `hardware-agent/tests/unit/test_discovery_timeout_forwarding.py`

---

## Reviewer — Task 5: Thread resolved timeout through discovery call sites — [APPROVE]

- **Order Given**: Authoritative review gate for Task 5 (spec 010). Verify the three discovery
  functions accept `timeout` and forward it to every `run_xml` call; default `None` preserves
  prior behaviour; `service_detection` untouched; test-double fixes minimal; run full unit suite
  + ruff on changed files.
- **What, How & Why**:
  - Read TASKS.md Task 5 and inspected the three production files plus the new spy test and the
    five stub-updated tests via `git diff`.
  - `discover_hosts(runner, subnet, timeout=None)` forwards into its single `run_xml`.
    `scan_ports_batch(..., timeout=None)` forwards into the standard `run_xml` and delegates to
    `_scan_ports_batch_nspi(..., timeout=timeout)`, which forwards into BOTH pass1 and pass2
    `run_xml` calls. `run_nse_vulnerability_scan(..., *, ..., timeout=None)` forwards into its
    `run_xml`. All match `NmapRunner.run_xml(arguments, timeout=None)`.
  - Confirmed `service_detection.py` is NOT in the working tree changes and still calls
    `run_xml(arguments)` with no timeout.
  - Stub diffs add only `timeout: float | None = None` to fake `run_xml`/`_capture` signatures;
    no assertions or production logic smuggled in.
  - Gate: `uv run pytest tests/unit/ -q` -> 352 passed. `uv run ruff check` on all changed
    files -> All checks passed.
- **Decisions Made**: APPROVE. Every success criterion met; new keyword-defaulted params do not
  break positional callers (full suite green); changes are surgical and match Target Files;
  no-comments style respected (new test module docstring matches existing repo test convention).
- **Code Reviewed**:
  - hardware-agent/src/agent/discovery/network_discovery.py
  - hardware-agent/src/agent/discovery/port_discovery.py
  - hardware-agent/src/agent/discovery/vulnerability_detection.py
  - hardware-agent/src/agent/discovery/service_detection.py (confirmed untouched)
  - hardware-agent/tests/unit/test_discovery_timeout_forwarding.py
  - hardware-agent/tests/unit/test_stage_reporter.py
  - hardware-agent/tests/unit/test_quick_mode_argv.py
  - hardware-agent/tests/unit/test_nspi_two_pass_merge.py
  - hardware-agent/tests/unit/test_scan_runner_events.py
  - hardware-agent/tests/unit/test_scan_runner_timing.py

## Task 6 — stages.py isolation, accounting, cancel check, timeout wiring

**Order Given**
Implement Task 6: per-unit isolation/accounting, cooperative cancel check, and
subprocess timeout wiring in `scanner/stages.py`, plus new event kinds and
`target_pct` mapping in `scanner/progress.py`. Add `cancel_event` keyword param
to both stage fns, `terminated_by` to `build_metadata`. Keep all existing
callers/tests green (CLAUDE.md integration rule for `tui/scanner.py`).

**What, How, and Why**
- progress.py: added `deep_stage_done`, `unit_timed_out`, `unit_failed` to the
  `ScanEventKind` Literal. Chose two distinct unit kinds over one `unit_skipped`
  + `reason` field (no schema change, lets the screen map kind→template).
  `target_pct` now returns `d + p + i` for `deep_stage_done` (grouped with
  `normalize_started`); the unit kinds fall through to the existing `return None`
  so they never advance the bar.
- stages.py: both stages now take `cancel_event: threading.Event | None = None`
  as a keyword-defaulted last param (positional signatures preserved). Inside the
  `as_completed` loop a top-of-iteration cancel check `break`s without raising.
  `future.result()` is wrapped in a tight `try/except/else`: `BudgetExceeded` →
  timeout skip, `UnitScanError` → failed skip; both record the skip count, emit a
  per-ip `unit_timed_out`/`unit_failed` event, and continue. Result application
  lives in the `else` so the try scope cannot swallow control flow.
  `CircuitBreakerError` (a `BudgetExceeded` subclass) is explicitly re-raised
  first so it propagates for Task 7 instead of being mis-handled as a timeout.
  Port-stage units are batches (skip increments by `len(batch)`, one event per
  ip); deep-stage units are hosts (skip increments by 1).
- Timeout wiring: executor submissions pass
  `timeout=subprocess_timeout_for(settings.scan_mode, "ports"|"nse")`.
- `port_stage_done` now carries `units_skipped`/`units_total=len(hosts)`; deep
  stage emits a new terminal `deep_stage_done` carrying
  `units_skipped`/`units_total=hosts_total`.
- `build_metadata` gained keyword-only `terminated_by: str | None = None`, stored
  verbatim as `metadata["terminated_by"]` when provided.

**Decisions Made**
- Two unit event kinds instead of one kind + reason field.
- `try/except/else` with result application in `else` to keep the catch scope
  tight (per spec "keep the try scope tight").
- Re-raise `CircuitBreakerError` before catching `BudgetExceeded` to honor "let
  the breaker propagate for now" despite the subclass relationship.
- Still increment progress (`port_batch_done` / `host_inspected`) and advance the
  bar on skipped units so the bar does not stall.

**Code Changed**
- Modified: hardware-agent/src/agent/scanner/stages.py
- Modified: hardware-agent/src/agent/scanner/progress.py

---

## Task 6: stages.py isolation, accounting, cancel check, timeout wiring — test-engineer

**Order Given**: Add pytest tests in `hardware-agent/tests/unit/test_stage_isolation.py` for Task 6:
per-unit isolation in `run_port_stage`/`run_deep_inspection_stage` (`UnitScanError` → skip "failed",
`BudgetExceeded` → skip "timeout", stage continues, other units' data intact, per-unit skip events,
`units_skipped`/`units_total` on the stage-done events), in-loop cancel check, resolved
`subprocess_timeout_for` wiring into the discovery fns, and `build_metadata(..., terminated_by=...)`.
Mirror `test_stage_reporter.py`. No comments/docstrings. Full unit suite + ruff must be green.

**What, How & Why**: Wrote behavioural tests covering all six success criteria. Deep-stage and
port-stage isolation are asserted by mutating the in-place `HostInfo` list and checking succeeding
hosts keep merged data (`host_scripts` set / ports populated) while the failing unit is untouched,
the stage never raises, and the matching `unit_failed`/`unit_timed_out` events carry the right ip.
`deep_stage_done`/`port_stage_done` skip accounting asserted (`units_skipped`/`units_total`,
host-counted; port batch failure skips every ip in the batch). Cancel asserted with a pre-set
`threading.Event` → zero futures processed (deterministic), no raise, for both stages. Timeout
wiring asserted by a spy fake capturing the `timeout` kwarg and comparing to
`subprocess_timeout_for(scan_mode, "ports"|"nse")` for `extensive`. `build_metadata` asserts the key
is present when `terminated_by` given and absent when omitted. Added an extra `target_pct` check
(skip kinds → None, `deep_stage_done` → d+p+i).

**Decisions Made**: Mocking boundary = monkeypatch `agent.scanner.stages.scan_ports_batch` and
`agent.scanner.stages.run_nse_vulnerability_scan` (the module-level names the stage fns call), rather
than a fake `run_xml` runner, because it lets each unit raise a precise taxonomy class and lets the
spy capture the resolved `timeout`. Used a minimal `_DummyRunner` (only `nmap_path`); `set_runner_stage`
no-ops since it isn't a `LoggedNmapRunner`. Cancel test uses a pre-set event for determinism (avoids
racing `as_completed` ordering) — asserts processed < total. No production code changed; existing
`test_stage_reporter.py` fakes already carry `timeout=None` defaults, so no sibling tweak needed.

**Code Changed**: `hardware-agent/tests/unit/test_stage_isolation.py` (new).

---

## Reviewer — Task 6 (stages.py isolation, accounting, cancel check, timeout wiring)

**Order Given**: Authoritative review gate for Task 6 (spec 010). Verify per-unit isolation,
CircuitBreakerError propagation, in-loop cancel check, timeout wiring, stage-done skip accounting +
per-unit skip events, `build_metadata(terminated_by=...)`, and `target_pct` for the new kinds.
Run `uv run pytest tests/unit/ -q` and `uv run ruff check` on changed files; confirm existing call
sites/tests still construct. First line `[APPROVE]`/`[REJECT]`.

**What, How & Why**: Read TASKS.md (Task 6), ARCHITECTURE.md (decision-table wiring, partial-result
and cancellation contracts), DESIGN.md (reporter contract items 1 & 2), then the changed sources
`scanner/stages.py`, `scanner/progress.py`, and the new `tests/unit/test_stage_isolation.py`.
Verified each success criterion by reading code: both stage loops catch `CircuitBreakerError` (re-raise)
BEFORE `except BudgetExceeded`/`UnitScanError`, so the breaker subclass propagates for Task 7 while
timeouts/failures skip+continue via the `else`-only data write; `cancel_event is not None and
.is_set()` breaks the `as_completed` loop with a None-default no-op and keyword-defaulted signature;
`subprocess_timeout_for(scan_mode,"ports"|"nse")` is passed into `scan_ports_batch`/
`run_nse_vulnerability_scan`; `port_stage_done`/`deep_stage_done` carry host-counted
`units_skipped`/`units_total`; `unit_timed_out`/`unit_failed` carry `ip`; `target_pct` maps
`deep_stage_done`→d+p+i and skip kinds→None with no existing mapping changed; `build_metadata`
stores `terminated_by` only when provided and leaves `partial_result`/`interrupted_stage` intact.
Grepped all `run_port_stage(`/`run_deep_inspection_stage(`/`build_metadata(` call sites: `tui/scanner.py`
and `test_stage_reporter.py` use keyword args and the new params are keyword-defaulted, so they
construct unchanged. Ran `uv run pytest tests/unit/ -q` → 374 passed; `uv run ruff check` on the three
changed files → All checks passed. No new comments/docstrings in source or tests.

**Decisions Made**: APPROVE. Every Task 6 success criterion is met and observable in
`test_stage_isolation.py` (22 tests); full unit suite green; lint clean; no regressions to existing
positional/keyword call sites; no-comments style honored. The CLAUDE.md integration rule does not
trigger here (no new `ScanRunner`/`ScanProgressScreen` constructor param; `cancel_event` threading
into `ScanRunner` is explicitly deferred to Task 8).

**Code Reviewed**: `hardware-agent/src/agent/scanner/stages.py`,
`hardware-agent/src/agent/scanner/progress.py`,
`hardware-agent/tests/unit/test_stage_isolation.py`,
`hardware-agent/src/agent/config.py` (timeout resolver, read-only),
`hardware-agent/src/agent/tui/scanner.py` (call sites, read-only).

---

## Task 7: stages.py transient retry + circuit breaker — coder (agent-developer)

**Order Given**: (P4) In the per-unit wrapper of `run_port_stage` / `run_deep_inspection_stage`:
on `TransientScanError`, retry the unit up to `settings.transient_retries` times, then demote to
`UnitScanError` (record + skip). A `BudgetExceeded` / timeout unit is never retried. Maintain
failure accounting and, when failed/total in a stage exceeds `settings.unit_failure_threshold`,
raise `CircuitBreakerError` (subclass of `BudgetExceeded`) after preserving everything gathered so
far. Target file: `scanner/stages.py` only.

**What, How & Why**: Added module-level `_run_unit_with_retry(retries, work, *args, **kwargs)`
helper and submit it to the executor in place of the direct `scan_ports_batch` /
`run_nse_vulnerability_scan` calls. The retry must re-run the unit work itself, not the future
result — a `Future` cannot be re-executed and `future.result()` only replays the stored exception.
By wrapping the call, the retry loop runs inside the executor worker thread, preserving the
existing parallel fan-out and keeping the `as_completed` loop unchanged. The helper loops
`transient_retries + 1` times, returning on success; if every attempt raises `TransientScanError`
it raises `UnitScanError` (demotion). `BudgetExceeded` (and any non-transient error) propagates out
of the helper uncaught, so a timeout unit is never retried — it surfaces to the existing
`except BudgetExceeded` skip branch. For the circuit breaker, accounting counts failed units per
stage (`batches_failed` for ports — batch-counted to match `batches_total`; reused `hosts_skipped`
for deep — host-counted to match `hosts_total`) and, at the end of each loop iteration, raises
`CircuitBreakerError` when `failed / total > unit_failure_threshold`. Raising inside the
`with ThreadPoolExecutor` block lets the executor drain in-flight futures while the host data
already written to the `HostInfo` objects is preserved, so the partial result is intact when
`ScanRunner` (Task 8) finalizes it.

**Decisions Made**:
- Retry lives in the unit work via a wrapper submitted to the executor, not on `future.result()`,
  because a `Future` is single-shot and re-running the work is the only way to retry a unit.
- Demotion raises a fresh `UnitScanError` chained (`from`) to the last `TransientScanError`, so the
  existing port/deep `except UnitScanError` skip+record branch handles it with no new branch.
- `unit_failure_threshold` is evaluated against the stage's full unit total (`batches_total` /
  `hosts_total`), counted consistently with the failure counter, so the breaker trips only once the
  configured proportion is genuinely crossed rather than on the first failure.
- Breaker check placed after the per-unit done event each iteration; the explicit
  `except CircuitBreakerError: raise` (Task 6) keeps a propagating breaker from being swallowed by
  `except BudgetExceeded`.
- No new parameter added to the stage fns or `ScanRunner` — both knobs already live on
  `AgentSettings` (Task 2) and flow through the inline TUI construction, so the CLAUDE.md
  integration rule needs no further threading.

**Code Changed**:
- Modified: `hardware-agent/src/agent/scanner/stages.py`

---

## Task 7: stages.py transient retry + circuit breaker — test-engineer

**Order Given**: Add pytest tests for Task 7 (spec 010): a unit raising `TransientScanError` once
then succeeding is retried up to `settings.transient_retries` times and its data kept; raising on
every attempt demotes to a unit failure (recorded + skipped, stage does not raise); a
`BudgetExceeded`/timeout unit is NOT retried; when failed/total exceeds
`settings.unit_failure_threshold` the stage raises `CircuitBreakerError`, below threshold it
continues. Extend `test_stage_isolation.py` and create `test_circuit_breaker.py`, mirror existing
patterns (monkeypatch `agent.scanner.stages.scan_ports_batch` / `run_nse_vulnerability_scan`,
minimal `_DummyRunner`, behavioural assertions). No comments/docstrings. Run scoped pytest + ruff.

**What, How & Why**: Retry behaviour lives in `test_stage_isolation.py::TestTransientRetry`,
driven by a stateful counting NSE fake (`_make_nse_counting_fake`) that raises `TransientScanError`
for the first N calls per ip then returns a populated `HostInfo`, plus a per-ip `calls` dict the
tests assert on. Coverage: transient-once → 2 attempts and data kept; `transient_retries=2` →
exactly 3 attempts (retry count honours the setting); persistent transient → exactly 2 attempts
(default retries=1), demoted to `unit_failed`, the host's `host_scripts` left empty while siblings
keep theirs, `deep_stage_done.units_skipped == 1`, stage does not raise; `BudgetExceeded` → exactly
1 call (never retried) surfacing as `unit_timed_out` not `unit_failed`. All retry tests use the
3-host `_eligible_hosts` fixture so a single demoted unit stays below the 0.5 breaker threshold
(1/3) and the retry path is observed in isolation. Circuit-breaker behaviour lives in
`test_circuit_breaker.py`: deep stage with all 3 hosts failing raises `CircuitBreakerError` (and a
second test asserts it is also a `BudgetExceeded`, confirming the taxonomy used by Task 8
finalization routing); 1/3 failing stays below threshold and emits a normal `deep_stage_done` with
`units_skipped == 1`. Port stage mirrors this with `host_batch_size=1` (so batches == hosts):
4/4 failing raises, 1/4 continues.

**Decisions Made**: Mocking boundary unchanged from Task 6 — monkeypatch the module-level
`agent.scanner.stages.run_nse_vulnerability_scan` / `scan_ports_batch` names, because the retry
wrapper (`_run_unit_with_retry`) re-invokes the unit work itself, so a stateful fake counting calls
is the only way to observe retry attempts (a `Future` re-replays its stored exception and cannot be
re-run). Used `max_workers=1` for retry/breaker tests for deterministic attempt counts and to make
the breaker trip ordering irrelevant under `pytest.raises`. Breaker tests assert the raise (and
below-threshold non-raise) rather than the exact preserved-host set, since `as_completed` ordering
makes which succeeding unit landed before the trip nondeterministic; the success criteria only
require the raise/continue boundary. Did not re-assert Task 6 isolation cases. `test_circuit_breaker.py`
is self-contained (own minimal `_FakeReporter`/`_DummyRunner`/fakes) mirroring sibling test-file
layout rather than importing helpers across test modules. No production code changed.

**Code Changed**:
- Modified: `hardware-agent/tests/unit/test_stage_isolation.py`
- Added: `hardware-agent/tests/unit/test_circuit_breaker.py`

---

## Task 7: stages.py transient retry + circuit breaker — code-reviewer (gate)

**Order Given**: Authoritative review gate for Task 7. Verify transient retry (retried up to
`settings.transient_retries`, data kept; persistent transient demoted to `UnitScanError` record+skip,
stage does not raise), `BudgetExceeded`/timeout never retried, circuit breaker raises
`CircuitBreakerError` (subclass of `BudgetExceeded`) when failed/total > `unit_failure_threshold`
preserving gathered data and continuing below threshold, no-comments style, surgical edits, Task 6
behavior intact (CircuitBreakerError re-raised before BudgetExceeded catch). Run pytest + ruff.

**What, How & Why**: Read TASKS.md Task 7 rubric, ARCHITECTURE/TRUTH context, and the prior Task 6/7
POOP entries. Reviewed `scanner/stages.py`: `_run_unit_with_retry(retries, work, *args, **kwargs)`
loops `range(retries + 1)`, returning on success and raising a fresh `UnitScanError` chained to the
last `TransientScanError` after exhaustion — so transient-once succeeds (2 attempts at default
retries=1), persistent transient demotes into the existing `except UnitScanError` skip branch, and
`BudgetExceeded` propagates uncaught (never retried) into the `except BudgetExceeded` timeout branch.
Both stages keep `except CircuitBreakerError: raise` ahead of `except BudgetExceeded` (Task 6 intact).
Breaker check at the end of each loop iteration raises `CircuitBreakerError` when
`failed/total > settings.unit_failure_threshold` (strict `>`, batch-counted for ports, host-counted
for deep) from inside the `with ThreadPoolExecutor` block, so already-written `HostInfo` data is
preserved. Ran `uv run pytest tests/unit/test_stage_isolation.py tests/unit/test_circuit_breaker.py`
→ 31 passed; full `uv run pytest tests/unit/` → 383 passed; `uv run ruff check` on the three changed
files → All checks passed.

**Decisions Made**: APPROVE. Every Task 7 success criterion is met and covered by tests
(`TestTransientRetry`, `TestDeepStageCircuitBreaker`, `TestPortStageCircuitBreaker`); both gates
green; edits are surgical (retry helper + breaker checks + one new import, no signature/call-site
changes). No new orchestrator/runner parameter, so the CLAUDE.md threading rule does not apply
(both knobs already live on `AgentSettings` from Task 2).

**Code Reviewed**:
- hardware-agent/src/agent/scanner/stages.py
- hardware-agent/tests/unit/test_stage_isolation.py
- hardware-agent/tests/unit/test_circuit_breaker.py
- hardware-agent/src/agent/scanner/errors.py (taxonomy lineage, read-only)

---

## Task 8: ScanRunner partial finalization + real cancellation — coder (agent-developer)

**Order Given**: (P2+P3+P4) Refactor `ScanRunner._run` (`tui/scanner.py`) so payload build +
`on_complete` is reachable from cancel / timeout / post-discovery-fatal with `partial_result=True`
+ `interrupted_stage` + `terminated_by` set per the §4.2 decision table. Stash the built runner on
`self._active_runner` (lock-guarded); `request_cancel()` sets the cancel event and calls
`terminate_active()`. Pass `self._cancel_event` into both stage fns. Resolve
`subprocess_timeout_for(self.scan_mode, "discovery")` and pass to `discover_hosts`. Enforce
`scan_deadline_s` between stages/units. Confirm inline `AgentSettings` carries the three new knobs.
Target file: `tui/scanner.py` only.

**What, How & Why**: Split the old monolithic `_run` body into two helpers plus a restructured
driver. `_build_payload` centralizes the `extract_findings` → `build_device_payload` →
`build_metadata` → `ScanPayload` assembly and now forwards `partial_result` / `interrupted_stage` /
`terminated_by` (Task 6 added these to `build_metadata`). `_finalize_partial` builds a
`partial_result=True` payload, emits a `failed` event (kept for the existing abort-message
regression), and routes the payload through `on_complete` so a partial is offered to the screen;
it degrades to a bare `failed` emit if the runner/settings were never built. `_run` initializes all
state locals up front (so every `except` branch can read them safely even on an early cancel),
stashes the runner on `self._active_runner` under `self._runner_lock` right after `build_runner`,
clears it in `finally`, and tracks `discovery_done` + `interrupted_stage` ("discovery" → "ports" →
"deep_inspection" → None). Discovery now passes the resolved
`subprocess_timeout_for(self.scan_mode, "discovery")`; both stage fns receive `cancel_event=self._cancel_event`;
`_check_deadline(deadline)` is called between discovery/stages (deadline is `None` when
`scan_deadline_s == 0`, so default behaviour is unchanged). The except ladder implements §4.2:
`FatalScanError` before discovery → `on_error`, no payload; after discovery → partial
`terminated_by="error"`; `BudgetExceeded` → partial, `"error"` for `CircuitBreakerError` (via
`isinstance`) else `"timeout"`; `ScanCancelled` → partial `"user_cancel"`; generic `Exception` →
`on_error` (preserves the `_BoomRunner` regression); full success → non-partial `terminated_by="completed"`.
`request_cancel()` now also calls `self._active_runner.terminate_active()` for honest cancellation.

**Decisions Made**:
- Emit `failed` (not a new event kind) on every partial path: the only event-level regression is
  cancel → `failed` + no `completed`, and Task 9 owns the screen-level badge/copy. Keeping `failed`
  here avoids inventing terminal states the screen does not yet read.
- Ordered the except ladder `FatalScanError` → `BudgetExceeded` → `ScanCancelled` → `Exception`;
  `CircuitBreakerError` is caught by `except BudgetExceeded` and disambiguated with `isinstance`,
  matching ARCHITECTURE §4.1.
- `discovery_done` flag (not host count) decides fatal-before-vs-after-discovery, so a zero-host
  discovery that later raises is still treated as "after discovery"; zero hosts on the happy path
  finishes non-partial `completed`.
- Did not pass the three knobs explicitly into the inline `AgentSettings(...)` — they are dataclass
  defaults and are not shadowed; `scan_deadline_s` is read straight off `settings`, exercising the
  threaded value.
- No new `ScanRunner` constructor param, so `scan_progress.py:115` and the two runner test files
  construct unchanged (grepped + full unit suite green).

**Code Changed**:
- Modified: hardware-agent/src/agent/tui/scanner.py

## Task 8: ScanRunner partial finalization + real cancellation — test-engineer

**Order Given**: Add pytest tests for Task 8 covering ScanRunner partial finalization + real
cancellation per the §4.2 decision table. Create `test_scan_runner_partial.py` and
`test_scan_runner_cancel.py`. Cover: cancel → partial payload (`partial_result True`,
`interrupted_stage` set, `terminated_by="user_cancel"`) and `request_cancel()` sets the event AND
calls `terminate_active()`; timeout (`BudgetExceeded` → `terminated_by="timeout"`,
`CircuitBreakerError` → `"error"`); post-discovery `FatalScanError` → partial `"error"`,
fatal-before-discovery → `on_error`, no payload; zero hosts → non-partial empty `"completed"`.
Mirror existing runner test fakes; behavioural assertions; no comments. Run scoped + full
`uv run pytest tests/unit/` and ruff. Do not change production code.

**What, How & Why**: Mirrored the `_FakeReporter` / `_FakeRunner(NmapRunner)` seams from
`test_scan_runner_events.py`. Drove `ScanRunner._run()` directly (no thread) as the existing tests
do. Monkeypatched `agent.tui.scanner.check_network_connectivity` and `agent.tui.scanner.discover_hosts`
(imported by name into the module) to seed discovered hosts or a fatal-at-discovery raise, and
monkeypatched `stages.run_port_stage` (referenced as `stages.run_port_stage` in production) to raise
the taxonomy class under test. Captured outcomes via `on_complete`/`on_error` list appenders and the
reporter's event log. `test_scan_runner_partial.py` asserts metadata `partial_result`/
`interrupted_stage`/`terminated_by` for post-discovery fatal, BudgetExceeded (timeout),
CircuitBreakerError (error), fatal-before-discovery (on_error, zero payloads), and zero-hosts
(non-partial `completed`, no `interrupted_stage` key). `test_scan_runner_cancel.py` asserts
`request_cancel()` sets the cancel event and calls `terminate_active()` on a recording fake runner
(stashed on `_active_runner`), the no-active-runner path, and that a `ScanCancelled` mid-port-stage
finalizes a `user_cancel` partial that retains discovered devices and emits `failed` (not
`completed`). Behavioural assertions only.

**Decisions Made**:
- Mocking boundary at the `stages.*` stage functions and the module-level `discover_hosts`, matching
  how Task 6/7 isolated stages — keeps the runner driver under test without real nmap.
- For `request_cancel()` + `terminate_active()`, set `_active_runner` directly on the instance rather
  than racing a live thread; this is the deterministic behavioural seam the production code reads.
- `device.ip` normalizes to `IPv4Address`; compared via `str(...)` for the retained-devices checks.
- Did not add an in-loop "stops reading further futures" test — that cancel-check lives in
  `stages.py` and is already covered by `test_stage_isolation.py`; here the stage is mocked.
- No production changes were needed; all targeted behaviours were observable through existing seams.

**Code Changed**:
- Added: hardware-agent/tests/unit/test_scan_runner_partial.py
- Added: hardware-agent/tests/unit/test_scan_runner_cancel.py

---

## Task 8 — Code Reviewer (APPROVE)

**Order Given**: Authoritative review gate for Task 8 (ScanRunner partial finalization + real cancellation). Verify against §4.2 decision table and Task 8 success criteria; run uv run pytest and uv run ruff check on the changed files; confirm no regressions.

**What, How, and Why**:
- Reviewed the refactored ScanRunner._run and its new finalization/cancel helpers against the §4.2 decision table and the Task 8 success criteria, plus the two new test modules.
- Ran `uv run pytest tests/unit/test_scan_runner_partial.py tests/unit/test_scan_runner_cancel.py tests/unit/test_scan_runner_events.py tests/unit/test_scan_runner_timing.py` (21 passed), the full `uv run pytest tests/unit/` (395 passed), and `uv run ruff check` on the three changed files (all checks passed).
- Confirmed: request_cancel() does _cancel_event.set() AND _active_runner.terminate_active() under _runner_lock; _active_runner set right after build_runner and cleared in finally; _cancel_event passed into both stage fns; subprocess_timeout_for(scan_mode,"discovery") forwarded to discover_hosts; scan_deadline_s enforced between stages via _check_deadline. Decision table verified: fatal-before-discovery -> on_error/no payload; fatal-after -> partial terminated_by="error"; BudgetExceeded -> "timeout"; CircuitBreakerError -> "error" via isinstance; ScanCancelled -> "user_cancel"; zero hosts -> non-partial "completed" with interrupted_stage absent.
- Confirmed CLAUDE.md integration rule: inline AgentSettings carries the three new knobs as dataclass defaults (not shadowed); ScanRunner constructor signature unchanged so scan_progress.py and runner tests still construct correctly. No new docstrings/comments introduced in the new methods.

**Decisions Made**: APPROVE. Every Task 8 success criterion is met and observable in tests; gates are green; edits are surgical and reuse build_metadata/build_runner/terminate_active rather than inventing new paths.

**Code Reviewed**:
- hardware-agent/src/agent/tui/scanner.py
- hardware-agent/tests/unit/test_scan_runner_partial.py
- hardware-agent/tests/unit/test_scan_runner_cancel.py
- hardware-agent/src/agent/scanner/stages.py (build_metadata signature)
- hardware-agent/src/agent/tui/screens/scan_progress.py (ScanRunner call site)

---

## Task 9: ScanProgressScreen contingency states (DESIGN) — coder (agent-developer)

**Order Given**: (P2+P3, DESIGN.md) Add the `#scan-badge` `Static` under the header plus its CSS
block; implement Partial, Fatal, and Cancelling states (spinner hides on every terminal state; only
Completed sets the bar to 100%; Partial/Fatal/Cancelling hold the last real value); `action_abort`
while running enters Cancelling (request cancel, no dismiss) and resolves to Partial (data exists)
or Aborted (`dismiss(None)`); a second Ctrl+X while cancelling is ignored; `_handle_error`
distinguishes Fatal (no payload) from Partial (via `on_complete`); add the degraded/timeout/partial
log templates, badge strings, and end-action labels verbatim per DESIGN Copy; generalize the
`_done` guard to a terminal predicate covering Completed|Partial|Fatal (Cancelling not terminal);
verify `home.py` needs no new constructor param.

**What, How & Why**: Added `Static("", id="scan-badge")` directly under `#scan-header` in
`compose_body` and the `#scan-badge { margin-bottom:1; text-style:bold; display:none; }` block in
`app.tcss` (hidden by default, revealed only in Partial/Fatal). Introduced `self._state`
(`running` → `cancelling`/`completed`/`partial`/`fatal`) alongside the kept `self._done` flag, plus
a `_terminal()` predicate (`completed|partial|fatal`) now used by every navigation/select/abort
guard in place of `_done`. Split the old `_handle_complete` into a dispatcher that branches on
`payload.metadata["partial_result"]`: `_handle_success` keeps the 009 look (bar→100%, View scan
focused); `_handle_partial` holds the bar, shows the `[black on yellow] PARTIAL [/] {reason}` badge,
writes the `⚠ Partial — {devices} devices, {findings} vulnerabilities (interrupted during {stage})`
line, and relabels `#btn-view-scan` to `View partial scan`. A partial payload with no devices
(nothing gathered, the cancel-before-data case) takes the Aborted `dismiss(None)` exit per DESIGN
(d). `_handle_error` now renders the Fatal terminal state (badge `✗ SCAN FAILED — nothing to keep`,
`#btn-view-scan` hidden, only `#btn-back-home` focused) rather than a toast; the `✗ Scan failed:`
log line is left to the existing `failed` event so it is not duplicated. `action_abort` while
running calls `_enter_cancelling` (appends the `● Stopping scan — terminating running steps…` line
and `request_cancel()`), ignores a second Ctrl+X, and dismisses only from a terminal state. Added
`port_stage_done`/`deep_stage_done` degraded finish-line variants gated on `units_skipped > 0`, the
per-unit `unit_timed_out`/`unit_failed` `↳` lines, and a `deep_stage_done` handler that finishes the
scripts stage (the `normalize_started` finish was re-guarded on `"scripts" in self._stage_lines` to
avoid a double line). Reason/stage copy comes from two class-level maps consuming
`metadata["terminated_by"]`/`["interrupted_stage"]`.

**Decisions Made**:
- Kept `self._done` (set only for Completed/Partial, never Fatal) so the existing
  `test_error_handler_does_not_dismiss_or_complete` (`_done is False` after a fatal) still passes,
  while routing all action guards through the new `_terminal()` predicate.
- The Fatal `✗ Scan failed: {error}` log line is emitted by the runner's `failed` event (009
  behaviour), so `_handle_error` only paints badge + buttons + state — avoids a duplicate red line.
- Suppressed the `failed`-event red line while `cancelling`/terminal so the cancel→Partial flow
  matches DESIGN mockups (d)→(b); the line is still written in the running state
  (`test_failed_event_writes_line`). A timeout/circuit-breaker Partial may still show one preceding
  red line (runner emits `failed` before `on_complete` in the running state); this is a Task 8
  emission artifact and is not gated by the Task 9 success criteria.
- `interrupted_stage` label map includes both `ports` (the value the runner actually writes) and the
  DESIGN `port_scan` key, mapping both to the exact `port scanning` label.
- `deep_stage_done` only renders a scanned line when the scripts stage was actually started
  (`"scripts" in self._stage_lines`), so the zero-eligible-hosts path keeps its
  `No hosts to inspect — skipping scripts` line.
- `home.py:73` constructs `ScanProgressScreen(subnet=subnet, scan_mode=mode)` — verified no new
  constructor param is needed (CLAUDE.md integration rule); home.py left unchanged.

**Code Changed**:
- modified: hardware-agent/src/agent/tui/screens/scan_progress.py
- modified: hardware-agent/src/agent/tui/app.tcss

---

## Task 9: ScanProgressScreen contingency states (DESIGN) — test-engineer

**Order Given**: Add pytest tests for Task 9 (Partial / Fatal / Cancelling screen states) by
extending `test_scan_progress_screen.py`, mirroring its Pilot/run_test patterns. Cover: `#scan-badge`
hidden while running and on success, shown with the exact Partial and Fatal strings; `#btn-view-scan`
hidden in Fatal, shown and labelled "View partial scan" in Partial; progress bar non-100% in
Partial/Fatal, 100% only on Completed; Cancelling appends the exact stop line and ignores a second
Ctrl+X until the runner callback resolves; degraded finish lines only when `units_skipped > 0`;
Fatal path shows only `#btn-back-home`. Use exact DESIGN Copy strings. No production code changes.

**What, How & Why**:
- Added `TestScanBadge`, `TestEndActions`, `TestProgressBarTerminal`, `TestCancelling`, and
  `TestDegradedFinishLines` classes.
- Badge: asserted hidden (`display is False`) while running and after a clean `_handle_complete`,
  and shown (`display is True`) with rendered text containing `PARTIAL` + the exact reason copy
  (timeout and user_cancel variants) and the Fatal `✗ SCAN FAILED — nothing to keep` string.
- End actions: `#btn-view-scan` hidden in Fatal (only `#btn-back-home` visible), shown in Partial
  with `label == "View partial scan"`.
- Progress bar: pre-seeded a real value (62 / 6) then asserted Partial/Fatal hold it and never read
  100; Completed reaches exactly 100.
- Cancelling: drove `ctrl+x` via `pilot.press`, asserted the `● Stopping scan — terminating running
  steps…` line, `_state == "cancelling"`, `_terminal() is False`, a single `request_cancel` call,
  a second Ctrl+X ignored (still one call), and resolution to Partial only when the runner callback
  fires `_handle_complete` with a partial payload.
- Degraded lines: `port_stage_done` / `deep_stage_done` render the `⚠ … skipped` variants only when
  `units_skipped > 0` and the clean `✓` line otherwise; `unit_timed_out` / `unit_failed` `↳` lines.

**Decisions Made**:
- Mocking boundary: reused the existing autouse fixtures that neuter `ScanRunner.start` and
  `load_config`; events are injected via `ProgressUpdated`, terminal states via direct
  `_handle_complete` / `_handle_error` calls (mirrors the existing `TestCompletion` / `TestFailure`
  style). `request_cancel` is stubbed per-test on the live `screen._runner` instance to count calls
  without touching real subprocess termination.
- Badge visibility is driven by the `#scan-badge { display: none }` rule in `app.tcss`, which the
  shared `_Harness` did not load. Added `CSS_PATH` on `_Harness` pointing at the production
  `app.tcss` so the CSS-hidden running/success state is observable; this is the faithful mechanism
  and is test-only (no production change). Verified the 33 pre-existing tests still pass with the
  stylesheet loaded.
- Badge text asserted via the rendered plain text (`str(Static.render())`); markup tags are consumed
  by the renderer, so substrings of the DESIGN Copy are matched rather than raw markup.
- Partial payloads built with `model_copy(update={"metadata": ...})` carrying
  `partial_result`/`terminated_by`/`interrupted_stage`; devices > 0 so `_handle_partial` does not
  take the no-data `dismiss(None)` branch.

**Code Changed**:
- modified: hardware-agent/tests/unit/test_scan_progress_screen.py

---

## Task 9: ScanProgressScreen contingency states (DESIGN) — code-reviewer (gate)

**Order Given**: Authoritative review gate for Task 9 (final task of spec 010). Verify the
`#scan-badge` widget + CSS, the Partial/Fatal/Cancelling states, exact DESIGN Copy strings (badge,
log templates, end-action labels), the `_done`→terminal-predicate generalization, the Fatal-vs-Partial
`_handle_error` split, `#btn-view-scan` hidden in Fatal / labelled "View partial scan" in Partial,
bar non-100% in Partial/Fatal, second-Ctrl+X-ignored-while-cancelling, degraded lines gated on
`units_skipped > 0`, and that `home.py` is unchanged (CLAUDE.md integration rule). Run
`uv run pytest tests/unit/` and `uv run ruff check` on the changed Python files.

**What, How & Why**: Read TASKS.md (Task 9 rubric), DESIGN.md (Copy/widget/state/key-binding
authority), and the Task 8/9 POOP entries, then the changed sources. Verified every DESIGN Copy
string verbatim against the implementation: Partial badge `[black on yellow] PARTIAL [/] {reason}`
(L370); Fatal badge `[bold red]✗ SCAN FAILED — nothing to keep[/bold red]` (L390); the three
`_PARTIAL_REASONS` strings + `partial results kept` fallback; `_INTERRUPTED_STAGE_LABELS` (incl.
both `ports` and `port_scan`→`port scanning`, plus `an earlier stage` fallback); port/deep degraded
and clean finish lines; `↳ timed out/failed (skipped)` unit lines; the `● Stopping scan …`
cancelling line; and the `⚠ Partial — {devices} devices, {findings} vulnerabilities (interrupted
during {stage})` final line. Confirmed `_terminal()` (completed|partial|fatal) now guards every
nav/select/abort action while `cancelling` is excluded; `_done` retained only for the
`normalize_started`/failure-regression semantics. Confirmed `_handle_error` paints Fatal (badge,
hides `#btn-view-scan`, focuses `#btn-back-home`, `_done` stays False) and is distinct from the
`_handle_partial` path routed via `on_complete`; a no-device partial takes the `dismiss(None)`
Aborted exit per DESIGN (d). Checked `action_abort` enters Cancelling once and returns on a second
Ctrl+X. Verified `target_pct` returns `None` for `failed` so a real timeout/circuit-breaker Partial
never eases the bar to 100 (only `completed`→100). Confirmed `home.py` is absent from `git status`
(unchanged) and still constructs `ScanProgressScreen(subnet=subnet, scan_mode=mode)` with no new
param. Gates: `uv run pytest tests/unit/` → 414 passed; `uv run pytest
tests/unit/test_scan_progress_screen.py` → 35 passed; `uv run ruff check` on
`scan_progress.py` + `test_scan_progress_screen.py` → All checks passed (app.tcss not
ruff-parseable, inspected by hand — `#scan-badge { margin-bottom:1; text-style:bold; display:none; }`
matches DESIGN L77).

**Decisions Made**: APPROVE. Every Task 9 success criterion is met and observably covered by the
new test classes (`TestScanBadge`, `TestEndActions`, `TestProgressBarTerminal`, `TestCancelling`,
`TestDegradedFinishLines`); all DESIGN Copy reproduced verbatim with no rewording; edits surgical;
no-comments style honored; home.py untouched (integration rule satisfied — no new constructor
param). The coder-noted preceding `failed` red line on timeout/circuit-breaker Partial paths is a
Task 8 emission artifact, not gated by Task 9 criteria, and is acceptable.

**Code Reviewed**:
- hardware-agent/src/agent/tui/screens/scan_progress.py
- hardware-agent/src/agent/tui/app.tcss
- hardware-agent/src/agent/tui/screens/home.py (verified unchanged)
- hardware-agent/tests/unit/test_scan_progress_screen.py
- hardware-agent/src/agent/scanner/progress.py (target_pct for failed, read-only)
