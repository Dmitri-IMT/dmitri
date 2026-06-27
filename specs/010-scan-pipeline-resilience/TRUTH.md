# TRUTH — Scan Pipeline Contingency Policy (stop vs. continue on errors)

Domain language and verifiable behaviour only. No file paths, no nmap flags, no code.

Source: GitHub issue #81. Full audit and proposed policy:
`docs/implementation/SCAN-PIPELINE-RESILIENCE.md`.

## Narrative

Long-running scans (extensive / max / large subnets) crash, hang, or silently lose every
result. The pipeline has no contingency policy: there are no scan-step timeouts, a single
failed work item aborts the entire scan, and a scan that fails late discards everything it
had already discovered. A user who waits forty minutes for a deep scan can end up with a
frozen screen or an empty result and no explanation.

This feature defines and enforces an explicit **stop-vs-continue policy**: classify each
failure, decide whether it should abort the scan or be tolerated, and always preserve the
work already done. The guiding principle is: **stop only when continuing is pointless
(unrecoverable), destructive (the environment is broken), the user asked to stop, or a
resource budget is exhausted. Otherwise degrade gracefully and keep partial results.**

## Domain language

- **Work item / unit** — the smallest independently-runnable piece of a scan stage (one host
  batch during port enumeration; one host during deep inspection). Units within a stage are
  independent of each other.
- **Partial result** — a scan outcome that did not complete every stage but still carries the
  hosts, ports, and findings gathered before it stopped. It is a valid, viewable, savable
  outcome, clearly badged "Partial", never silently discarded.
- **Terminal state** — how a scan ended: completed, error, user-cancelled, or timed-out.
- **Failure taxonomy** — every failure is classified as exactly one of:
  - **Fatal** — the scan cannot meaningfully proceed (e.g. scanning tool missing, invalid
    arguments, permission denied, workspace not writable).
  - **Unit** — a single work item failed; other units are unaffected.
  - **Transient** — likely to succeed on a retry (temporary resolution / network blip).
  - **Cancelled** — the user asked to stop.
  - **Budget exceeded** — a per-item or scan-wide time limit was reached.
- **Circuit breaker** — when the proportion of failed units in a stage crosses a threshold,
  the environment is treated as broken and the scan stops, keeping what succeeded.

## Business rules

- A single scan step that stalls must not block the scan forever; it is bounded by a timeout,
  after which the step is terminated and recorded as a budget/timeout failure.
- A single unit failure must never abort its stage. The failure is recorded and the remaining
  units continue.
- A transient failure on a unit is retried once before it is demoted to a unit failure.
- When the unit failure rate in a stage exceeds the configured threshold, the scan stops
  (circuit breaker) and preserves everything gathered so far as a partial result.
- A fatal failure **before** any data exists stops the scan immediately with a clear error and
  nothing to keep. A fatal failure **after** discovery stops the scan but emits a partial
  result.
- Cancellation stops launching new work, terminates in-flight scan subprocesses, and finalizes
  a partial result recording the stage that was interrupted. Cancellation must actually halt
  work, not merely dismiss the screen while background work continues.
- Discovery returning zero hosts is not an error; downstream stages are skipped and the scan
  finishes with a valid empty result.
- Any partial / timed-out / cancelled scan is finalized with the partial flag set and the
  interrupted stage recorded, and is surfaced to the user as a viewable, savable outcome.
- The per-step timeout is lenient and varies by scan mode and stage — it is a safety net against
  a single stalled step, not a limit on how long a normal scan may take (a quick scan on a network
  with many hosts may legitimately run a while). The other tuning knobs (scan deadline, unit-failure
  threshold, transient retries) have conservative defaults. A TUI-initiated scan honors all of them
  exactly as a non-TUI scan would.

## User stories

1. As an operator running a deep scan over a large subnet, I want a stalled scan step to be
   bounded by a timeout, so that the scan never hangs forever and I am told a step timed out.
2. As an operator, I want one failed host or batch to be skipped rather than fail the whole
   scan, so that a single bad host does not waste the entire run.
3. As an operator whose scan stopped early (cancel, timeout, or late fatal error), I want to
   keep and view the hosts and ports already discovered, so that the time spent is not lost.
4. As an operator, I want pressing abort to actually stop the running scan promptly, so that
   nothing keeps scanning the network in the background after I cancelled.
5. As an operator on a broken network, I want the scan to give up once most units are failing,
   so that I get a clear partial result quickly instead of grinding through guaranteed
   failures.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Step timeout bounds a hang | A scan step exceeds its configured per-step timeout | The timeout expires | The step's subprocess is terminated and the failure is recorded with the timeout terminal state; the scan does not hang |
| Unit failure is isolated | A stage has multiple units and one unit fails | The stage runs | The failed unit is recorded and skipped; every other unit completes and its data is kept |
| Transient retried once | A unit fails with a transient failure | The stage runs | The unit is retried exactly once; if it then fails it is demoted to a unit failure and the stage continues |
| Circuit breaker stops scan | The proportion of failed units in a stage exceeds the configured threshold | The threshold is crossed | The scan stops and finalizes a partial result containing everything that succeeded so far |
| Partial result on late fatal | Discovery has produced hosts and a fatal error occurs afterward | The scan stops | A partial result is emitted with the partial flag set and the interrupted stage recorded, not an empty result |
| Cancel keeps partial and halts work | A scan is mid-stage with discovered data | The operator cancels | New work stops, in-flight scan subprocesses are terminated, and a partial result is finalized with the interrupted stage recorded; the partial is offered to the operator |
| Fatal before data stops cleanly | No data has been gathered yet | A fatal failure occurs | The scan stops immediately, shows a clear error, and keeps nothing |
| Zero hosts finishes valid | Discovery finds no active hosts | The scan runs | Downstream stages are skipped and the scan finishes as a valid empty (non-error) result |
| Config knobs honored from TUI | New contingency knobs are configured | A scan is started from the TUI | The TUI-initiated scan applies the same timeout / deadline / threshold / retry behaviour as a non-TUI scan |

## Out of scope (v1)

- Whether the backend ingest contract accepts partial-result payloads (open question, report
  §9) — partial scans may stay local; resolving the contract is out of agent scope and does
  not block this work.
- Re-checking network connectivity periodically mid-scan (report F8) beyond what the
  circuit breaker and per-step timeouts already cover.
- New scan modes or changes to existing scan-mode port/timing profiles.
- Backend, frontend, or persistence changes.

## Related specs

- Implementation: `ARCHITECTURE.md`, `DESIGN.md` (ScanProgressScreen partial/degraded states)
- Execution ledger: `POOP.md` (written during orchestration)
- Background: `docs/implementation/SCAN-PIPELINE-RESILIENCE.md`, `docs/adr/ADR-004-scan-methodology.md`
