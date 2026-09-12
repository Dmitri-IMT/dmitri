---
type: Module
title: scanner/stages — port, deep, and OT inspection stages
description: Threaded Nmap stages, serial bounded OT inspection, retry/circuit-breaker policy, and HostInfo-to-HostPayload normalization.
resource: hardware-agent/src/agent/scanner/stages.py
tags: [hardware-agent, scanner, pipeline, threading, contingency]
timestamp: 2026-09-11T00:00:00Z
---

# scanner/stages — port, deep & OT-inspection stages

## Purpose

`stages.py` holds the two heavy, thread-pooled Nmap stages, NSPi's serial bounded Modbus stage, and
the helpers that turn scan results into contract shapes and run metadata. Each Nmap stage fans work across a
`ThreadPoolExecutor(max_workers)`, retries transient failures per unit, and trips a circuit breaker
when too large a fraction of units fail — the mechanical half of the ADR-010 contingency policy.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `run_port_stage()` | Batches hosts, runs port-only discovery, attaches ports + OS evidence, reports per-host skips, and returns their count. The breaker uses skipped hosts / total hosts. | `stages.py:91` |
| `run_deep_inspection_stage()` | Runs the sole `-sV` + NSE authority per eligible host, retains NSPi's bounded `-O`, merges evidence additively, and returns skipped-host count. Empty regular results emit `unit_failed`; empty NSPi results retain their timeout classification. | `stages.py:195` |
| `run_ot_inspection_stage()` | After NSPi Nmap enrichment, performs unchanged serial, bounded Modbus inventory or read-only mapping. | `stages.py:333` |
| `_run_unit_with_retry()` | Retries a unit of work on `TransientScanError` up to `retries + 1` times, then raises `UnitScanError`. | `stages.py:60` |
| `build_host_payload()` | Maps host, OS, ports, and industrial evidence into `HostPayload`. | `stages.py:417` |
| `nmap_arguments_summary()` | Describes port-only enumeration, the single deep `-sV`/NSE command, and selected OT submode. | `stages.py:530` |
| `build_metadata()` | Assembles general scan metadata plus NSPi/Modbus counters. | `stages.py:563` |
| `set_runner_stage()` | Tags a `LoggedNmapRunner` with the current stage name; no-op for a plain runner. | `stages.py:75` |

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
- Deep inspection uses `max(settings.version_intensity, 7)`: the former port-stage `-sV` implicitly
  used Nmap intensity 7, so this floor preserves its fingerprint detail after deduplication.
- Both Nmap stages return explicit skip counts. These let the runner preserve all successful
  evidence while truthfully marking an otherwise completed scan partial when any unit was skipped.
- NSPi still proceeds to `run_ot_inspection_stage()` after its deduplicated deep scan; this change
  does not modify Modbus candidacy, safety policy, request budgets, or progress events.
- `build_host_payload` (formerly `build_device_payload`) emits the wire term **host** for the ingest
  payload — ADR-013 unified the ingest vocabulary with the rest of the pipeline. See
  [glossary](/glossary.md).
- A set `cancel_event` breaks the `as_completed` loop but in-flight Nmap subprocesses are killed via
  `ScanRunner.request_cancel()` → `NmapRunner.terminate_active()`, not from here.

# Citations

[1] [ADR-010 — scan contingency policy](../../../../docs/adr/ADR-010-scan-contingency-policy.md)
