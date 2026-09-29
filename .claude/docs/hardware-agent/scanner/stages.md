---
type: Module
title: scanner/stages — port, deep, and OT inspection stages
description: Threaded Nmap stages, serial bounded OT inspection, retry/circuit-breaker policy, and HostInfo-to-HostPayload normalization.
resource: hardware-agent/src/agent/scanner/stages.py
tags: [hardware-agent, scanner, pipeline, threading, contingency]
timestamp: 2026-09-28T00:00:00Z
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
| `run_port_stage()` | Batches hosts, runs port-only discovery, attaches ports + OS evidence, folds the result's MAC/vendor into the host with `merge_mac_vendor`, reports per-host skips, and returns their count. The breaker uses skipped hosts / total hosts. | `stages.py:126` |
| `run_deep_inspection_stage()` | Runs the primary `-sV` + NSE pass per eligible host. On a failed or empty result, a bounded service-only recovery probe may retain evidence; a failed recovery counts as an incomplete host. A successful result's MAC/vendor is folded in with `merge_mac_vendor`. | `stages.py:237` |
| `_recover_deep_stage_services()` | Reuses `detect_services` for recovery; treats a host-level Nmap error or timeout as unsuccessful recovery without stopping the scan. | `stages.py:99` |
| `_stage_deadline_hit()` | Returns elapsed stage seconds when the stage clock is past, else `None`. | `stages.py:409` |
| `run_ot_inspection_stage()` | Serial Modbus inventory or read-only mapping. Checks cancel and the stage ceiling at the start of each host; after the loop, if the run was not cancelled, emits `ot_stage_deadline` once. Each started host gets `host_deadline` (stage cap plus `MAX_OT_HOST_SECONDS`) for inventory and mapping. | `stages.py:418` |
| `_run_unit_with_retry()` | Retries a unit of work on `TransientScanError` up to `retries + 1` times, then raises `UnitScanError`. | `stages.py:70` |
| `build_host_payload()` | Maps original host, OS, port, and industrial observations into `HostPayload`; optional assessment fields are attached later by the runner. | `stages.py:538` |
| `nmap_arguments_summary()` | Describes port-only enumeration, the primary deep `-sV`/NSE command, and selected OT submode. | `stages.py:628` |
| `build_metadata()` | Assembles general scan metadata plus NSPi/Modbus counters and the stage-deadline signal. | `stages.py:659` |
| `set_runner_stage()` | Tags a `LoggedNmapRunner` with the current stage name; no-op for a plain runner. | `stages.py:83` |

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
- A failed deep inspection starts a service-only recovery probe. If that probe times out or has a
  host-level scan error, the host is counted as skipped; its earlier port evidence remains intact.
- The OT host deadline limits requests for that host. The stage deadline is checked before
  starting a host and once after the host loop; only that stage limit sets
  `modbus_stage_deadline_reached`. `hosts_done` counts hosts that passed the start-of-loop check.
- Both Nmap stages return explicit skip counts. These let the runner preserve all successful
  evidence while truthfully marking an otherwise completed scan partial when any unit was skipped.
- NSPi proceeds to `run_ot_inspection_stage()` after deep inspection, using the discovered Modbus
  candidates and the policy's request budget and pacing.
- `build_host_payload` (formerly `build_device_payload`) emits the wire term **host** for the ingest
  payload — ADR-013 unified the ingest vocabulary with the rest of the pipeline. See
  [glossary](/glossary.md).
- A set `cancel_event` breaks the `as_completed` loop but in-flight Nmap subprocesses are killed via
  `ScanRunner.request_cancel()` → `NmapRunner.terminate_active()`, not from here.

# Citations

[1] [ADR-010 — scan contingency policy](../../../../docs/adr/ADR-010-scan-contingency-policy.md)
