# Scan Pipeline Resilience & Contingency — Design Report

**Status:** Draft for review · **Date:** 2026-06-25 · **Scope:** `hardware-agent` scan pipeline
**Author:** drafted from codebase audit (request: "define when to stop, when to keep going with errors")

---

## 1. Problem

Users report crashes, hangs, and lost results on **long-running scans** (extensive / max / large
subnets). The root cause is not a single bug — it is that the pipeline has **no contingency policy**.
Today every error is treated identically (abort the whole scan), there are **no timeouts**, and a
scan that fails late throws away everything it had already discovered.

This report maps the current behaviour, enumerates the concrete failure modes, and proposes an
explicit **stop-vs-continue policy** plus the structural changes needed to enforce it.

---

## 2. How the pipeline works today

A TUI scan runs entirely on a daemon worker thread owned by `ScanRunner._run()`
(`hardware-agent/src/agent/scanner/runner.py`). Stages run sequentially:

```
discover_hosts → run_port_stage → run_deep_inspection_stage → extract_findings → ScanPayload
```

- **Discovery** (`discovery/network_discovery.py`): one `nmap -sn` call over the subnet.
- **Port stage** (`scanner/stages.py:run_port_stage`): hosts split into batches, each batch a
  separate nmap process, run concurrently via a `ThreadPoolExecutor`.
- **Deep inspection** (`scanner/stages.py:run_deep_inspection_stage`): one nmap NSE process per host
  with open ports, again via a `ThreadPoolExecutor`.
- Each nmap call goes through `NmapRunner.run_xml()` / `LoggedNmapRunner.run_xml()`
  (`scanner/nmap.py`), which shells out to nmap and parses XML.

Cancellation: `ScanRunner._check_cancel()` raises `ScanCancelled` — but only **between** stages.

---

## 3. Failure modes found

Each is concrete and traceable to code.

### F1 — No subprocess timeout (the primary hang) 🔴
`NmapRunner.run_xml()` calls `subprocess.run(command, ...)` with **no `timeout=`**
(`scanner/nmap.py:79`). `run_streamed()` calls `proc.wait()` with **no timeout**
(`scanner/nmap.py:126`). A single nmap process that stalls — common with `-p-`, `--top-ports 10000`,
`-O`, and heavy `--script` sets on a filtered/unresponsive host — **blocks forever**. Because the
worker is a daemon thread, the TUI sits on "in progress" indefinitely with no way to recover. This
is almost certainly the #1 source of "long scans hang/crash."

### F2 — One failed unit kills the entire scan 🔴
In both stages, `future.result()` (`scanner/stages.py:62` and `:102`) re-raises any
`NmapExecutionError` from a worker. A single batch or host failing — one malformed XML response, one
script that errors, one non-zero exit — propagates up, aborts the whole stage, and fails the entire
scan. **All successful batches are discarded.** There is no per-unit isolation.

### F3 — Partial results are designed-for but never produced 🟠
`build_metadata()` already accepts `partial_result` and `interrupted_stage`
(`scanner/stages.py:166-189`), and `workspace.py:12` defines
`TerminatedBy = Literal["completed", "error", "user_cancel", "timeout"]`. **None of these are ever
emitted.** `ScanRunner` only ever builds a payload on full success; on `ScanCancelled` it just
`pass`es (`scanner/runner.py:174-175`), and `LoggedNmapRunner` only writes `"completed"` or
`"error"` (`scanner/nmap.py:188-191`). A 40-minute scan that fails in deep inspection yields
**nothing** — not even the hosts and ports already found.

### F4 — Cancellation is coarse and does not stop work 🟠
`_check_cancel()` runs only between stages. Inside the executor loops there is no cancel check, and
`request_cancel()` only sets an event — it never terminates running nmap subprocesses. The
`with ThreadPoolExecutor(...)` block **waits for all submitted futures** before returning. So
pressing Ctrl+X mid-port-stage dismisses the UI (`scan_progress.py:171-177`) while the daemon threads
and nmap processes **keep running in the background** until they finish on their own.

