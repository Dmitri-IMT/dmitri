---
type: Module
title: normalize — contracts & findings extraction
description: The Pydantic wire contracts (ScanPayload, HostPayload) and the NSE-to-findings extractor that produce the shared on-disk payload.
resource: hardware-agent/src/agent/normalize/contracts.py
tags: [hardware-agent, normalize, contracts, findings, pydantic]
timestamp: 2026-07-22T00:00:00Z
---

# normalize — contracts & findings

## Purpose

`normalize/` turns the agent's in-memory scan state into the shared wire contract. `contracts.py`
holds the Pydantic models serialized to disk (and, in future, uploaded); `findings.py` walks parsed
NSE output and emits structured `FindingPayload`s. The `ScanPayload` is the cross-component boundary
object — the seam that binds the agent to the (planned) backend.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `ScanPayload` | Top-level result: `scan_id`, `timestamp`, `subnet` (CIDR), `scan_mode`, `hosts`, `findings`, `metadata`. | `contracts.py:50` |
| `HostPayload` | A host on the wire: `ip`, `mac` (regex), `hostname`, `vendor`, `ports`. Formerly `DevicePayload`. | `contracts.py:25` |
| `PortPayload` | A port: `port` (1–65535), `protocol` enum, `state` enum, `service`, `version`. | `contracts.py:17` |
| `FindingPayload` | A vulnerability/observation: ip/port/service, `cve_id` (regex), `cvss_score` (0–10), `severity` enum, title/description/recommendation/evidence, references. | `contracts.py:33` |
| `extract_findings()` | Walks each host's host-scripts and port-scripts, dispatches per script id, dedups by `(ip, port, script, cve/title)`. | `findings.py:17` |
| `_EXTRACTORS` | Dispatch table: `vulners`, `smb2-security-mode`, `smb-protocols`, `http-methods`, `ssh-auth-methods`, `ssl-cert`, `ssl-enum-ciphers`, `ftp-anon`. | `findings.py:707` |
| `_extract_vulners_findings()` | Correlates CVE + CVSS from the `vulners` NSE table → severity. | `findings.py:104` |
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

## Notes / gotchas

- **`HostPayload` (formerly `DevicePayload`).** ADR-013 retired the frozen ingest word "device" from
  the wire; the agent now emits `ScanPayload.hosts` (`HostPayload[]`) end to end, matching the
  domain term **host** used everywhere else in the agent. See [glossary](/glossary.md).
- `scan_mode` is `Literal["quick","standard","extensive","nspi","max"]` — no `full`; the legacy mode
  is being removed in favor of `max`.
- The full OpenAPI surface diverges from what is implemented on the backend today; the backend's
  read path (`GET /hosts`, `/scans/{id}`, `/findings`) is wired, ingest is not — see
  [contracts](/contracts.md).

# Citations

[1] [ADR-011 — Pi command channel](../../../docs/adr/ADR-011-pi-command-channel.md)
[2] [ADR-004 — scan methodology](../../../docs/adr/ADR-004-scan-methodology.md)
[3] [ADR-013 — ingest host-vocabulary unification](../../../docs/adr/ADR-013-ingest-host-vocabulary-unification.md)
