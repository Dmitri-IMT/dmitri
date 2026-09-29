---
type: Module
title: utils — network detection & Nmap XML parsing
description: Local-network detection/connectivity checks and the Nmap/NSE XML parsers shared across the pipeline.
resource: hardware-agent/src/agent/utils/network.py
tags: [hardware-agent, utils, network, xml, parsing]
timestamp: 2026-09-28T00:00:00Z
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
| `AvailableSubnetInfo` | Dataclass of one usable subnet: `interface`, `cidr`, `is_default_route`. | `utils/network.py:51` |
| `detect_available_subnets()` | Daemon-facing enumeration: every usable IPv4 interface as an `AvailableSubnetInfo`. Filters loopback, link-local, down interfaces, IPv6 and bad netmasks; dedupes by `(interface, cidr)`; canonicalizes to the network address. | `utils/network.py:59` |
| `check_network_connectivity()` | Raises `NetworkUnreachableError` unless a non-loopback IPv4 interface is up. Called first in `ScanRunner._run()`. | `utils/network.py:105` |
| `parse_ports()` | Parses `<port>`/service/script nodes into `PortInfo` (open/filtered only). | `utils/nmap_xml.py:95` |
| `extract_ipv4()` | Pulls the IPv4 address from a host node. | `utils/nmap_xml.py:151` |
| `extract_mac_vendor()` | Returns `(mac, vendor)` from the first `addrtype="mac"` address node, or `(None, None)`. Used by host, port and deep-inspection parsing. | `utils/nmap_xml.py:160` |
| `parse_host_scripts()` | Parses `<hostscript>` entries into `ScriptResult`s. | `utils/nmap_xml.py:172` |
| `parse_script()` | Parses one `<script>` node into a `ScriptResult`. | `utils/nmap_xml.py:184` |
| `parse_nse_node()` | Recursively parses NSE structured tables into nested dicts/lists. | `utils/nmap_xml.py:201` |

## How it connects

- **Upstream** — `check_network_connectivity` is called by
  [`ScanRunner`](/hardware-agent/scanner/runner.md); the XML parsers are called by every
  [discovery](/hardware-agent/discovery.md) function; `detect_local_network` /
  `_detect_interfaces`-style logic backs the TUI network screen ([tui](/hardware-agent/tui.md));
  `detect_available_subnets` is called by the
  [command channel](/hardware-agent/command-channel.md) once per hello.
- **Downstream** — produces [models](/hardware-agent/scanner/models.md); the nested dicts from
  `parse_nse_node` are what [findings](/hardware-agent/normalize.md) walks.

## Notes / gotchas

- `parse_ports` deliberately drops `closed` ports (keeps only `open`/`filtered`), so downstream port
  counts reflect reachable ports only.
- The `LocalNetworkInfo` the runner records in metadata is a placeholder — real interface selection
  happens in the TUI network screen, not via `detect_local_network`, on the TUI path.
- `detect_available_subnets` **reports, it does not select.** It never picks a scan target, never
  persists a list, and never raises: if the default-route probe fails it returns the full usable
  list with every flag `False` rather than guessing. Target selection belongs to the backend and
  the operator.
- The route flag is marked **per interface**, not per CIDR — an interface carrying two IPv4 subnets
  yields two `True` entries. That matches the contract's wording ("mark only entries on the
  interface selected by the outbound route") and the dual-homed Pi it was written for.
- The TUI's private `_detect_interfaces()` is a separate enumerator and was deliberately left
  untouched by DMI-66.
