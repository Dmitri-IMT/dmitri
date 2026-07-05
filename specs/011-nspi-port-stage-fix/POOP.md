# POOP — Fix NSPi mode port stage (Stage 2)

Append-only execution ledger. Every agent-developer, test-engineer, and code-reviewer appends
one section before returning (Order Given / What, How & Why / Decisions Made / Code Changed or
Reviewed — file paths only, no snippets). The orchestrator appends only `STRUCTURAL_REEVAL`
blocks.

---

## Task 1 — agent-developer — Completion fix: NSPi pass 1 runs at `-T4`

**Order Given**: In `_scan_ports_batch_nspi`, change pass 1 (broad top-1000 `-sV -O` sweep) from
`-T2` to `-T4`; leave pass 2 (OT-ports `-p <NSPI_PORTS> -sV` probe) at polite `-T2`; keep `-n` on
both; preserve two-pass + `merge_ports` structure; touch no other mode. Update the 004 contract
note so "Timing & flags" reads `-T4 -n` (pass 1) / `-T2 -n` (pass 2).

**What, How & Why**: Changed the single flag in `pass1_args` from `-T2` to `-T4` — a one-token
edit, the laziest change that satisfies the fix. Root cause (DMI-50): `-T2` serializes probes so
pass 1's top-1000 sweep across an 8-host batch cannot finish inside the shared 600 s per-invocation
budget, so every batch hits `BudgetExceeded` and the circuit breaker aborts the stage. `-T4` on
pass 1 matches Quick's proven port-stage timing on these same PLCs; pass 2's OT-service probes keep
polite `-T2`. The 004 contract note already read `-T4 -n` / `-T2 -n` (status "amended by DMI-50
2026-07-05"), so it already matched the required state — no edit was needed there.

**Decisions Made**:
- Only `pass1_args` touched; `pass2_args`, the two-pass ordering, and `merge_ports` dedup left
  byte-for-byte unchanged.
- No config/budget change: `TIMEOUTS["ports"]["nspi"]` stays 600.0 per ARCHITECTURE decision 1.
- No orchestrator/runner parameter added, so the CLAUDE.md integration rule is vacuously satisfied
  (nothing to thread through `ScanRunner` / `ScanProgressScreen`).
- Left the existing `test_both_passes_use_t2_and_n` failing as-is: updating it is the test-engineer's
  task per ARCHITECTURE's testing table (assert pass 1 `-T4`, pass 2 `-T2`) and the test is not in
  Task 1's target files.

**Code Changed**:
- Modified: `hardware-agent/src/agent/discovery/port_discovery.py`
- Unchanged (already matched): `specs/004-nspi-scan-mode/contracts/nspi-constants.md`

---

## Task 1 — test-engineer

**Order Given**: Update the NSPi two-pass test so it asserts pass 1 uses `-T4` (and NOT
`-T2`) and pass 2 still uses `-T2`, both keeping `-n`; rename the misleading
`test_both_passes_use_t2_and_n`; keep the existing merge/dedup assertions intact. Only test
Task 1's change. Confirm `uv run pytest tests/unit/test_nspi_two_pass_merge.py` is green.

**What, How & Why**: Renamed `test_both_passes_use_t2_and_n` to
`test_pass1_t4_pass2_t2_and_n` and rewrote its body to assert `captured[0]` (pass 1, the broad
top-1000 sweep) contains `-T4` and not `-T2`, `captured[1]` (pass 2, the OT-port probe)
contains `-T2` and not `-T4`, and both keep `-n`. This mirrors the existing mocking style in the
file (`_make_nspi_runner` captures each nmap invocation's argv via a stubbed `run_xml`, ordered
pass 1 then pass 2). The old test encoded the pre-fix invariant (both passes `-T2`) which is now
wrong after the Stage 2 completion fix; behavior assertions on the exact captured argv prove the
timing split without snapshotting the full command line.

**Decisions Made**: Mocking boundary is the `NmapRunner.run_xml` stub (unchanged from the file's
existing helper) — the unit boundary is the nmap runner, no subprocess. Asserted both presence
(`-T4` in pass 1 / `-T2` in pass 2) and absence (`-T2` not in pass 1 / `-T4` not in pass 2) to
pin the split rather than just presence. Left all merge/dedup/call-count/`-p`/`NSPI_PORTS` tests
untouched. Did not add tests for other tasks' changes.

**Code Changed**:
- Modified: `hardware-agent/tests/unit/test_nspi_two_pass_merge.py`

---

## Task 1 — code-reviewer — [APPROVE]

**Order Given**: Authoritative review gate for Task 1 (spec 011). Verify pass 1 args contain `-T4`
(not `-T2`) and still `-n`, `-sV`, `-O`, top-1000 (no `-p`); pass 2 args unchanged
(`-T2 -n -p <NSPI_PORTS> -sV`); no other mode's branch/config/budget/`merge_ports` touched; 004
contract note reflects `-T4 -n` pass 1 / `-T2 -n` pass 2. Run `uv run pytest` and `uv run ruff check`.

**What, How & Why**: Reviewed the source and test diffs against Task 1 success criteria, ARCHITECTURE
decision 1, and TRUTH acceptance criteria. `git diff` confirms a single-token edit: `pass1_args`
`-T2`→`-T4`; `pass2_args`, two-pass ordering, and `merge_ports` byte-for-byte unchanged. Pass 1 =
`["-Pn", "-T4", "-n", "-sV", "-O", *ips]` (no `-p`, top-1000); pass 2 =
`["-Pn", "-T2", "-n", "-p", NSPI_PORTS, "-sV", *ips]`. No other mode branch, `config.py`, or budget
touched. 004 contract note "Timing & flags" already reads `-T4 -n` / `-T2 -n` (amended by DMI-50) —
confirmed correct, no edit needed. Test `test_pass1_t4_pass2_t2_and_n` asserts the split (presence +
absence) and `-n` on both passes; merge/dedup/`-p`/`NSPI_PORTS` assertions retained. Ran
`uv run pytest` → 445 passed; `uv run ruff check` on both changed files → all checks passed. No
`# ponytail:` markers present in the touched files (nothing to strip). CLAUDE.md integration rule
vacuously satisfied — no orchestrator/runner parameter added.

**Decisions Made**: [APPROVE]. Every Task 1 success criterion met, both gates green, changes
surgical and confined to the NSPi branch, contract note in sync.

**Code Reviewed**:
- `hardware-agent/src/agent/discovery/port_discovery.py`
- `hardware-agent/tests/unit/test_nspi_two_pass_merge.py`
- `specs/004-nspi-scan-mode/contracts/nspi-constants.md` (contract note; unchanged, verified)

---

## Task 2 — agent-developer — Relocate `ScanCancelled` into `scanner/errors.py`

**Order Given**: Move the single `class ScanCancelled(ScanError)` out of `tui/scanner.py` (~line 29)
into `scanner/errors.py`, placed consistently with the other error classes; change `tui/scanner.py`
to import it from `agent.scanner.errors` (add to the existing import block, delete the local class).
Pure relocation, no behaviour change; exactly one `ScanCancelled(ScanError)` afterward; `scanner/`
must not import from `tui/`. Do NOT add the Task 3 nmap cancel guard.

**What, How & Why**: Added `class ScanCancelled(ScanError): pass` to `scanner/errors.py` between
`TransientScanError` and `BudgetExceeded`, grouping it with the other direct `ScanError` subclasses.
Deleted the local class in `tui/scanner.py` and swapped `ScanError` for `ScanCancelled` in the
existing `from agent.scanner.errors import (...)` block. This corrects layering — `scanner/` no
longer needs anything from `tui/` — so Task 3's nmap guard and `ScanRunner` can share one class type.
`_check_cancel` (raises) and the `except ScanCancelled` catch at `scanner.py:313` now bind to the
relocated type; behaviour is identical.

**Decisions Made**:
- Used a bare `pass` body (dropped the old docstring) to match every sibling class in `errors.py`
  and the project's no-docstrings rule. The constructor/signature is the default `Exception` one,
  so nothing that raises or catches `ScanCancelled()` changes.
- Removed `ScanError` from the `tui/scanner.py` import: it was referenced only by the deleted local
  class (grep confirmed no other use in that file), so leaving it would be an unused import.
- Tests importing `from agent.tui.scanner import ScanCancelled` keep working — the name is now
  re-exported into `tui/scanner`'s namespace via the import, so no test edits were needed.
- No orchestrator/runner parameter added, so the CLAUDE.md integration rule is vacuously satisfied.

**Code Changed**:
- Modified: `hardware-agent/src/agent/scanner/errors.py`
- Modified: `hardware-agent/src/agent/tui/scanner.py`

---

## Task 2 — test-engineer

**Order Given**: Add/keep tests for the `ScanCancelled` relocation into
`hardware-agent/src/agent/scanner/errors.py`. Assert it is importable from `agent.scanner.errors`
and is a subclass of `ScanError`, and assert the `ScanCancelled` caught by `ScanRunner`
(`tui/scanner.py`) is the SAME class object as `agent.scanner.errors.ScanCancelled` (identity).
Do NOT test the nmap cancel guard (Task 3). Mirror existing test patterns; no comments/docstrings.

**What, How, and Why**: Extended the two existing tests instead of adding a new file, since both
already cover this surface. In `test_scan_errors.py` (`TestScanCancelled`) I added
`test_defined_in_errors_module` (subclass of `ScanError` and `__module__ == "agent.scanner.errors"`,
proving the canonical definition site) and `test_tui_import_is_same_class` (identity between the
`agent.tui.scanner` name and the `agent.scanner.errors` name). In `test_scan_runner_cancel.py` I
added `TestScanCancelledIdentity.test_runner_catches_same_class_as_errors_module` asserting the
symbol `ScanRunner` imports/catches is `scanner_errors.ScanCancelled` by identity — this is the
guard against the relocation silently minting two distinct types.

**Decisions Made**:
- No new test file: the relocation is a pure move, so mirroring the two nearest tests (per strategy)
  kept the change minimal and behavior-focused.
- Imported the canonical class as `ScanCancelledFromErrors` from `agent.scanner.errors` (not via the
  `agent.scanner` package, which does not re-export `ScanCancelled`) to test the exact import path
  the task specifies.
- Asserted identity (`is`) rather than snapshotting module contents; picked `__module__` as the
  definition-site check because it is the behavioral signal that the class lives in `errors.py`.
- No production code changed; no testability hook needed.

**Code Changed**:
- Modified: `hardware-agent/tests/unit/test_scan_errors.py`
- Modified: `hardware-agent/tests/unit/test_scan_runner_cancel.py`

---

## Task 2 — code-reviewer — [REJECT]

**Order Given**: Authoritative review gate for Task 2 (spec 011). Verify exactly one
`ScanCancelled(ScanError)` exists in `scanner/errors.py` (grep whole package); `tui/scanner.py`
imports it from `agent.scanner.errors` and no longer defines it locally; `scanner/` does not import
from `tui/`; the replaced `ScanError` import is neither undefined nor unused; pure relocation, no
behaviour change. Run `uv run pytest` (full suite) and `uv run ruff check`.

**What, How & Why**: Reviewed the relocation against Task 2 success criteria and ARCHITECTURE
decision 3. The relocation itself is correct: grep of the whole package finds exactly one
`class ScanCancelled(ScanError)` — in `scanner/errors.py`; `tui/scanner.py` imports it via its
existing `from agent.scanner.errors import (...)` block with the local class deleted; no `agent.tui`
import exists anywhere under `scanner/` (layering intact); `ScanError` bare name is not referenced in
`tui/scanner.py` (only `FatalScanError`), so its removal leaves no undefined name and no unused
import; behaviour is unchanged. `uv run pytest` (full) → 448 passed. However `uv run ruff check` on
the changed files FAILS: `tests/unit/test_scan_runner_cancel.py:1` raises I001 (import block
un-sorted) — the test-engineer's added `from agent.scanner import errors as scanner_errors` sits
after `from agent.scanner import stages`, out of isort order. The four ruff gates on the other three
files pass. A lint-gate failure on a changed file blocks approval.

**Decisions Made**: [REJECT]. Sole blocker is the ruff I001 failure on the added test file; the
production relocation meets every success criterion. Fix is mechanical (reorder the two
`from agent.scanner import ...` lines, or run `ruff check --fix`), after which this should approve.

**Code Reviewed**:
- `hardware-agent/src/agent/scanner/errors.py`
- `hardware-agent/src/agent/tui/scanner.py`
- `hardware-agent/tests/unit/test_scan_errors.py`
- `hardware-agent/tests/unit/test_scan_runner_cancel.py`

---

## agent-developer — Task 2 lint fix (import ordering)

**Order Given** — Fix only the I001 isort lint failure in
`hardware-agent/tests/unit/test_scan_runner_cancel.py`; reorder the import block so
`from agent.scanner import errors as scanner_errors` precedes
`from agent.scanner import stages`. No production code, no `ScanCancelled` relocation changes,
no test-assertion changes.

**What, How, and Why** — Swapped the two adjacent `from agent.scanner import ...` lines so the
`errors` import comes before `stages`, satisfying ruff's isort ordering. Scoped, one-block edit
only. Verified `uv run ruff check` (all checks passed) and
`uv run pytest tests/unit/test_scan_runner_cancel.py tests/unit/test_scan_errors.py` (18 passed).

**Decisions Made** — Manual two-line swap rather than `ruff check --fix` to keep the diff
minimal and confined to the import ordering.

**Code Changed** — Modified: `hardware-agent/tests/unit/test_scan_runner_cancel.py`

---

## Task 2 — code-reviewer — [APPROVE] (re-review after lint fix)

**Order Given**: Re-review Task 2 after the prior `[REJECT]` on the ruff I001 import-ordering
failure in `hardware-agent/tests/unit/test_scan_runner_cancel.py`. Confirm the relocation substance
still holds and the lint fix landed: exactly one `ScanCancelled(ScanError)` in `scanner/errors.py`;
`tui/scanner.py` imports it from `agent.scanner.errors` with no local class; `scanner/` does not
import `tui/`; no undefined/unused import from the `ScanError` removal; import ordering in the test
now satisfies ruff. Run `uv run pytest` (full) and `uv run ruff check`.

**What, How & Why**: Grep of the whole package finds exactly one `class ScanCancelled(ScanError)` —
`scanner/errors.py:20`. `tui/scanner.py` imports `ScanCancelled` via its
`from agent.scanner.errors import (...)` block (no local class); `ScanError` bare name is gone from
that file's imports and is not otherwise referenced, so no undefined/unused import. Grep for any
`agent.tui` import under `scanner/` returns nothing — layering intact. In
`test_scan_runner_cancel.py` the import block now orders `from agent.scanner import errors as
scanner_errors` before `from agent.scanner import stages`, satisfying isort. Ran `uv run ruff check`
on all four changed files → all checks passed; `uv run pytest` (full) → 448 passed. No
`# ponytail:` markers in any touched file (nothing to strip).

**Decisions Made**: [APPROVE]. Every Task 2 success criterion met; the sole prior blocker (I001)
is resolved; both gates green; relocation is a pure, behaviour-preserving move.

**Code Reviewed**:
- `hardware-agent/src/agent/scanner/errors.py`
- `hardware-agent/src/agent/tui/scanner.py`
- `hardware-agent/tests/unit/test_scan_errors.py`
- `hardware-agent/tests/unit/test_scan_runner_cancel.py`

---

## Task 3 — agent-developer — Cancel-before-spawn guard in the nmap runner

**Order Given**: Add `if self._cancelled: raise ScanCancelled(...)` at the top of
`NmapRunner.run_xml`, `NmapRunner.run_streamed`, and `LoggedNmapRunner.run_xml` — before any run
folder or subprocess is created. Import `ScanCancelled` from `agent.scanner.errors`. No progress
sink / stats callback / stream hook; no reordering of `ScanRunner.request_cancel()`; no stage-loop,
retry, or circuit-breaker change; `ScanCancelled` stays a plain `ScanError` (not retried).

**What, How & Why**: Added `ScanCancelled` to the existing `agent.scanner.errors` import block, then
placed one `if self._cancelled: raise ScanCancelled("Scan cancelled before nmap spawn.")` guard at
the top of each of the three methods. In `NmapRunner.run_xml` the guard precedes the `command`
list / `subprocess.run`. In `NmapRunner.run_streamed` it precedes the `console.log`/`stderr.log`
path setup and `subprocess.Popen`. In `LoggedNmapRunner.run_xml` it sits directly after the local
workspace import but before `make_run_folder_name` / `run_dir.mkdir`, so it precedes both the
`logs/` run folder and the delegated `run_streamed` spawn. This makes in-flight batch threads that
sit between passes (or in a retry loop) finish fast so `ThreadPoolExecutor.shutdown(wait=True)`
returns promptly, per ARCHITECTURE decision 3. Guard only fires when already cancelled, so the
uncancelled path is byte-for-byte unchanged.

**Decisions Made**:
- Reused the `_cancelled` flag already set by `terminate_active()`; no new state.
- `ScanCancelled` is a plain `ScanError`, so `_run_unit_with_retry` (catches only
  `TransientScanError`) does not retry it and it does not count toward the circuit-breaker ratio.
- Guard message string mirrors the file's existing short-sentence raise style.

**Code Changed**:
- `hardware-agent/src/agent/scanner/nmap.py`

---

## Task 3 — test-engineer

**Order Given**: Add `hardware-agent/tests/unit/test_cancel_before_spawn.py` (mirror
`test_scan_runner_cancel.py`). For each of `NmapRunner.run_xml`, `NmapRunner.run_streamed`, and
`LoggedNmapRunner.run_xml`: set `runner._cancelled = True` and assert the method raises
`ScanCancelled`; assert no subprocess was spawned (patch `subprocess.run` / `subprocess.Popen`,
assert never called); for `LoggedNmapRunner.run_xml` assert no `logs/` run folder was written; also
assert the un-cancelled path still works. No comments/docstrings; behavior over snapshots.

**What, How, and Why**: Wrote a new test file with three classes, one per guarded method. Each has a
cancelled case (`_cancelled = True` → `pytest.raises(ScanCancelled)` with the spawn mock asserted
never called) and an un-cancelled case proving the guard is skipped. Constructed runners via
`NmapRunner.__new__` / `LoggedNmapRunner.__new__` and set attributes directly, mirroring the
existing helpers in `test_nmap_streaming.py` and `test_logged_runner.py` (avoids the real
`_resolve_nmap_path`). The spawn boundary is patched with `monkeypatch.setattr(subprocess, "run", …)`
and `…, "Popen", …)`, recording into a `calls` list that must stay empty — this proves the guard
fires before any process launch. For `run_streamed` cancelled I also assert `run_dir` stays empty
(no `console.log`/`stderr.log`), and for `LoggedNmapRunner.run_xml` cancelled I assert `logs_dir`
has no run folder (the guard sits before `make_run_folder_name`/`mkdir`). Un-cancelled paths:
`run_xml` uses a fake `subprocess.run` returning `returncode=0` + `<nmaprun/>`; `run_streamed` and
`LoggedNmapRunner.run_xml` drive the real Python interpreter as a fake nmap (same technique the
mirrored suites use) and assert a process ran / a run folder was written.

**Decisions Made**:
- Mocking boundary is the stdlib `subprocess` module's `run`/`Popen` attributes (the true spawn
  point) rather than the runner methods, so the guard's before-spawn ordering is what is under test.
