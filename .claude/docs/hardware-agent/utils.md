---
type: Module
title: utils — network detection & Nmap XML parsing
description: Local-network detection/connectivity checks and the Nmap/NSE XML parsers shared across the pipeline.
resource: hardware-agent/src/agent/utils/network.py
tags: [hardware-agent, utils, network, xml, parsing]
timestamp: 2026-07-21T00:00:00Z
---

# utils — network & XML helpers

## Purpose

`utils/` holds two cross-cutting helper modules. `network.py` resolves the active local subnet and
guards that a network path exists before a scan starts. `nmap_xml.py` is the shared parser layer:
every discovery stage funnels Nmap's XML through it to produce [models](/hardware-agent/scanner/models.md).

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `LocalNetworkInfo` | Dataclass of the active interface's `ip`, `netmask`, `subnet`, `interface`. | `utils/network.py:12` |
| `detect_local_network()` | Resolves the outbound IPv4/subnet via a UDP-socket trick + `psutil`. | `utils/network.py:22` |
| `check_network_connectivity()` | Raises `NetworkUnreachableError` unless a non-loopback IPv4 interface is up. Called first in `ScanRunner._run()`. | `utils/network.py:54` |
| `parse_ports()` | Parses `<port>`/service/script nodes into `PortInfo` (open/filtered only). | `utils/nmap_xml.py:11` |
| `extract_ipv4()` | Pulls the IPv4 address from a host node. | `utils/nmap_xml.py:62` |
| `parse_host_scripts()` | Parses `<hostscript>` entries into `ScriptResult`s. | `utils/nmap_xml.py:71` |
| `parse_script()` | Parses one `<script>` node into a `ScriptResult`. | `utils/nmap_xml.py:83` |
| `parse_nse_node()` | Recursively parses NSE structured tables into nested dicts/lists. | `utils/nmap_xml.py:100` |

## How it connects

- **Upstream** — `check_network_connectivity` is called by
  [`ScanRunner`](/hardware-agent/scanner/runner.md); the XML parsers are called by every
  [discovery](/hardware-agent/discovery.md) function; `detect_local_network` /
  `_detect_interfaces`-style logic backs the TUI network screen ([tui](/hardware-agent/tui.md)).
- **Downstream** — produces [models](/hardware-agent/scanner/models.md); the nested dicts from
  `parse_nse_node` are what [findings](/hardware-agent/normalize.md) walks.

## Notes / gotchas

- `parse_ports` deliberately drops `closed` ports (keeps only `open`/`filtered`), so downstream port
  counts reflect reachable ports only.
- The `LocalNetworkInfo` the runner records in metadata is a placeholder — real interface selection
  happens in the TUI network screen, not via `detect_local_network`, on the TUI path.
