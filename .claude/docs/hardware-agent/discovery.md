---
type: Module
title: discovery — per-stage Nmap argument builders
description: Thin per-stage Nmap-argument builders — host discovery, port discovery, service detection, and NSE vulnerability scanning.
resource: hardware-agent/src/agent/discovery/
tags: [hardware-agent, discovery, nmap, nse]
timestamp: 2026-09-11T00:00:00Z
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
| `scan_ports_batch()` | Enumerates ports for a batch of IPs in one Nmap process; dispatches to the NSPi two-pass path for `nspi`. Used by `run_port_stage`. | `discovery/port_discovery.py:96` |
| `scan_ports()` | Single-host port scan (not used by the batched live pipeline). | `discovery/port_discovery.py:84` |
| `discovery_arguments()` | Port-only args: regular modes retain `-O`; `max` adds `-p- --min-rate 1000`, `extensive` adds top-10000, and Quick/Standard use Nmap's default top-1000. The common caller adds `-Pn -n -T4`; no port path adds `-sV` or NSE. | `discovery/port_discovery.py:76` |
| `_scan_ports_batch_nspi()` / `NSPI_PASS1_ARGS` / `NSPI_PASS2_ARGS` | NSPi port-only two-pass scan: default top-1000 at `-T4`, then the seven OT ports at `-T2`; both use `-Pn -n --host-timeout 300s` and their `PortScanResult`s are merged. | `discovery/port_discovery.py:122`, `:12`, `:13` |
| `merge_ports()` | Deduplicates two port lists by `(port, protocol)`. | `discovery/port_discovery.py:24` |
| `run_nse_vulnerability_scan()` | Sole enrichment unit: `-Pn -n -T4 -sV --version-intensity <effective> --script <scripts> --script-args vulners.mincvss=<min>` over the already-open ports of one host; optional NSPi OS/internal-timeout flags remain supported. | `discovery/vulnerability_detection.py:14` |
| `detect_services()` | `-sV --version-intensity` over open ports. Exported but **not called** by the live pipeline. | `discovery/service_detection.py:10` |

## How it connects

- **Upstream** — `discover_hosts` is called by [`ScanRunner`](/hardware-agent/scanner/runner.md);
  `scan_ports_batch` and `run_nse_vulnerability_scan` are driven by
  [stages](/hardware-agent/scanner/stages.md).
- **Downstream** — `NmapRunner.run_xml` ([nmap](/hardware-agent/scanner/nmap.md)), the XML parsers
  ([utils](/hardware-agent/utils.md)), the [models](/hardware-agent/scanner/models.md), and the mode
  script sets in [config](/hardware-agent/cli.md).

## Notes / gotchas

- **`detect_services` is dead in the live flow.** Service/version detection and NSE enrichment now
  happen together exactly once in `run_nse_vulnerability_scan`; `service_detection.py` remains a
  standalone/legacy helper kept but unwired — do not treat its absence from the pipeline as a bug.
- Regular port discovery retains OS detection (`-O`) but does not run `-sV` or NSE. NSPi keeps its
  current OS probe in the bounded per-host deep command. The deep stage is the single authority for
  service/version and script evidence in every mode; both NSPi port passes are enrichment-free.
- `discovery_arguments` has no `full` branch: the legacy `full` mode is being removed in favor of
  `max`.

# Citations

[1] [ADR-004 — scan methodology](../../../docs/adr/ADR-004-scan-methodology.md)
[2] [ADR-002 — scanning-tools selection](../../../docs/adr/ADR-002-scanning-tools-selection.md)