- Represented cancellation by setting `_cancelled = True` directly (what `terminate_active()` sets),
  matching how the existing cancel test reasons about runner cancellation.
- Chose the real-interpreter fake-nmap approach for the two streaming un-cancelled cases (consistent
  with `test_nmap_streaming.py` / `test_logged_runner.py`) and a lightweight `SimpleNamespace` fake
  for `run_xml` un-cancelled (no real process needed to prove the guard is skipped).
- Kept the un-cancelled assertions minimal (spawn happened / folder written), deferring full
  happy-path coverage to the existing streaming/logged-runner suites — no duplication.
- No production code changed; no testability hook needed.

**Code Changed**:
- Created: `hardware-agent/tests/unit/test_cancel_before_spawn.py`

---

## Task 3 — code-reviewer — [APPROVE]

**Order Given**: Authoritative review gate for Task 3 (spec 011). Verify in all three methods
(`NmapRunner.run_xml`, `NmapRunner.run_streamed`, `LoggedNmapRunner.run_xml`) that `ScanCancelled`
is raised before any subprocess spawn and before any `logs/` run folder is created — by reading the
actual code, not just passing tests; un-cancelled path unchanged; `ScanCancelled` imported from
`agent.scanner.errors`, a plain `ScanError`, not caught by `_run_unit_with_retry` (no retry, no
circuit-breaker count); `request_cancel()` not reordered, `tui/scanner.py`/stage-loop/retry/circuit
breaker untouched, no progress/stats/stream hook. Run `uv run pytest` (full) and `uv run ruff check`.

