---
type: Module
title: scanner/models — in-memory scan dataclasses
description: The in-memory scan dataclasses HostInfo, PortInfo, ServiceInfo, and ScriptResult that carry state across pipeline stages.
resource: hardware-agent/src/agent/scanner/models.py
tags: [hardware-agent, scanner, models, dataclasses]
timestamp: 2026-07-22T00:00:00Z
---

# scanner/models — in-memory scan models

## Purpose

`models.py` defines the mutable, slotted dataclasses that carry scan state *between* pipeline
stages, before normalization to the wire contract. A `HostInfo` is enriched in place: discovery
fills identity, the port stage sets `ports`, deep inspection merges services and NSE scripts.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `HostInfo` | A discovered host: `ip`, `hostname`, `mac`, `vendor`, `state`, `ports`, `host_scripts`. | `models.py:50` |
| `HostInfo.open_ports` | Property returning only `state == "open"` ports — the ones that feed service/NSE stages. | `models.py:62` |
| `PortInfo` | A port: `port`, `protocol`, `state`, `service`, `scripts`. | `models.py:39` |
| `ServiceInfo` | A service fingerprint: `name`, `product`, `version`, `extra_info`, `cpes`. | `models.py:20` |
| `ServiceInfo.banner` | Property joining product/version/extra_info into a compact string (or `None`). | `models.py:30` |
| `ScriptResult` | An NSE script run: `script_id`, `output`, parsed `data`, `is_host_script`. | `models.py:10` |

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
- `ScriptResult.data` is `Any` — the recursive NSE table parsed by
  [`parse_nse_node`](/hardware-agent/utils.md) into nested dicts/lists that
  [findings](/hardware-agent/normalize.md) walks.