### F5 — No retries for transient failures 🟡
Nmap fails transiently (temporary resolve failure, ARP timeout, brief network blip). There is no
single retry anywhere; any transient blip is fatal to its unit (and via F2, to the whole scan).

### F6 — No error taxonomy: fatal and tolerable are identical 🟠
Every failure is a bare `NmapExecutionError` (`scanner/nmap.py:24`). "nmap not found" (truly
fatal — should stop instantly) is indistinguishable from "one host returned non-zero" (tolerable —
should skip and continue). Without a taxonomy there is nothing to base a stop/continue decision on.

### F7 — No scan-wide wall-clock budget 🟡
extensive/max scans have no overall deadline and no graceful "stop and keep what we have." They run
until done or until something hangs (F1).

### F8 — Connectivity checked once, at the start 🟡
`check_network_connectivity()` runs once (`scanner/runner.py:87`). If the network drops mid-scan,
every subsequent nmap call fails and the scan collapses (amplified by F2).

---

## 4. The core gap: no stop / continue policy

The request is exactly right: we must **define when to stop vs. when to keep going with errors.**
Today the implicit policy is *"any error anywhere stops everything, and we keep nothing."* The
proposal below replaces that with an explicit, testable policy.

### 4.1 Error taxonomy

Introduce error classes (subclasses of a base `ScanError`) so each failure carries its policy:

| Class | Examples | Meaning |
|-------|----------|---------|
| `FatalScanError` | nmap binary not found; invalid args; raw-socket permission denied; workspace not writable | Scan cannot meaningfully proceed |
| `UnitScanError` | one batch/host: non-zero exit, malformed XML, NSE script crash, per-host timeout | A single work item failed; others are unaffected |
| `TransientScanError` | temporary resolve failure, transient network error | Likely to succeed on retry |
| `Cancelled` | user pressed abort | User asked to stop |
| `BudgetExceeded` | per-host timeout or scan wall-clock deadline hit | Resource limit reached |

### 4.2 Decision table — the heart of the policy

| Situation | Decision | What we keep |
|-----------|----------|--------------|
| `FatalScanError` **before** any data | **STOP immediately** | Nothing; clear error to user |
| `FatalScanError` **after** discovery (e.g. network lost mid-scan, F8) | **STOP**, but emit partial | Hosts/ports gathered so far, `partial_result=True` |
| `TransientScanError` on a unit | **RETRY once** (short backoff); still failing → demote to `UnitScanError` | — |
| `UnitScanError` on a single batch/host | **CONTINUE** with remaining units; record failure in metadata | All successful units |
| Unit failure rate exceeds threshold (e.g. >50% of batches) | **STOP** (circuit breaker — environment is broken) | Everything succeeded so far, `partial_result=True` |
| Discovery returns 0 hosts | **CONTINUE** (not an error) — skip downstream, finish empty | Empty but valid result (already handled) |
| `Cancelled` (Ctrl+X) | **STOP launching new work, kill running subprocesses**, finalize partial | Everything up to the cancel point, `interrupted_stage=<stage>` |
| `BudgetExceeded` (per-host or scan deadline) | Treat like cancel: stop, keep partial | Partial, `partial_result=True`, `interrupted_stage` set |

Guiding principle: **stop only when continuing is pointless (fatal) or destructive (environment
broken / user asked / budget hit). Otherwise degrade gracefully and always preserve partial work.**

---

## 5. Structural changes to enforce the policy

These are the minimal mechanisms the policy depends on. (Implementation detail for a follow-up spec —
listed here so the policy is grounded in something buildable.)

