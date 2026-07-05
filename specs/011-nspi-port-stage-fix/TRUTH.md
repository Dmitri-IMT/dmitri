# TRUTH — Fix NSPi mode port stage (Stage 2)

Domain language and verifiable behaviour only. No file paths, no nmap flags, no code.

## Narrative

NSPi is the scan mode built for the pilot's OT/PLC lab. In the field it failed
deterministically: host discovery found devices, but the port stage produced zero ports,
the operator saw no progress for minutes and cancelled, and the app appeared frozen while
cancelling. A later Quick scan of the same subnet then erased the failed run's diagnostic
logs.

Stage 1 (root-cause analysis, recorded on Linear DMI-50) established that the failure was
mathematical, not environmental: the NSPi port stage runs a slow, deliberately "polite"
two-pass enumeration whose minimum runtime far exceeds the time budget it inherited from a
faster mode, so it can never finish. Three secondary defects made it worse — progress is
only reported once per host-batch (a multi-minute silent gap), cancellation both locks the
UI and can leave a new probe running, and log retention counts folders globally so an
unrelated later scan evicts a failed run's evidence.

Stage 2 makes NSPi complete reliably **in dev**, gives the port stage visible progress,
makes cancellation responsive, and protects a failed/partial run's logs. The pilot continues
on Quick scan regardless; there is no field retest.

## Business rules

- An NSPi port scan of a lab-size multi-host subnet must complete within its own time budget
  and attach the ports it finds — the stage's minimum runtime must fit inside its allotted
  budget rather than being guaranteed to exceed it.
- The OT-service probes stay gentle: enumeration of the OT-specific device ports stays
  deliberately polite/low-rate. The broad top-ports sweep may run at the standard rate — the
  same rate the Quick mode already applies to these devices — but the OT-port enumeration is
  never sped up.
- No other scan mode (Quick, Standard, Extensive, MAX) changes behaviour — timing, port
  scope, budgets, and outputs for those modes are untouched.
- The port stage reports progress more often than once per host-batch, so the operator never
  sees a multi-minute stretch with no new information during a normal NSPi run.
- Cancellation is responsive: after the operator cancels, the UI keeps accepting input and
  no new network probe is launched once cancellation has been requested; the partial result
  is still saved.
- A failed or partial scan's diagnostic logs survive a subsequent, unrelated scan. Retention
  is grouped per scan (protecting the most recent failed/partial run), not a flat global
  count of folders.
- The scan's saved metadata describes the enumeration that actually ran for NSPi (not the
  parameters of a different mode or a path that was bypassed).

## User stories

1. As the pilot operator, I run an NSPi scan on a lab-size subnet and get open ports and
   findings attached, so the mode built for NSPi is actually usable there.
2. As the operator, I watch an NSPi scan and see the port stage advance regularly, so I know
   it is working and don't cancel a healthy scan.
3. As the operator, I cancel a slow NSPi scan and the app stays responsive and saves what it
   found so far, so I'm never left staring at a frozen screen.
4. As the person diagnosing a failed scan, I still have that run's logs after running another
   scan, so failures remain investigable.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| NSPi completes | a dev subnet with several reachable hosts | an NSPi scan runs to completion | the scan finishes with at least one open port attached and the result is marked complete, not partial |
| Budget fits runtime | a lab-size NSPi port scan in dev | the two-pass port stage runs under its configured budget | it returns without a budget-exceeded timeout and no hosts are skipped for timing out (the stage is no longer guaranteed to exceed its budget) |
| OT politeness preserved | the OT-specific device-port pass | an NSPi scan runs | that pass still uses the deliberately polite/low-rate timing; only the broad sweep may run faster |
| Other modes untouched | Quick, Standard, Extensive, and MAX profiles | their port stages run | their timing, port scope, budgets, and outputs are identical to before this change |
| Sub-batch progress | an NSPi port stage scanning a multi-host batch | the stage is mid-run | progress updates arrive more than once per host-batch, with no multi-minute silent gap |
| Responsive cancel | an NSPi scan cancelled during the port stage | the operator cancels and the app finalizes | the UI keeps accepting input during cancelling, no new probe starts after cancel is requested, and the partial result is saved |
| Logs survive next scan | an NSPi scan that failed or was cancelled during the port stage | a subsequent unrelated scan runs and writes new logs | that failed/partial run's logs still exist afterwards |
| Honest metadata | a completed NSPi scan's saved metadata | the metadata is read | it describes the enumeration NSPi actually performed |
| Suites green | the touched scope | `uv run pytest` and `uv run ruff check` run | both pass |

## Out of scope (v1)

- No field retest at the NSPi lab (the test is closed; validate in dev only).
- No behaviour changes to Quick / Standard / Extensive / MAX modes.
- No progress-screen redesign beyond what the stall/responsiveness fix requires.
- No offline / vulners work.
- No new scan mode; this is a repair of the existing NSPi profile.

## Related specs

- Root cause: Linear DMI-50 Stage 1 comment (2026-07-04).
- Prior spec: `specs/004-nspi-scan-mode/` (original NSPi mode; the `-T2` PLC-safety decision).
- Decision context: `docs/adr/ADR-004-scan-methodology.md`, `docs/adr/ADR-010-scan-contingency-policy.md`.
- Implementation: `ARCHITECTURE.md`, `DESIGN.md`
- Execution ledger: `POOP.md` (written during orchestration)