**What, How & Why**: Read `scanner/nmap.py` directly. The guard `if self._cancelled: raise
ScanCancelled("Scan cancelled before nmap spawn.")` sits at the top of all three methods and truly
precedes the spawn/folder work: in `run_xml` before the `command` list / `subprocess.run`; in
`run_streamed` before the `console.log`/`stderr.log` path setup and `subprocess.Popen`; in
`LoggedNmapRunner.run_xml` after the local workspace import but before `make_run_folder_name` /
`run_dir.mkdir` and the delegated `run_streamed`. `git diff` of nmap.py is purely additive (import +
three three-line guards) — no reordering, no sink. `errors.py` shows `ScanCancelled(ScanError)` is a
plain `ScanError`; `stages.py:48` `_run_unit_with_retry` catches only `TransientScanError`, so
`ScanCancelled` is neither retried nor counted toward the breaker, and the `as_completed` loops
`break` on `cancel_event.is_set()` before `.result()`. `request_cancel()` (`tui/scanner.py:58`) still
sets `_cancel_event` before `terminate_active()` — ordering invariant preserved; the only
`tui/scanner.py` change on the branch is Task 2's import relocation, not a Task 3 edit. Ran
`uv run ruff check` on both changed files → all checks passed; scoped tests → 24 passed;
`uv run pytest` (full) → 454 passed. No `# ponytail:` markers in the touched files (nothing to strip).

