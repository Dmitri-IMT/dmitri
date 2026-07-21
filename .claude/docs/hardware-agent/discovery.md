---
type: Module
title: discovery — per-stage Nmap argument builders
description: Thin per-stage Nmap-argument builders — host discovery, port discovery, service detection, and NSE vulnerability scanning.
resource: hardware-agent/src/agent/discovery/
tags: [hardware-agent, discovery, nmap, nse]
timestamp: 2026-07-21T00:00:00Z
---

# discovery — per-stage Nmap builders

## Purpose

The `discovery/` package is a set of thin functions, one per pipeline stage. Each takes an
`NmapRunner`, builds the stage's argument list, calls `run_xml`, and parses the result into
[models](/hardware-agent/scanner/models.md) via the [utils](/hardware-agent/utils.md) XML helpers.
They hold *what to ask Nmap*; the threading, retry, and batching live in
[stages](/hardware-agent/scanner/stages.md).

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `discover_hosts()` | Stage 1: runs `-sn -PE -T4 <subnet>`, parses `up` hosts into `HostInfo`. Called directly by `ScanRunner._run()`. | `discovery/network_discovery.py:11` |
| `scan_ports_batch()` | Enumerates ports for a batch of IPs in one Nmap process; dispatches to the NSPi two-pass path for `nspi`. Used by `run_port_stage`. | `discovery/port_discovery.py:59` |
| `scan_ports()` | Single-host port scan (not used by the batched live pipeline). | `discovery/port_discovery.py:47` |
| `discovery_arguments()` | Per-mode port args: `max`→`-p-`, `extensive`→top-10000, else `--top-ports`/`--script`. | `discovery/port_discovery.py:39` |
| `_scan_ports_batch_nspi()` / `NSPI_PASS1_ARGS` / `NSPI_PASS2_ARGS` | NSPi two-pass scan (top-1000 + OT ports), merged. | `discovery/port_discovery.py:85`, `:10`, `:11` |
| `merge_ports()` | Deduplicates two port lists by `(port, protocol)`. | `discovery/port_discovery.py:14` |
| `run_nse_vulnerability_scan()` | Deep-inspection unit: `-sV --script <scripts> --script-args vulners.mincvss=<min>` per host; returns a `HostInfo` with parsed ports + host scripts. Called by `run_deep_inspection_stage`. | `discovery/vulnerability_detection.py:10` |
| `detect_services()` | `-sV --version-intensity` over open ports. Exported but **not called** by the live pipeline. | `discovery/service_detection.py:10` |

## How it connects

- **Upstream** — `discover_hosts` is called by [`ScanRunner`](/hardware-agent/scanner/runner.md);
  `scan_ports_batch` and `run_nse_vulnerability_scan` are driven by
  [stages](/hardware-agent/scanner/stages.md).
- **Downstream** — `NmapRunner.run_xml` ([nmap](/hardware-agent/scanner/nmap.md)), the XML parsers
  ([utils](/hardware-agent/utils.md)), the [models](/hardware-agent/scanner/models.md), and the mode
  script sets in [config](/hardware-agent/cli.md).

## Notes / gotchas

- **`detect_services` is dead in the live flow.** Service detection is folded into the port stage's
  `-sV` and the NSE args, so `service_detection.py` is a standalone/legacy helper kept but unwired —
  do not treat its absence from the pipeline as a bug.
- `discovery_arguments` has no `full` branch: the legacy `full` mode is being removed in favor of
  `max`.

# Citations

[1] [ADR-004 — scan methodology](../../../docs/adr/ADR-004-scan-methodology.md)
[2] [ADR-002 — scanning-tools selection](../../../docs/adr/ADR-002-scanning-tools-selection.md)
