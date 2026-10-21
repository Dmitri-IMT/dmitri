---
type: Module
title: normalize — contracts & findings extraction
description: The Pydantic scan payloads, versioned finding evidence metadata, local interpretation, and NSE/targeted finding extraction.
resource: hardware-agent/src/agent/normalize/contracts.py
tags: [hardware-agent, normalize, contracts, findings, pydantic]
timestamp: 2026-10-17T00:00:00Z
---

# normalize — contracts & findings

## Purpose

`normalize/` turns the agent's in-memory scan state into the shared wire contract. `contracts.py`
holds the Pydantic models serialized to disk and uploaded; `findings.py` walks parsed NSE and
targeted output and emits structured `FindingPayload`s with bounded evidence observations, while
keeping unattached negative and inconclusive NSE observations at scan level. `coverage.py` flattens
recorded stage and targeted results into `CoverageUnitPayload`s. The `ScanPayload` is the cross-component boundary
object that binds the agent to the backend ingest route. Modbus process values remain on the Pi;
only range status and an optional keyed digest cross this boundary.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `ScanPayload` | Top-level result including optional assessment and finding-evidence policy versions, endpoint exposures and bounded standalone observations; missing evidence policy marks a legacy result. | `contracts.py:344` |
| `FindingEvidenceObservationPayload` | Bounded witness tied to a condition and optional host/endpoint/unit, with method, result, source, rule/version, excerpt and primitive facts. | `contracts.py:248` |
| `CoverageUnitPayload` / `CoverageObservationPayload` | One checked unit per `ip` + `stage` with `outcome`, `reason_code`, `evidence_source`, `issue_keys`, and bounded `observations`. Mirrored by the backend schema. | `contracts.py:320` |
| `HostPayload` | A host on the wire: original observations plus optional `machine_type` and `device_profile`. | `contracts.py:236` |
| `AssessmentEvidencePayload` | Bounded evidence item with a closed kind, source, and normalized value. | `contracts.py:67` |
| `ExposurePayload` | One open endpoint's role, attention, confidence, reason, and evidence; separate from findings. | `contracts.py:96` |
| `DeviceProfilePayload` | Evidence-backed machine type, manufacturer/product/model assessment, confidence, conflicts, and limitations. | `contracts.py:121` |
| `PortPayload` | A port: `port` (1–65535), `protocol` enum, `state` enum, `service`, `version`, CPEs. | `contracts.py:149` |
| `ModbusTcpServicePayload` / `ModbusUnitPayload` | Bounded industrial service and unit evidence. | `contracts.py:224`, `:208` |
| `ModbusAddressRangePayload` | Address, status, timestamp, and optional `hmac-sha256` digest; no process values or aggregates. | `contracts.py:186` |
| `FindingPayload` | A finding with optional stable `issue_key`, up to 16 evidence observations and a truncation flag. | `contracts.py:282` |
| `extract_coverage()` | Flattens each host's `stage_coverage` and `targeted_results` into `CoverageUnitPayload[]`, sanitizing targeted observations. Targeted units skipped by a scan stop (`scan_cancelled`/`scan_timeout`) report `evidence_source="not_run"`. | `coverage.py:15` |
| `extract_findings_and_observations()` | Returns deduplicated findings, up to 512 unattached non-positive NSE observations, and a truncation flag. Supported negative witnesses bind to matching findings; failed or unsupported checks do not negate a finding. | `findings.py:430` |
| `extract_findings()` | Compatibility wrapper. Evidence fields are omitted by default; callers can opt in to the metadata. | `findings.py:412` |
| `assess_local_evidence()` | Applies closed local predicates to retained witnesses and categorizes evidence as supported, conflicting or inconclusive with categorical confidence. | `findings.py:30` |
| `_extract_modbus_read_findings()` | One finding per unit that has a readable range, with that `unit_id`. NSE findings omit `unit_id`. | `findings.py:606` |
| `_EXTRACTORS` | Dispatch table for supported NSE scripts. | `findings.py:1869` |
| `_extract_vulners_findings()` | Correlates CVE + CVSS from the `vulners` NSE table → severity. | `findings.py:1041` |
| `_extract_smb_signing_finding()` | Emits an SMB-signing finding from either a host script or a port script; the port fields remain null for host-scoped NSE output. | `findings.py:1114` |
| `_extract_smbv1_finding()` | Emits an SMBv1 finding from either script scope while rejecting SMB2-only protocol output. | `findings.py:1154` |
| `_extract_generic_findings()` | Fallback for unknown scripts: generic vuln-table walk, else CVE-regex scrape. | `findings.py:992` |

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

- The scan runner emits finding evidence policy version `1` and serializes `issue_key` for
  reconciliation. A finding record is not proof of a vulnerability. Methods and confidence are
  local categories, not percentages or backend enrichment. Evidence is bounded; truncation makes
  interpretation inconclusive. Standalone observations are negative or inconclusive only; positive
  witnesses belong to a finding.
- The offline corpus in `hardware-agent/tests/fixtures/finding_evidence_quality/` compares the
  parser with predictions pinned to revision `471739f`. Its small synthetic examples verify
  regressions and explicit denominators, but do not estimate production precision or recall.
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
