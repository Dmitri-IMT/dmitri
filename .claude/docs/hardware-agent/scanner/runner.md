---
type: Module
title: scanner/runner — ScanRunner
description: ScanRunner — the worker thread, cancellation, deadline guards, and the _run() pipeline body that drives the whole scan.
resource: hardware-agent/src/agent/scanner/runner.py
tags: [hardware-agent, scanner, pipeline, threading]
timestamp: 2026-10-17T00:00:00Z
---

# scanner/runner — ScanRunner

## Purpose

`ScanRunner` owns one scan session: a daemon worker thread and a `threading.Event` cancel flag.
Its `_run()` method **is** the scan pipeline — it inlines host discovery, the port stage, deep
inspection, NSPi OT inspection, and normalization. It wraps each step in cancel/deadline guards
and translates every failure mode into a completed payload, partial payload, or error callback.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `ScanRunner` | Session object; holds scan inputs/callbacks, Nmap and Modbus cancellation handles, NSPi submode/policy, and workspace root. | `runner.py:38` |
| `ScanRunner.__init__` | Validates NSPi depth before active work and accepts general scan inputs and NSPi submode/policy options. | `runner.py:41` |
| `start()` / `run_blocking()` | Run `_run()` on a daemon thread or inline, respectively. | `runner.py:69`, `runner.py:73` |
| `request_cancel()` | Cancels active Nmap and Modbus work. | `runner.py:76` |
| `_check_cancel()` / `_check_deadline()` | Raise the existing cancellation/budget signals. | `runner.py:88`, `runner.py:92` |
| `_build_payload()` | Normalizes accepted host evidence, runs local assessment, and assembles profiles, exposures, evidence-aware findings, scan-level observations, coverage and policy version `1` into one `ScanPayload`. The same builder handles completed and partial results. | `runner.py:121` |
| `_finalize_partial()` | Calls `_record_not_run`, then builds a partial payload tagged with cause/stage, or emits `failed` if construction is impossible. | `runner.py:172` |
| `_record_not_run()` | On a stop, appends a `skipped`/`not_run` `StageCoverage` (reason `scan_cancelled`/`scan_timeout`/`scan_error`) for each stage the host never reached: `ports` when missing, `deep_inspection` for hosts with open ports, `ot_inspection` in NSPi mode for hosts with a Modbus candidate when the OT stage had not started, and — in targeted modes, only if the targeted stage had not started — one `targeted_assessment` line per host with open ports (no port or tool; nothing is re-selected). | `runner.py:496` |
| `_run()` | Drives discovery → ports → deep inspection → NSPi OT inspection → normalization; a completed scan with skipped port/deep units carries `partial_result=true` and `terminated_by="completed"`. | `runner.py:225` |

## How it connects

- **Upstream** — constructed by [`ScanProgressScreen`](/hardware-agent/tui.md) (`.start()`) and by
  [`run_headless_scan`](/hardware-agent/cli.md) (`.run_blocking()`).
- **Downstream** — `check_network_connectivity` ([utils](/hardware-agent/utils.md)),
  `build_runner` ([nmap](/hardware-agent/scanner/nmap.md)), `discover_hosts`
  ([discovery](/hardware-agent/discovery.md)), `run_port_stage` / `run_deep_inspection_stage` /
  `run_ot_inspection_stage` / `build_host_payload` / `build_metadata`
  ([stages](/hardware-agent/scanner/stages.md)),
  `extract_findings` and `ScanPayload` ([normalize](/hardware-agent/normalize.md)),
  `assess_hosts` ([assessment](/hardware-agent/assessment.md)),
  `ScanEvent` ([progress](/hardware-agent/scanner/progress.md)).
- Emits [`ScanEvent`](/hardware-agent/scanner/progress.md)s through the reporter; reports the final
  result via `on_complete(payload)` / `on_error(exc)`.

## Notes / gotchas

- **There is no `ScanOrchestrator`.** `_run()` is the pipeline; the CLAUDE.md "bypass" warning is
  about the *dual front-door* design (TUI + headless), not a second live code path. Both front doors
  construct a `ScanRunner` and must thread `workspace_root` — that is the invariant the integration
  rule protects, and there are exactly two constructor sites to keep in sync.
- The `except` ladder maps failure classes to `terminated_by` on the partial payload:
  `FatalScanError` before discovery → hard `failed`; after discovery → partial `error`;
  `CircuitBreakerError` → `error`; other `BudgetExceeded` → `timeout`; `ScanCancelled` →
  `user_cancel`; any other exception with hosts in hand → partial `error`.
- A skipped port batch, an eligible deep-inspection host, a targeted gap, or a reached OT
  inspection stage deadline sets `partial_result=true` when the
  pipeline finishes, with `terminated_by="completed"` and no `interrupted_stage`. Cancellation,
  timeout, and errors keep their cause and interrupted stage instead.
- The network info passed into metadata is a placeholder (`ip="0.0.0.0"`, `interface="tui"`);
  subnet selection happens in the front door, not here.
- Assessment is a normalization substep, not a new scan stage: it adds no event, timeout, probe, or
  I/O, and it also runs when an accepted partial result is finalized.
- Finding evidence extraction is also local normalization. Every runner payload, including a
  partial payload, carries `finding_evidence_policy_version="1"`; finding `issue_key` values bind
  observations to their condition. See [normalize](/hardware-agent/normalize.md).

# Citations

[1] [ADR-010 — scan contingency policy](../../../../docs/adr/ADR-010-scan-contingency-policy.md)
[2] [ADR-004 — scan methodology](../../../../docs/adr/ADR-004-scan-methodology.md)
