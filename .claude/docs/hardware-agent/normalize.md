---
type: Module
title: normalize — contracts & findings extraction
description: The Pydantic scan payloads for observations, profiles, exposures and findings, plus the NSE finding extractor.
resource: hardware-agent/src/agent/normalize/contracts.py
tags: [hardware-agent, normalize, contracts, findings, pydantic]
timestamp: 2026-09-18T00:00:00Z
---

# normalize — contracts & findings

## Purpose

`normalize/` turns the agent's in-memory scan state into the shared wire contract. `contracts.py`
holds the Pydantic models serialized to disk and uploaded; `findings.py` walks parsed
NSE output and emits structured `FindingPayload`s. The `ScanPayload` is the cross-component boundary
object that binds the agent to the backend ingest route. Modbus process values remain on the Pi;
only range status and an optional keyed digest cross this boundary.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `ScanPayload` | Top-level result including optional `assessment_policy_version` and `exposures`; absence marks a legacy scan whose assessment is unavailable. | `contracts.py:263` |
| `HostPayload` | A host on the wire: original observations plus optional `machine_type` and `device_profile`. | `contracts.py:233` |
| `AssessmentEvidencePayload` | Bounded evidence item with a closed kind, source, and normalized value. | `contracts.py:64` |
| `ExposurePayload` | One open endpoint's role, attention, confidence, reason, and evidence; separate from findings. | `contracts.py:93` |
| `DeviceProfilePayload` | Evidence-backed machine type, manufacturer/product/model assessment, confidence, conflicts, and limitations. | `contracts.py:118` |
| `PortPayload` | A port: `port` (1–65535), `protocol` enum, `state` enum, `service`, `version`, CPEs. | `contracts.py:31` |
| `ModbusTcpServicePayload` / `ModbusUnitPayload` | Bounded industrial service and unit evidence. | `contracts.py:106`, `:90` |
| `ModbusAddressRangePayload` | Address, status, timestamp, and optional `hmac-sha256` digest; no process values or aggregates. | `contracts.py:68` |
| `FindingPayload` | A vulnerability/observation with optional `unit_id` for Modbus attribution. | `contracts.py:128` |
| `extract_findings()` | Walks host scripts, port scripts, and per-unit Modbus read findings. Dedups by `(ip, port, unit_id, script, cve/title)`. | `findings.py:17` |
| `_extract_modbus_read_findings()` | One finding per unit that has a readable range, with that `unit_id`. NSE findings omit `unit_id`. | `findings.py:39` |
| `_EXTRACTORS` | Dispatch table: `vulners`, `smb2-security-mode`, `smb-protocols`, `http-methods`, `ssh-auth-methods`, `ssl-cert`, `ssl-enum-ciphers`, `ftp-anon`. | `findings.py:703` |
| `_extract_vulners_findings()` | Correlates CVE + CVSS from the `vulners` NSE table → severity. | `findings.py:104` |
| `_extract_smb_signing_finding()` | Emits an SMB-signing finding from either a host script or a port script; the port fields remain null for host-scoped NSE output. | `findings.py:161` |
| `_extract_smbv1_finding()` | Emits an SMBv1 finding from either script scope while rejecting SMB2-only protocol output. | `findings.py:200` |
| `_extract_generic_findings()` | Fallback for unknown scripts: generic vuln-table walk, else CVE-regex scrape. | `findings.py:64` |

## How it connects

- **Upstream** — `extract_findings` and `build_host_payload` are called by
  [`ScanRunner._build_payload`](/hardware-agent/scanner/runner.md) /
  [stages](/hardware-agent/scanner/stages.md); it consumes
  [models](/hardware-agent/scanner/models.md) (`HostInfo`, `PortInfo`, `ScriptResult`) whose NSE
  tables come from [`parse_nse_node`](/hardware-agent/utils.md).
- **Downstream** — `ScanPayload` is serialized by
  [workspace `write_scan_result`](/hardware-agent/scanner/workspace.md) and rendered by the TUI's
  scan-view ([tui](/hardware-agent/tui.md)). It mirrors the shared [contracts](/contracts.md).
- **Assessment** — [`assess_hosts`](/hardware-agent/assessment.md) produces the profile and exposure
  fields without mutating original host/port observations.

## Notes / gotchas

- **`HostPayload` (formerly `DevicePayload`).** ADR-013 retired the frozen ingest word "device" from
  the wire; the agent now emits `ScanPayload.hosts` (`HostPayload[]`) end to end, matching the
  domain term **host** used everywhere else in the agent. See [glossary](/glossary.md).
- `scan_mode` is `Literal["quick","standard","extensive","nspi","max"]` — no `full`; the legacy mode
  is being removed in favor of `max`.
- The Modbus payloads reject extra fields, bound device-supplied strings and lists, and omit raw
  values and summaries. A missing digest key leaves `value_digest=null` without stopping the scan.
- `smb2-security-mode` and `smb-protocols` commonly arrive under Nmap's `<hostscript>`, where no
  port is attached. Their extractors therefore preserve `port=None` instead of dropping the
  finding; descriptions mention `TCP/<port>` only when the script was port-scoped.
- The full OpenAPI surface still diverges from what is implemented on the backend today, but ingest
  is no longer the gap: DMI-63 mounted `POST /api/v1/scans` alongside the read path
  (`GET /hosts`, `/scans/{id}`, `/findings`) — see [contracts](/contracts.md).
- **These models are gated against the shared contract.** `hardware-agent/tests/test_contract_models.py`
  asserts that payload fields emitted by the agent are properties of the matching
  `contracts/openapi/openapi.yaml` schema, and that every contract-`required` field is present. All
  relevant schemas declare `additionalProperties: false`, so a field added here without updating the
  contract is a **`422`** at ingest, not a silently ignored extra. Contract-*optional* fields the
  agent omits are allowed. This is the agent-side mirror of
  `backend/tests/test_contract_fidelity.py`.

# Citations

[1] [ADR-011 — Pi command channel](../../../docs/adr/ADR-011-pi-command-channel.md)
[2] [ADR-004 — scan methodology](../../../docs/adr/ADR-004-scan-methodology.md)
[3] [ADR-013 — ingest host-vocabulary unification](../../../docs/adr/ADR-013-ingest-host-vocabulary-unification.md)