**Decisions Made**: [APPROVE]. Every Task 3 success criterion met; guards verifiably precede folder
and subprocess creation in all three methods; un-cancelled path byte-for-byte unchanged; retry /
circuit-breaker / `request_cancel` ordering untouched; both gates green.

**Code Reviewed**:
- `hardware-agent/src/agent/scanner/nmap.py`
- `hardware-agent/src/agent/scanner/errors.py`
- `hardware-agent/src/agent/scanner/stages.py`
- `hardware-agent/src/agent/tui/scanner.py`
- `hardware-agent/tests/unit/test_cancel_before_spawn.py`

---

## Task 4 — agent-developer — Retention fix: `prune_logs` groups by scan

**Order Given**: Rewrite `prune_logs` in `scanner/workspace.py` to count scans, not folders, and
always protect the most recent failed/partial run. New signature
`prune_logs(logs_dir, max_scans=10, *, protected=frozenset())`. Read each run folder's `meta.json`
for `parent_scan_id` / `terminated_by`; group by `parent_scan_id` (legacy = singleton); order groups
by newest folder name; keep newest `max_scans` groups, delete older; always retain the most recent
group containing a folder whose `terminated_by ∈ {"timeout","error","user_cancel"}`; never delete
`protected` dirs; never raise (runs in a `finally`) — wrap each per-folder meta read in try/except,
treat missing/malformed meta as an ungrouped singleton. Leave `prune_results` untouched.

**What, How, and Why**: Replaced the flat folder-FIFO body with per-scan grouping. Added a tiny
`_read_run_meta(run_dir)` helper that parses `meta.json` inside a `try/except Exception` and returns
`(parent_scan_id, terminated_by)` or `(None, None)` on any failure — the "never raise" requirement
is strong here because the function runs in `run_xml`'s `finally`, and a malformed/mid-write/absent
meta must degrade to an ungrouped singleton rather than mask the real run result. Folders are grouped
by `parent_scan_id`; folders lacking one (legacy or unreadable meta) key on their own `Path`, making
each a distinct singleton group. Groups are ordered newest-first by their max folder basename
(basenames are timestamp-prefixed via `make_run_folder_name`, so name-sort ≈ time-sort). The newest
`max_scans` groups are kept; then the most recent group flagged failed/partial (any member with
`terminated_by` in the failure set) is force-added to the keep set even if it fell outside the window.
Every folder of a non-kept group is `rmtree`'d unless it is in `protected`. Reused stdlib `json` /
`shutil` already imported; no new dependency, no parallel path.

**Decisions Made**:
- Module-level `_FAILED_TERMINATED_BY = frozenset({"timeout", "error", "user_cancel"})` constant so
  the failure taxonomy has one source of truth in this module.
- `except Exception` (not a bare `except`) in `_read_run_meta` — broad on purpose to cover
  `OSError` (missing file), `json.JSONDecodeError`/`ValueError` (partial/empty JSON), and
  `AttributeError` (meta parsed to a non-dict), all of which must resolve to a singleton.
- Singleton grouping keys on the folder `Path` object (not its name) so legacy/unreadable folders
  never collide with each other or with a real `parent_scan_id`.
- Kept `protected` as `frozenset[Path] = frozenset()` (immutable default, matches requested
  signature) instead of the old `None`-sentinel — ruff clean, no `B008`.
