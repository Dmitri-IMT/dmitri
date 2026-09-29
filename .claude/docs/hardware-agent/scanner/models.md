---
type: Module
title: scanner/models — in-memory scan dataclasses
description: The in-memory scan dataclasses HostInfo, PortInfo, ServiceInfo, and ScriptResult that carry state across pipeline stages.
resource: hardware-agent/src/agent/scanner/models.py
tags: [hardware-agent, scanner, models, dataclasses]
timestamp: 2026-09-28T00:00:00Z
---

# scanner/models — in-memory scan models

## Purpose

`models.py` defines the mutable, slotted dataclasses that carry scan state *between* pipeline
stages, before normalization to the wire contract. A `HostInfo` is enriched in place: discovery
fills identity, the port stage sets `ports`, deep inspection merges services and NSE scripts.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `HostInfo` | A discovered host: `ip`, `hostname`, `mac`, `vendor` (default `"unknown"`), `state`, `ports`, `operating_system`, `host_scripts`, `industrial_services`, `targeted_results`. | `models.py:105` |
| `HostInfo.open_ports` | Property returning only `state == "open"` ports — the ones that feed service/NSE stages. | `models.py:120` |
| `PortScanResult` | One Nmap host node from the port stage: `ports`, `operating_system`, `mac`, `vendor`, `skipped`. | `models.py:69` |
| `merge_mac_vendor()` | Merges MAC and vendor as one pair. No incoming MAC keeps the existing pair. Same MAC keeps the existing vendor unless the incoming one is known. A new MAC never inherits the old vendor: it takes the incoming vendor or `"unknown"`. | `models.py:79` |
| `PortInfo` | A port: `port`, `protocol`, `state`, `service`, `scripts`. | `models.py:58` |
| `ServiceInfo` | A service fingerprint: `name`, `product`, `version`, `extra_info`, `cpes`. | `models.py:38` |
| `ServiceInfo.banner` | Property joining product/version/extra_info into a compact string (or `None`). | `models.py:49` |
| `ScriptResult` | An NSE script run: `script_id`, `output`, parsed `data`, `is_host_script`. | `models.py:28` |

## How it connects

- **Upstream** — produced/mutated by the [discovery](/hardware-agent/discovery.md) functions and the
  [stages](/hardware-agent/scanner/stages.md); built by the XML parsers in
  [utils](/hardware-agent/utils.md).
- **Downstream** — consumed by [stages](/hardware-agent/scanner/stages.md) `build_host_payload`
  and by `extract_findings` in [normalize](/hardware-agent/normalize.md) on the way to the
  [`ScanPayload`](/hardware-agent/normalize.md) contract.

## Notes / gotchas

- These models are the in-agent representation of a [host](/glossary.md); they become contract-shaped
  **`HostPayload`**s at `build_host_payload`.
- **MAC and vendor travel as a pair.** Discovery, the port stage, and deep inspection each read the
  MAC `<address>` node, and [stages](/hardware-agent/scanner/stages.md) folds each later reading into
  the host with `merge_mac_vendor`. A stage whose XML has no MAC node cannot erase the discovery
  vendor, and a vendor never carries over to a different MAC.
- `ScriptResult.data` is `Any` — the recursive NSE table parsed by
  [`parse_nse_node`](/hardware-agent/utils.md) into nested dicts/lists that
  [findings](/hardware-agent/normalize.md) walks.
