---
type: Module
title: scanner/runner — ScanRunner
description: ScanRunner — the worker thread, cancellation, deadline guards, and the _run() pipeline body that drives the whole scan.
resource: hardware-agent/src/agent/scanner/runner.py
tags: [hardware-agent, scanner, pipeline, threading]
timestamp: 2026-07-21T00:00:00Z
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
| `ScanRunner` | Session object; holds subnet, mode, reporter, callbacks, `workspace_root`, cancel event, and the active runner handle. | `runner.py:29` |
| `ScanRunner.__init__` | Params: `subnet`, `scan_mode`, `reporter`, `on_complete`, `on_error`, `workspace_root`, `runner`. | `runner.py:32` |
| `start()` | Spawns `_run()` on a daemon thread (TUI path). | `runner.py:54` |
| `run_blocking()` | Runs `_run()` inline on the caller's thread (headless path). | `runner.py:58` |
| `request_cancel()` | Sets the cancel event and calls `terminate_active()` on the live Nmap runner. | `runner.py:61` |
| `_check_cancel()` | Raises `ScanCancelled` if the event is set. | `runner.py:72` |
| `_check_deadline()` | Raises `BudgetExceeded` once the wall-clock deadline passes. | `runner.py:76` |
| `_build_payload()` | Assembles devices + findings + metadata into a `ScanPayload`. | `runner.py:84` |
| `_finalize_partial()` | Builds a partial payload tagged with `terminated_by`, or emits `failed` if nothing usable exists. | `runner.py:120` |
| `_run()` | The pipeline body: connectivity check → settings/network/runner build → discovery → ports → deep inspection → normalize, with per-stage guards and a layered `except` ladder. | `runner.py:163` |

## How it connects

- **Upstream** — constructed by [`ScanProgressScreen`](/hardware-agent/tui.md) (`.start()`) and by
  [`run_headless_scan`](/hardware-agent/cli.md) (`.run_blocking()`).
- **Downstream** — `check_network_connectivity` ([utils](/hardware-agent/utils.md)),
  `build_runner` ([nmap](/hardware-agent/scanner/nmap.md)), `discover_hosts`
  ([discovery](/hardware-agent/discovery.md)), `run_port_stage` / `run_deep_inspection_stage` /
  `build_device_payload` / `build_metadata` ([stages](/hardware-agent/scanner/stages.md)),
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
- The network info passed into metadata is a placeholder (`ip="0.0.0.0"`, `interface="tui"`);
  subnet selection happens in the front door, not here.

# Citations

[1] [ADR-010 — scan contingency policy](../../../../docs/adr/ADR-010-scan-contingency-policy.md)
[2] [ADR-004 — scan methodology](../../../../docs/adr/ADR-004-scan-methodology.md)