- Left `prune_results` and every other function byte-for-byte unchanged.
- The sole production caller `LoggedNmapRunner.run_xml` passes `protected=` by keyword and no
  positional count, so the `max_count`→`max_scans` rename does not touch it — verified by grep. The
  existing `TestPruneLogs` unit tests still call `max_count=` and will be updated by the
  test-engineer (out of Task 4's target files).
- No orchestrator/runner parameter added, so the CLAUDE.md integration rule is vacuously satisfied.

**Code Changed**:
- Modified: `hardware-agent/src/agent/scanner/workspace.py`

---

## Task 4 — test-engineer

**Order Given**: Update/extend `TestPruneLogs` in `hardware-agent/tests/unit/test_workspace.py`
for the rewritten `prune_logs(logs_dir, max_scans=10, *, protected=frozenset())`. Replace the
now-removed `max_count=` kwarg with `max_scans=` in every existing call, and add tests for the new
grouping semantics: (1) grouping counts scans not folders, (2) a failed/partial scan survives a
later completed scan that pushes it outside the window, (3) malformed/missing `meta.json` never
raises and is treated as a singleton, (4) `protected` dirs are never deleted. Mirror existing
fixtures; no comments/docstrings; assert behaviour. Run
`uv run pytest hardware-agent/tests/unit/test_workspace.py` green.

**What, How, and Why**:
- Renamed all eight `TestPruneLogs` calls from `max_count=` to `max_scans=`; left `TestPruneResults`
  on `max_count=` (its signature is unchanged, Task 4 out of scope).
- Added a `_make_run_dir` helper (mirrors the existing hand-built `_make_run_dirs` style) that
  writes a timestamp-prefixed, time-sortable folder plus a `meta.json` in one of four states:
  `valid` (with `parent_scan_id`/`terminated_by`), `malformed` (partial JSON), `empty`, or `none`
  (no meta file). Chose direct `json.dumps` over `write_meta_json` for control over the malformed/
  empty/missing cases and to keep only the two grouping fields `prune_logs` actually reads.
- New tests:
  - `test_grouping_counts_scans_not_folders` — 3 scans × 2 folders (6 folders), `max_scans=2`;
    asserts the oldest whole scan's two folders are evicted and 4 folders (2 scans) remain — a
    folder-FIFO of 2 would have left 2, so this proves scans are the unit.
  - `test_failed_scan_survives_later_completed_scans` — oldest scan `terminated_by="error"` then 3
    newer completed scans, `max_scans=2`; asserts the failed scan survives outside the window while
    the oldest completed scan (also outside the window) is evicted.
  - `test_failed_scan_all_folders_survive` — a failed scan with two folders (one `completed`, one
    `timeout`) survives as a unit under `max_scans=1`.
  - `test_malformed_meta_does_not_raise` — malformed + empty + missing meta folders under the limit;
    asserts no exception and all survive.
  - `test_malformed_meta_treated_as_singleton` — a malformed-meta folder evicts an older real
    2-folder scan under `max_scans=1`, proving the malformed folder is its own singleton group.
  - `test_protected_grouped_dirs_never_deleted` — protects one folder of an out-of-window scan;
    asserts it survives while its unprotected sibling is deleted.

**Decisions Made**:
- Rewrote the pre-existing `test_skips_protected_directories`: under the OLD FIFO it encoded
  "protected folders still count toward the limit so others get evicted to reach N". The new
  semantics simply exempt `protected` from deletion (they do not force extra evictions), so the old
  assertion `not dirs[2].exists()` / `len == 10` was no longer true (all 12 survived). Retargeted it
  to protect only `dirs[0]` (out of the newest-10 window) and assert it survives while the
  unprotected out-of-window `dirs[1]` is deleted — same intent (protected exemption), expressed
  under the grouping model.
- Mocking boundary: none needed — `prune_logs` is pure filesystem; tests use real `tmp_path` dirs,
  mirroring the existing suite.
- Skipped a raise-injection test (e.g. patching `shutil.rmtree`): the "never raises" guarantee for
  meta reads is covered by the malformed/empty/missing cases, and forcing `rmtree` to throw would
  test `shutil`, not `prune_logs`.

**Code Changed**:
- Modified: `hardware-agent/tests/unit/test_workspace.py`

---

## Task 4 — code-reviewer — [REJECT]

**Order Given**: Authoritative review gate for Task 4 (spec 011) — verify the `prune_logs`
per-scan-grouping rewrite against the Task 4 success criteria and ARCHITECTURE decision 4:
exact signature, group-by-`parent_scan_id`, most-recent failed/partial group always retained,
never-raise on missing/malformed `meta.json` (try/except confirmed by reading code), `protected`
never deleted, `prune_results` untouched, sole caller passes `protected=` by keyword. Adjudicate
the retargeted `test_skips_protected_directories` (protected exempt-but-not-counted). Run
`uv run pytest` (full suite) and `uv run ruff check`.

**What, How & Why**: Read the rewritten `prune_logs` / `_read_run_meta` / `_FAILED_TERMINATED_BY`
and the updated `TestPruneLogs`. The production logic satisfies every Task 4 criterion in
isolation. Adjudication: ARCHITECTURE decision 4 defines retention purely on group count and lists
`protected` only as a never-delete overlay ("still never deleted — unchanged"), never as a
window-counting participant — so exempt-but-not-counted IS spec-sanctioned and the
`test_workspace.py::test_skips_protected_directories` retarget is acceptable. HOWEVER the same
semantic change broke a sibling integration test that was not updated: the full suite is red.
Gates: `uv run ruff check` on both changed files → all checks passed;
`uv run pytest tests/unit/test_workspace.py` → 63 passed; `uv run pytest` (full) →
**1 failed, 459 passed** —
`test_logged_runner.py::TestLoggedNmapRunnerConcurrentPrune::test_prune_skips_in_flight_run_directory`
asserts `len(run_dirs) == 10` but now gets 11. Old FIFO counted the protected in-flight dir toward
`max_count` (excess=2 → 2 evicted → 10 remain); the new group model keeps the newest 10 singletons
plus the exempt protected dir (only the single oldest unprotected dir is evicted → 11 remain). The
Task 4 changeset altered protected-counting without updating this second prune_logs test call-site.

**Decisions Made**: [REJECT]. Sole blocker is the full-suite failure — never approve with a failing
test. Fix is test-only and mirrors the already-accepted `test_workspace.py` retarget: update
`test_logged_runner.py::TestLoggedNmapRunnerConcurrentPrune::test_prune_skips_in_flight_run_directory`
to the new exempt-but-not-counted semantics (assert 11 remaining; protected dir survives, only the
oldest unprotected singleton evicted). Production `prune_logs` is spec-correct and needs no change.

**Code Reviewed**:
- `hardware-agent/src/agent/scanner/workspace.py`
- `hardware-agent/tests/unit/test_workspace.py`
- `hardware-agent/tests/unit/test_logged_runner.py`
- `hardware-agent/src/agent/scanner/nmap.py` (caller site verified)

---

## Task 4 — agent-developer — Fix stale second `prune_logs` test call-site

**Order Given**: Fix exactly the blocker from the Task 4 `[REJECT]` — the second stale
FIFO-era assertion in `test_logged_runner.py::TestLoggedNmapRunnerConcurrentPrune::
test_prune_skips_in_flight_run_directory` (lines 191-218), which still expects
`len(run_dirs) == 10`. Do not touch production `prune_logs` (already confirmed correct) or
`test_workspace.py`.

**What, How, and Why**: The test builds 1 protected `slow_dir` + 10 completed singleton
folders, then `run_xml` adds 1 more folder before `prune_logs` runs — 11 unprotected folders
total. Under the new exempt-but-not-counted model the window keeps the newest 10 unprotected
folders and `slow_dir` is exempt on top, so only the single oldest unprotected folder
(`2026-05-02-10-00-00-old-aa00`, the `i=0` iteration) is evicted, leaving 11 folders total —
matching the same math already accepted in `test_workspace.py::test_skips_protected_directories`.
Changed the assertion from `len(run_dirs) == 10` to `len(run_dirs) == 11` and added an explicit
`assert not (logs_dir / "2026-05-02-10-00-00-old-aa00").exists()` so the test also pins which
specific folder was evicted, not just the count. Left the `slow_dir.exists()` and
`console.log` content assertions (protected-dir intent) and the `-nse-` new-folder assertion
untouched.

**Decisions Made**:
- Asserted the exact evicted folder name rather than only bumping the count, to keep the test's
  original intent legible (protected dir survives; the new grouping model evicts by oldest
  unprotected singleton, not by raw folder-FIFO).
- No production code touched — reviewer already confirmed `prune_logs` is spec-correct; this is
  a test-only fix for the second stale call-site the earlier test-engineer pass missed.
- No other test file touched.

**Code Changed**:
- Modified: `hardware-agent/tests/unit/test_logged_runner.py`

---

## Task 4 — code-reviewer — [APPROVE] (re-review after test-only fix)

**Order Given**: Re-review Task 4 after the prior `[REJECT]` blocker — the stale FIFO-era
assertion in `test_logged_runner.py::TestLoggedNmapRunnerConcurrentPrune::
test_prune_skips_in_flight_run_directory`. Confirm the fresh coder applied exactly the prescribed
test-only fix (assert `== 11`, only the oldest unprotected singleton evicted), touched no
production code and no other test, and that the gate is now green. Re-run `uv run pytest` (full)
and `uv run ruff check`.

**What, How & Why**: `git diff` confirms the only change to `test_logged_runner.py` is the
prescribed one — `assert len(run_dirs) == 10` → `== 11` plus an added
`assert not (logs_dir / "2026-05-02-10-00-00-old-aa00").exists()` pinning the single evicted
folder; production `prune_logs` and every other test untouched. The production rewrite was already
verified spec-correct in the prior pass (signature, per-scan grouping, most-recent failed group
always retained, never-raise try/except on missing/malformed meta, protected never deleted,
`prune_results` untouched, sole caller passes `protected=` by keyword) and the exempt-but-not-counted
adjudication (sanctioned by ARCHITECTURE decision 4) stands. Gates: `uv run ruff check` on the
changed workspace/test files → all checks passed; `uv run pytest` (full) → **460 passed**. Grep for
`# ponytail:` across the package `*.py` → none, so nothing to strip.

**Decisions Made**: [APPROVE]. The sole prior blocker (full-suite failure from the un-updated
second prune_logs test call-site) is resolved by a minimal, spec-consistent test-only edit; full
suite green, ruff clean, no ponytail markers.

**Code Reviewed**:
- `hardware-agent/src/agent/scanner/workspace.py`
- `hardware-agent/tests/unit/test_workspace.py`
- `hardware-agent/tests/unit/test_logged_runner.py`
- `hardware-agent/src/agent/scanner/nmap.py` (caller site)

---

## Task 5 — agent-developer — Metadata fix: honest `nmap_arguments_summary` for NSPi

**Order Given**: Special-case `scan_mode == "nspi"` in `nmap_arguments_summary`
(`scanner/stages.py`) so the `ports=` clause describes the two passes NSPi actually runs
instead of `discovery_arguments("nspi")` (which wrongly reports `--script` plus a single
`-T4`); target form `pass1:-Pn -T4 -n -sV -O (top-1000); pass2:-Pn -T2 -n -p
502,4840,44818,445,139,3389,5985 -sV`; must not contain `--script`; every other mode's
`ports=` clause byte-for-byte unchanged.

**What, How & Why**: Added an `if settings.scan_mode == "nspi"` branch at the top of
`nmap_arguments_summary` that builds `port_stage` as a literal string describing both NSPi
passes, using the existing `NSPI_PORTS` constant (imported from `agent.config`, already the
comma-joined string `"502,4840,44818,445,139,3389,5985"` used by `_scan_ports_batch_nspi`) so
the port list has one source of truth. The `else` branch keeps the prior computation
(`" ".join(discovery_arguments(settings.scan_mode))` plus the trailing `-Pn -T4`) so every
other mode's rendered clause is identical to before. Only the local `port_stage` variable and
the format string's `-Pn -T4` suffix (now folded into each branch) changed; the surrounding
`discovery=...`/`deep_inspection=...`/`scripts=...` fragments are untouched.

**Decisions Made**:
- Reused `NSPI_PORTS` from `agent.config` rather than hardcoding the digit string a second
  time, keeping pass 2's port list order tied to the same constant `_scan_ports_batch_nspi`
  uses.
- Moved the trailing `-Pn -T4` into the non-NSPi branch's `port_stage` value (instead of
  appending it in the shared return line) so the NSPi branch can render its own two-pass
  string without a stray `-Pn -T4` tacked onto the end; verified this produces byte-for-byte
  identical output for quick/standard/extensive/max via the existing
  `test_nmap_arguments_summary.py` suite (3 passed, unmodified).
