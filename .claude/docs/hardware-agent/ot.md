---
type: Package
title: hardware-agent OT package
description: Modbus inspection on the Pi — policy, digest, read-only client, inventory, and the OT scan stage.
resource: hardware-agent/src/agent/ot/
tags: [hardware-agent, ot, modbus, pymodbus]
timestamp: 2026-09-12T00:00:00Z
---

# hardware-agent OT package

`agent/ot/` talks Modbus TCP from the Pi. It is an extra stage after NSE, not a replacement
for Nmap. The dependency is `pymodbus`. `AGENT_VERSION` is `0.1.4`.

## Layout

| Path | Role |
|------|------|
| `ot/policy.py` | Installer mapping policy, CIDR/MAC corroboration |
| `ot/digest.py` | HMAC-SHA256 of process values; key from `DMITRI_OT_DIGEST_KEY` or `~/.config/dmitri/ot-digest-key` |
| `ot/untrusted.py` | Bound device strings at parse |
| `ot/modbus/readonly.py` | Client that raises on any write |
| `ot/modbus/inventory.py` | Per-unit FC43, paced, isolated |
| `ot/modbus/mapper.py` | Read-only ranges and digests |
| `scanner/stages.py` | OT stage, host/stage deadlines, `ot_stage_deadline` |

Default NSPi submodes that run: `inventory`, `read_only_mapping`. `active_validation` is
refused in `ScanRunner.__init__`.