1. **Per-invocation subprocess timeouts (fixes F1).** Add a `timeout=` to `subprocess.run` and a
   `proc.wait(timeout=...)` to `run_streamed`; on expiry, `proc.kill()` and raise `BudgetExceeded`
   (mapped to `terminated_by="timeout"`, which the schema already supports). Timeout scaled per
   stage/mode (discovery short; deep inspection longer; max mode longest).

2. **Per-unit isolation in the executor loops (fixes F2).** Wrap each `future.result()` in
   try/except. On `UnitScanError`/`BudgetExceeded`, log, record the failed ip/batch, and continue.
   Never let one unit abort the stage.

3. **Failure accounting + circuit breaker (fixes F2 escalation).** Count failed vs. total units per
   stage; if the failure ratio crosses a threshold, stop the scan (broken environment) instead of
   grinding through hundreds of guaranteed failures.

4. **One retry for transient errors (fixes F5).** In the per-unit wrapper, retry a
   `TransientScanError` once before demoting it to a unit failure.

5. **Real cancellation (fixes F4).** Check the cancel event inside the executor loops; on cancel,
   stop submitting new work and `proc.kill()` in-flight subprocesses (track live `Popen` handles).

6. **Partial-result finalization (fixes F3).** Refactor `ScanRunner._run()` so the
   payload-building/`on_complete` path is reachable from cancel, timeout, and post-discovery-fatal
   paths — setting `partial_result=True` and `interrupted_stage`. The `_handle_error` path in
   `scan_progress.py:161-163` should preserve and offer the partial payload instead of dismissing
   with `None`.

7. **Error taxonomy (fixes F6).** Replace the single `NmapExecutionError` with the classes in §4.1,
   so `run_xml` raises the right type and call sites can branch on policy.

8. **Optional: scan wall-clock budget (fixes F7).** A deadline checked between units; on expiry,
   behave like cancel (stop, keep partial).

---

## 6. Surfacing contingency to the user

- Progress screen should show degraded outcomes, e.g. `✓ Scanning ports (3 of 20 hosts skipped)`,
  not a silent success or a hard failure.
- A partial/timed-out/cancelled scan must be **viewable and savable**, clearly badged "Partial".
- `scan_progress.py:_handle_error` should distinguish *fatal* (show error, nothing to keep) from
  *partial* (offer "View partial scan").

---

## 7. Suggested config knobs

Add to `AgentSettings` (`config.py`), with conservative defaults; tune per mode:

| Setting | Purpose | Suggested default |
|---------|---------|-------------------|
| `subprocess_timeout_s` | per-nmap-call timeout | per-stage (e.g. discovery 120s, deep 600s) |
| `scan_deadline_s` | overall wall-clock budget | 0 = unlimited (set for max mode) |
| `unit_failure_threshold` | circuit-breaker ratio | 0.5 |
| `transient_retries` | retries per unit | 1 |

---

## 8. Suggested phasing

1. **P1 — Stop the hangs:** subprocess timeouts + kill on timeout (F1). Highest impact, smallest
   change.
2. **P2 — Stop losing everything:** per-unit isolation + partial-result finalization (F2, F3).
3. **P3 — Honest cancellation:** real subprocess termination + in-loop cancel checks (F4).
4. **P4 — Polish:** error taxonomy, retries, circuit breaker, wall-clock budget (F5–F8).

P1+P2 alone should resolve the bulk of the reported "crashes/bugs on long scans."

---

## 9. Open questions

- **Per-host timeout values:** should they be fixed, or derived from scan mode / port count?
- **Circuit-breaker threshold:** 50% reasonable, or mode-dependent?
- **Partial results to backend:** does the ingest contract / backend accept `partial_result=True`
  payloads, or must partial scans stay local only? (Needs a contract check — out of agent scope.)
- **Integration rule (CLAUDE.md):** any new `AgentSettings` field or `ScanRunner` parameter must be
  threaded through `ScanRunner` **and** `ScanProgressScreen` — verify all call sites when implementing.
```
