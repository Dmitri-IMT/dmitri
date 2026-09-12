---
type: Package
title: hardware-agent OT package
description: Modbus inspection on the Pi — policy, digest, read-only client, inventory, and the OT scan stage.
resource: hardware-agent/src/agent/ot/
tags: [hardware-agent, ot, modbus, pymodbus]
timestamp: 2026-09-12T23:15:00Z
---

# hardware-agent OT package

## Purpose

`agent/ot/` talks Modbus TCP from the Pi. It is an extra stage after NSE, not a replacement
for Nmap. The dependency is `pymodbus`. `AGENT_VERSION` is `0.1.4`.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `stop_reason()` | `cancel`, `deadline`, or `None`. Cancel wins when both are true. | `ot/policy.py:35` |
| `must_stop()` | True when `stop_reason` is not `None`. Port loops and mapping range loops keep this bool. | `ot/policy.py:46` |
| `pace_or_stop()` | Sleeps only when still running; otherwise returns the stop reason. Inventory fallbacks and mapping chunks share it. | `ot/policy.py:53` |
| `CaptureValues` | `none` or `digest`. Default `digest`. Policy ranks digest as more capture than none. | `ot/policy.py:16` |
| `profile_is_conservative()` | Allows an identity-only mapping profile only when every read stays inside a generic-baseline address range and its other limits are no broader. CIDR/MAC matches may use broader site profiles. | `ot/policy.py:152` |
| `load_digest_key()` / `value_digest()` | Load the local key and compute an HMAC-SHA256 digest; no key means no digest. | `ot/digest.py:35`, `:48` |
| `ReadOnlyModbusClient` | Exposes only the allowed read methods to Modbus sessions. | `ot/modbus/readonly.py:23` |
| `merge_unit()` | One status rank for NSE parse and inventory probes: responding > exception > timeout/error > skipped. Never demotes. | `ot/modbus/merge.py:14` |
| `inventory_modbus_host()` | Collects paced, isolated FC43 identification for candidate ports and units. Cancel stops fallbacks without fake skipped units; a deadline records `skipped` and continues. | `ot/modbus/inventory.py:23` |
| `resolve_mapping_plan()` / `map_modbus_service()` | Choose the allowed range profile and execute read-only mapping. The planner returns `identity_not_corroborated`; the mapper tags evidence. | `ot/modbus/mapper.py:71`, `:122` |

## How it connects

[`run_ot_inspection_stage()`](/hardware-agent/scanner/stages.md) calls inventory, optional mapping,
and fingerprint correlation after the primary Nmap/NSE pass. Its host and stage deadlines are
separate: one slow host does not prevent later hosts from being inspected while stage time remains.
The resulting industrial observations become [scan payloads](/hardware-agent/normalize.md).

## Notes / gotchas

Default NSPi submodes that run: `inventory`, `read_only_mapping`. `active_validation` is
refused in `ScanRunner.__init__`.
