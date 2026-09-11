---
type: Module
title: scanner/runner — ScanRunner
description: ScanRunner — the worker thread, cancellation, deadline guards, and the _run() pipeline body that drives the whole scan.
resource: hardware-agent/src/agent/scanner/runner.py
tags: [hardware-agent, scanner, pipeline, threading]
timestamp: 2026-09-11T00:00:00Z
---

# scanner/runner — ScanRunner

## Purpose

`ScanRunner` owns one scan session: a daemon worker thread and a `threading.Event` cancel flag.
Its `_run()` method **is** the scan pipeline — it inlines host discovery, the port stage, the deep
inspection stage, and normalization, wrapping each step in cancel/deadline guards and translating
every failure mode into either a completed payload, a partial payload, or an error callback.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `ScanRunner` | Session object; holds scan inputs/callbacks, Nmap and Modbus cancellation handles, NSPi submode/policy, and workspace root. | `runner.py:36` |
| `ScanRunner.__init__` | Accepts both general scan inputs and current NSPi submode/policy options. | `runner.py:39` |
| `start()` / `run_blocking()` | Run `_run()` on a daemon thread or inline, respectively. | `runner.py:66`, `runner.py:70` |
| `request_cancel()` | Cancels active Nmap and Modbus work. | `runner.py:73` |
| `_check_cancel()` / `_check_deadline()` | Raise the existing cancellation/budget signals. | `runner.py:85`, `runner.py:89` |
| `_build_payload()` | Assembles hosts, OS/industrial data, findings, and metadata into a `ScanPayload`. | `runner.py:97` |
| `_finalize_partial()` | Builds a partial payload tagged with cause/stage, or emits `failed` if construction is impossible. | `runner.py:134` |
| `_run()` | Drives discovery → port-only enumeration → sole deep enrichment → NSPi OT inspection → normalization; carries port/deep skip counts into final partial metadata. | `runner.py:177` |

## How it connects

- **Upstream** — constructed by [`ScanProgressScreen`](/hardware-agent/tui.md) (`.start()`) and by
  [`run_headless_scan`](/hardware-agent/cli.md) (`.run_blocking()`).
- **Downstream** — `check_network_connectivity` ([utils](/hardware-agent/utils.md)),
  `build_runner` ([nmap](/hardware-agent/scanner/nmap.md)), `discover_hosts`
  ([discovery](/hardware-agent/discovery.md)), `run_port_stage` / `run_deep_inspection_stage` /
  `build_host_payload` / `build_metadata` ([stages](/hardware-agent/scanner/stages.md)),
  `extract_findings` and `ScanPayload` ([normalize](/hardware-agent/normalize.md)),
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
- A locally skipped port batch or eligible deep-inspection host also produces a normalized partial
  payload even when the pipeline reaches the end: `terminated_by="error"`; `interrupted_stage` is
  `ports` if any port unit was skipped, otherwise `deep_inspection`. Zero skips remains a
  completed payload. Cancellation and timeout keep their original cause/stage instead.
- The network info passed into metadata is a placeholder (`ip="0.0.0.0"`, `interface="tui"`);
  subnet selection happens in the front door, not here.

# Citations

[1] [ADR-010 — scan contingency policy](../../../../docs/adr/ADR-010-scan-contingency-policy.md)
[2] [ADR-004 — scan methodology](../../../../docs/adr/ADR-004-scan-methodology.md)
