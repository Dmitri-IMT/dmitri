---
type: Module
title: scanner/stages — threaded port & deep-inspection stages
description: The threaded port and deep-inspection stages, with per-unit retry, circuit breaker, and the HostInfo-to-HostPayload builder.
resource: hardware-agent/src/agent/scanner/stages.py
tags: [hardware-agent, scanner, pipeline, threading, contingency]
timestamp: 2026-07-22T00:00:00Z
---

# scanner/stages — port & deep-inspection stages

## Purpose

`stages.py` holds the two heavy, thread-pooled pipeline stages plus the helpers that turn scan
results into contract shapes and run metadata. Each stage fans work across a
`ThreadPoolExecutor(max_workers)`, retries transient failures per unit, and trips a circuit breaker
when too large a fraction of units fail — the mechanical half of the ADR-010 contingency policy.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `run_port_stage()` | Chunks host IPs into `host_batch_size` batches, runs `scan_ports_batch` across the pool, records ports per host, and emits port events. Raises `CircuitBreakerError` when `batches_failed / batches_total > unit_failure_threshold`. | `stages.py:71` |
| `run_deep_inspection_stage()` | Per host with open ports, runs `run_nse_vulnerability_scan` in the pool; merges resulting ports + host scripts. Same retry + breaker logic. | `stages.py:170` |
| `_run_unit_with_retry()` | Retries a unit of work on `TransientScanError` up to `retries + 1` times, then raises `UnitScanError`. | `stages.py:40` |
| `build_host_payload()` | Maps a `HostInfo` → `HostPayload` (formerly `build_device_payload`), sanitizing protocol to `tcp`/`udp` and state to `open`/`closed`/`filtered` to satisfy the contract enums. | `stages.py:270` |
| `nmap_arguments_summary()` | Human-readable summary of the Nmap args used (special-cased for NSPi two-pass). | `stages.py:296` |
| `build_metadata()` | Assembles the `ScanPayload.metadata` dict: version, nmap path/args, timing, counts, `partial_result`, `interrupted_stage`, `terminated_by`. | `stages.py:317` |
| `set_runner_stage()` | Tags a `LoggedNmapRunner` with the current stage name (for log-folder naming); no-op for a plain runner. | `stages.py:55` |

## How it connects

- **Upstream** — called by [`ScanRunner._run()`](/hardware-agent/scanner/runner.md) and its
  `_build_payload()`.
- **Downstream** — `scan_ports_batch`, `discovery_arguments`, `merge_ports`, `NSPI_PASS*_ARGS`
  ([discovery](/hardware-agent/discovery.md)), `run_nse_vulnerability_scan`
  ([discovery](/hardware-agent/discovery.md)), `deep_stage_scripts` / `subprocess_timeout_for`
  ([config](/hardware-agent/cli.md)), `HostPayload` / `PortPayload`
  ([normalize](/hardware-agent/normalize.md)), the scan errors
  ([errors](/hardware-agent/scanner/errors.md)), and `ScanEvent`
  ([progress](/hardware-agent/scanner/progress.md)).

## Notes / gotchas

- The circuit breaker is checked *after each completed future*, so a run can abort mid-pool once the
  failure ratio crosses `unit_failure_threshold` (default `0.5`).
- `build_host_payload` (formerly `build_device_payload`) emits the wire term **host** for the ingest
  payload — ADR-013 unified the ingest vocabulary with the rest of the pipeline. See
  [glossary](/glossary.md).
- A set `cancel_event` breaks the `as_completed` loop but in-flight Nmap subprocesses are killed via
  `ScanRunner.request_cancel()` → `NmapRunner.terminate_active()`, not from here.

# Citations

[1] [ADR-010 — scan contingency policy](../../../../docs/adr/ADR-010-scan-contingency-policy.md)