- No orchestrator/runner parameter added, so the CLAUDE.md integration rule is vacuously
  satisfied — nothing to thread through `ScanRunner`/`ScanProgressScreen`.

**Code Changed**:
- Modified: `hardware-agent/src/agent/scanner/stages.py`

---

## Task 5 — test-engineer

**Order Given**: Extend `test_nmap_arguments_summary.py` to assert the NSPi summary's `ports=`
clause contains `pass1:-Pn -T4` and the exact substring
`pass2:-Pn -T2 -n -p 502,4840,44818,445,139,3389,5985 -sV`, and does not contain `--script`; confirm
quick/standard/extensive/max clauses are unchanged. Mirror the existing file's patterns; no
comments/docstrings.

**What, How, and Why**: Added `test_nspi_port_stage_describes_both_passes`, asserting `"pass1:-Pn
-T4" in summary`, the exact `pass2:-Pn -T2 -n -p 502,4840,44818,445,139,3389,5985 -sV` substring,
and `"--script" not in summary`, mirroring the file's existing one-call-one-assert-block style
(`nmap_arguments_summary(AgentSettings(scan_mode=...))` then `in`/`not in` checks). The existing
`test_extensive_uses_top_ports_no_port_stage_script`, `test_max_uses_all_ports_min_rate`, and
`test_quick_port_stage_unchanged` tests already pin quick/extensive/max byte-for-byte and still pass
unmodified, proving the NSPi branch did not perturb them. `standard` had no existing coverage in this
file (ARCHITECTURE's testing table names it alongside quick/extensive/max as "unchanged"), so I added
`test_standard_port_stage_unchanged` asserting the `--script <csv>` + `-Pn -T4` shape is present,
closing that gap rather than leaving it implicit.

**Decisions Made**:
- Asserted the NSPi pass2 substring exactly (not just presence of pieces) since `NSPI_PORTS`'s
  ordering is load-bearing and the success criteria specify the literal string.
- Added a `standard` mode test since it was named in ARCHITECTURE's acceptance row but absent from
  the file; kept it loose (`--script ` prefix + `-Pn -T4` presence) rather than asserting the full
  NSE script CSV, since that list is `config.py`'s concern, not this summary function's.
- No production code changed; no testability hook needed.

**Code Changed**:
- Modified: `hardware-agent/tests/unit/test_nmap_arguments_summary.py`

---

## Task 5 — code-reviewer — [APPROVE]

**Order Given**: Authoritative review gate for Task 5 (spec 011). Verify the NSPi `ports=`
clause contains `pass1:-Pn -T4` and the exact substring
`pass2:-Pn -T2 -n -p 502,4840,44818,445,139,3389,5985 -sV` and does NOT contain `--script`,
using the real `NSPI_PORTS` config constant (not a hardcoded list); only the NSPi branch is
special-cased so quick/standard/extensive/max `ports=` clauses are byte-for-byte unchanged; the
change is surgical. Run `uv run pytest` (full) and `uv run ruff check`.

**What, How & Why**: Read `stages.py` and its `git diff HEAD`. The NSPi branch renders
`pass1:-Pn -T4 -n -sV -O (top-1000); pass2:-Pn -T2 -n -p {NSPI_PORTS} -sV` where `NSPI_PORTS`
is imported from `agent.config` and equals `"502,4840,44818,445,139,3389,5985"` (grep-confirmed
at `config.py:72`), so the rendered pass 2 substring is exact and the port list has one source
of truth rather than a drift-prone literal. The clause has no `--script`. The diff shows the
shared `-Pn -T4` suffix was moved out of the return line into the `else` branch's `port_stage`,
making non-NSPi output byte-for-byte identical (`ports=<discovery_arguments> -Pn -T4`) — confirmed
by the unmodified quick/extensive/max tests plus the added `standard` test all passing. Only the
NSPi branch and the relocated suffix changed; surrounding `discovery=`/`deep_inspection=`/
`scripts=` fragments untouched. No orchestrator/runner parameter added, so the CLAUDE.md
integration rule is vacuously satisfied. Gates: `uv run ruff check` on both changed files → all
checks passed; `uv run pytest` (full) → 462 passed. Grep for `# ponytail:` across the package
`*.py` → none, so nothing to strip.

**Decisions Made**: [APPROVE]. Every Task 5 success criterion met; the NSPi clause is honest and
uses the canonical constant; other modes' clauses are byte-for-byte unchanged; the change is
surgical; both gates green.

**Code Reviewed**:
- `hardware-agent/src/agent/scanner/stages.py`
- `hardware-agent/src/agent/config.py` (NSPI_PORTS constant, verified)
- `hardware-agent/tests/unit/test_nmap_arguments_summary.py`

---

## Task 6 — agent-developer — S4 elapsed-time heartbeat + responsive cancelling banner

**Order Given**: In `tui/screens/scan_progress.py` only: on `port_stage_started` record a
`_port_stage_started_at` timestamp and the mode-aware base label; have the `_tick` path
(`_refresh_active_stage_lines`) append a live `{m}m {s}s` (or `{s}s` under a minute) elapsed
counter to the active `ports` line; add a `port_batch_done` branch to
`on_scan_progress_screen_progress_updated` folding in a coarse `(batch N/M)` structure, with the
bar advancing only on `port_batch_done`, never on a tick; extend `_enter_cancelling` to show
`#scan-badge` with the exact `CANCELLING` banner copy and the new `Stopping scan — saving partial
results…` activity-log line, leaving `_active_stages` populated so the spinner keeps animating. No
new event/field/id/binding/CSS; both TUI call sites (`ScanRunner` at `scan_progress.py:131`,
`ScanProgressScreen` at `home.py:74`) must stay unchanged.

**What, How & Why**: Added four `__init__` fields (`_port_stage_started_at`, `_port_base_label`,
`_port_batches_done`, `_port_batches_total`) alongside the existing `_active_stages`/
`_stage_lines` state. `port_stage_started` now computes the mode-aware base label into
`_port_base_label`, stamps `monotonic()`, resets the batch counters, and starts the stage with the
base label (so the pre-first-tick line reads exactly `⠙ Scanning ports…`, matching DESIGN's first
table row). Added two small helpers, `_format_elapsed` (stdlib `divmod`, no new dependency) and
`_port_stage_label` (composes `{base} ({elapsed})` or `{base} (batch {done}/{total} · {elapsed})`
per the DESIGN Change 1 table), placed next to the existing `_spinner_line`/`_refresh_active_stage_lines`
so the pattern reads as one family. `_refresh_active_stage_lines` — the existing `_tick`-driven
repaint path — now recomposes `_active_stages["ports"]` via `_port_stage_label()` before the
existing per-stage spinner-repaint loop runs, so the elapsed counter rides the pre-existing
spinner-repaint mechanism with zero new rendering path and never touches `#progress-bar`. A new
`port_batch_done` branch stores `event.batches_done`/`event.batches_total` and immediately
recomposes+repaints the same line so the batch structure appears without waiting for the next
tick; the bar itself was already driven unconditionally by the existing
`self._target_pct = self._mapper.update(event)` line at the top of the handler (unchanged), so no
separate bar-advance code was needed — `port_batch_done` already updates `_target_pct` via
`ProgressMapper`, and `_tick`'s separate interpolation-toward-target loop (also unchanged) is the
only thing that paints the bar. `_enter_cancelling` was extended with the `#scan-badge` update
(`display = True` + exact `[black on yellow] CANCELLING [/] saving partial results…` copy) before
the existing `request_cancel()` call, and the activity-log line copy was swapped to the exact new
`Stopping scan — saving partial results, no new probes will start…` string; `_active_stages` is
untouched (not cleared) so the ports/scripts spinner keeps animating, and the existing
`if self._state == "cancelling": return` guard in `action_abort` was left as-is (unmodified) so a
second `ctrl+x` remains an idempotent no-op.

**Decisions Made**:
- Recomposed `_active_stages["ports"]` in place (mutating the dict entry each tick/batch-event)
  rather than introducing a parallel "current label" concept, since `_refresh_active_stage_lines`
  and `_finish_stage` already key off that dict — reusing it kept the diff to the smallest surface
  and meant `_finish_stage("ports", ...)` (unchanged) naturally stops the elapsed counter by
  popping the stage out of `_active_stages` on `port_stage_done`, with no extra "stop the timer"
  code needed.
- Did not guard `_port_stage_label()` against `_port_stage_started_at is None` inside the
  `port_batch_done` branch: pipeline ordering guarantees `port_stage_started` always precedes
  `port_batch_done` for the same stage (verified against `stages.py`'s port-stage emission order),
  so an extra None-check would be defensive code for an unreachable state — the `_refresh_active_stage_lines`
  tick path does carry a `is not None` guard because it runs on an unconditional interval timer that
  can fire before the first `port_stage_started` of a scan.
- Left `_port_stage_started_at` unset (not reset to `None`) on `port_stage_done`; the next
  `port_stage_started` always reassigns it before the "ports" stage becomes active again, and no
  code path reads it while "ports" is absent from `_active_stages`, so an explicit reset would be
  inert.
- Did not touch the pre-existing `test_abort_while_running_enters_cancelling` test, which now fails
  against the old `"terminating running steps…"` copy assertion — DESIGN Change 2 explicitly
  replaces that copy, the test file is outside this task's scope
  (`tui/screens/scan_progress.py` only), and updating the mirrored assertion is the test-engineer's
  job per the pipeline's task split.
- No orchestrator/runner parameter, `ScanEvent` field, widget id, binding, or CSS rule added; the
  two TUI call sites (`ScanRunner(...)` at `scan_progress.py:131`, `ScanProgressScreen(...)` at
  `home.py:74`) were grepped and confirmed unchanged — nothing to thread per CLAUDE.md.

**Code Changed**:
- Modified: `hardware-agent/src/agent/tui/screens/scan_progress.py`

---

## Task 6 — test-engineer

**Order Given**: Update/extend `hardware-agent/tests/unit/test_scan_progress_screen.py` for the
Task 6 change to `tui/screens/scan_progress.py` only: (1) fix
`test_abort_while_running_enters_cancelling` (and any other test asserting the old `terminating
running steps…` copy) to the new `#scan-badge` CANCELLING banner + new stopping-line copy while
keeping its cancelling-state/`request_cancel`/spinner-animating intent; (2) add a sub-batch
progress test that sends `port_stage_started`, advances the `_tick` clock past a threshold with no
`port_batch_done`, and asserts the active `ports` line's elapsed counter grew while `#progress-bar`
did not move; (3) add a batch-counter test asserting a `port_batch_done` line contains `batch N/M`
and the bar advanced. Control the clock deterministically (no real sleeps); no comments/docstrings;
run the file green.

**What, How, and Why**: Read the actual `_format_elapsed`/`_port_stage_label`/`_tick` implementation
in `scan_progress.py` rather than trusting the DESIGN.md mockup's literal `(0m 12s)` example — the
shipped `_format_elapsed` returns bare `{s}s` under a minute (`if minutes:` is falsy for 0), so my
assertions use the code's actual output (`"(5s)"`, `"(12s)"`, `"1m 20s"`) instead of copying the
mockup string verbatim. Monkeypatched `agent.tui.screens.scan_progress.monotonic` (the exact name
bound by the module's `from time import monotonic`) to a mutable one-element list so elapsed time
advances deterministically without real sleeps, and drove `screen._tick()` directly (a plain
synchronous method) rather than waiting on the real `set_interval(0.05, ...)` timer, mirroring how
the file already drives state via direct method calls (`screen._handle_complete(...)`,
`screen._handle_error(...)`) rather than through the Textual clock.
- Fixed `test_abort_while_running_enters_cancelling`: first posts `port_stage_started` so
  `_active_stages` is non-empty going into cancel (proving the spinner-animating claim is
  falsifiable, not vacuous), then after `ctrl+x` asserts the new activity-log line
  (`Stopping scan — saving partial results, no new probes will start…`), `#scan-badge` `display is
  True` with rendered text containing both `CANCELLING` and `saving partial results…` (using the
  existing `_badge_text` helper), and `"ports" in screen._active_stages` for the spinner-still-alive
  assertion — on top of the test's original `_state`/`_terminal()`/`request_cancel` calls/screen-not-
  dismissed assertions, all kept intact.
- Added `TestPortStageHeartbeat.test_elapsed_counter_advances_without_moving_bar_on_tick`: uses
  `scan_mode="nspi"` (so the base label is `Scanning ports…`, not `Scanning all ports…`, matching
  the substring asserted). After `port_stage_started`, calls `screen._tick()` 5 times to let the
  existing bar-interpolation loop (`_display_pct` chasing `_target_pct` in `_PCT_STEP=5.0`
  increments) fully settle at the stage's target (10.0 for nspi's discovery weight) before taking
  the "before" reading — otherwise the pre-existing catch-up animation itself would look like
  bar movement and produce a false positive for the "bar doesn't move on a tick" claim. Then advances
  the fake clock twice (+5s, +12s total) calling `_tick()` after each, asserting the log text
  contains `"(5s)"` then `"(12s)"` (proving the counter is live and growing) while `bar.progress`
  stays equal to the settled value both times.
- Added `TestPortStageHeartbeat.test_batch_done_updates_fraction_and_advances_bar`: same settle-first
  pattern, then advances the fake clock +80s and posts `port_batch_done(batches_done=3,
  batches_total=8)`, ticks a few more times to let the bar interpolate toward the new
  `port_batch_done`-computed target, and asserts the line contains `"batch 3/8"` and `"1m 20s"`
  (exercising the `>= 60s` branch of `_format_elapsed`, complementing the first test's `< 60s`
  branch) and `bar.progress > progress_before_batch`.

**Decisions Made**:
- Trusted the shipped code's `_format_elapsed` output over the DESIGN.md mockup's example string —
  the mockup is illustrative prose, the merged implementation is the contract under test; noting
  this as the resolution of an apparent doc/code mismatch rather than silently picking one.
- Mocking boundary is the module-level `monotonic` name (patched via `monkeypatch.setattr` on the
  fully-qualified module attribute), not `time.monotonic` globally — matches the file's own
  `from time import monotonic` import so only this screen's clock is faked.
- Drove `_tick()` directly instead of trying to fast-forward Textual's real interval timer, since the
  method is a plain synchronous callable and the existing test file already favors direct
  state-mutation calls over waiting on framework timers.
- Deliberately let the bar "settle" (5 manual ticks) before recording the baseline progress in both
  new tests, so the pre-existing `_PCT_STEP` catch-up animation (unrelated to this feature) can't be
  mistaken for the tick-driven movement the test is designed to rule out.
- Did not add a separate assertion for the bar holding during the *cancelling* state (mentioned in
  DESIGN's widget-ids section) since it was not one of the three items in this task's scope and the
  existing `TestProgressBarTerminal` suite already covers bar-holds-at-value-in-partial/fatal.
- No production code changed; no testability hook needed — `_tick` and `monotonic` were already
  accessible/patchable from the test module.

**Code Changed**:
- Modified: `hardware-agent/tests/unit/test_scan_progress_screen.py`

---

## Task 6 — code-reviewer — [APPROVE]

**Order Given**: Authoritative review gate for Task 6 (spec 011) — the TUI task. Verify the S4
elapsed-time heartbeat + coarse batch counter and the responsive cancelling banner in
`tui/screens/scan_progress.py` against the Task 6 success criteria, DESIGN changes 1 & 2 (copy
table, widget ids, states), and ARCHITECTURE decision 2. Confirm no new pipeline event/field/id/
binding/CSS, and that `ScanRunner` / `ScanProgressScreen` signatures are unchanged (CLAUDE.md
integration rule). Adjudicate the elapsed format (`{s}s` under a minute vs the mockup's `0m 12s`).
Run `uv run pytest` (full) and `uv run ruff check`.

**What, How & Why**: Read `scan_progress.py` and its `git diff main` — the change is confined to
that one file and to the specified regions (import `monotonic`; four `__init__` fields;
`_format_elapsed`/`_port_stage_label` helpers; the elapsed recompose in
`_refresh_active_stage_lines`; the `port_stage_started`/`port_batch_done` branches; the
`_enter_cancelling` badge + copy). `git diff main --stat` shows `progress.py`, `home.py`,
`app.tcss` untouched and the only `tui/scanner.py` change is Task 2's import relocation, so no new
event/field/id/binding/CSS was added; `port_batch_done`/`batches_done`/`batches_total` already
exist in `progress.py`. The bar advances only via `_mapper.update(event)` (set on
`port_batch_done`), never on a `_tick` — the tick path recomposes the `ports` label with elapsed
time and does not touch `#progress-bar`. `_start_scan`'s `workspace_root=` arg is pre-existing
(not in this diff), so both `ScanRunner` and `ScanProgressScreen` signatures are unchanged by Task
6 — CLAUDE.md rule satisfied. Copy verified byte-for-byte against DESIGN's table: badge
`[black on yellow] CANCELLING [/] saving partial results…` and activity line
`[yellow]● Stopping scan — saving partial results, no new probes will start…[/yellow]`.
`_active_stages` is left populated on cancel (spinner keeps animating) and the
`if self._state == "cancelling": return` guard in `action_abort` is intact. Adjudication: the
authoritative Task 6 Description and DESIGN prose (lines 73, 90) both explicitly permit bare
`{s}s` under a minute; the mockup's `(0m 12s)` is an illustrative inconsistency, so the shipped
`_format_elapsed` is correct. Gates: `uv run pytest` (full) → 464 passed; `uv run ruff check` on
both changed files → all checks passed. Grep for `# ponytail:` across `hardware-agent` → none, so
nothing to strip.

**Decisions Made**: [APPROVE]. Every Task 6 success criterion met — elapsed heartbeat advances on
ticks without moving the bar; `port_batch_done` yields `batch N/M` and advances the bar; cancel
shows the CANCELLING badge + stopping line with the spinner still alive and the idempotent
second-`ctrl+x` no-op preserved; copy is exact; no new pipeline surface; both TUI call sites
unchanged. Both gates green; the elapsed-format adjudication favors the implementation.

**Code Reviewed**:
- `hardware-agent/src/agent/tui/screens/scan_progress.py`
- `hardware-agent/tests/unit/test_scan_progress_screen.py`
- `hardware-agent/src/agent/scanner/progress.py` (event/field pre-existence, verified)
- `hardware-agent/src/agent/tui/scanner.py`, `hardware-agent/src/agent/tui/screens/home.py`, `hardware-agent/src/agent/tui/app.tcss` (call-site/CSS non-change, verified)
