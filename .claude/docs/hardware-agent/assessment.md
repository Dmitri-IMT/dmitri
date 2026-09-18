---
type: Module
title: assessment — local attack-surface and device profiling
description: The deterministic, versioned local policy that turns accepted scan evidence into endpoint exposures and conservative device profiles.
resource: hardware-agent/src/agent/assessment/analyzer.py
tags: [hardware-agent, assessment, attack-surface, profiling, policy]
timestamp: 2026-09-18T00:00:00Z
---

# assessment — local attack-surface and device profiling

## Purpose

`assessment/` interprets evidence already accepted by the scanner. It performs no network or cloud
lookup. For each open endpoint it emits one attack-surface exposure, and for each host it emits a
conservative device profile using the existing nine-value machine-type vocabulary. The frozen
policy version makes stored results reproducible and keeps historical scans from being silently
reclassified.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `LOCAL_ASSESSMENT_POLICY_VERSION` | Version written on every newly assessed scan. | `hardware-agent/src/agent/assessment/policy.py:7` |
| `ExposureRole` / `ExposureAttention` | Closed role and operator-attention vocabularies; attention is not vulnerability severity. | `hardware-agent/src/agent/assessment/policy.py:20` |
| `AssessmentResult` | Immutable result containing host profiles and endpoint exposures. | `hardware-agent/src/agent/assessment/analyzer.py:63` |
| `assess_hosts()` | Deduplicates open endpoints deterministically, profiles every host, and emits one exposure per accepted open endpoint. | `hardware-agent/src/agent/assessment/analyzer.py:937` |
| `_profile_host()` | Combines bounded manufacturer, hostname, OS, service, product, CPE, certificate, and industrial signals; records conflicts and limitations instead of inventing identity. | `hardware-agent/src/agent/assessment/analyzer.py:308` |
| `_exposure_for()` | Assigns endpoint role, confidence, reason, evidence, and informational/review/priority attention. | `hardware-agent/src/agent/assessment/analyzer.py:812` |

## How it connects

- **Upstream** — [`ScanRunner._build_payload()`](/hardware-agent/scanner/runner.md) calls
  `assess_hosts()` after discovery, deep inspection, and optional OT inspection have accepted their
  evidence.
- **Inputs** — scanner [`HostInfo` / `PortInfo`](/hardware-agent/scanner/models.md); no raw response
  bodies or external services.
- **Outputs** — bounded [`DeviceProfilePayload` and `ExposurePayload`](/hardware-agent/normalize.md),
  consumed by the local [TUI](/hardware-agent/tui.md) and shared [ingest contract](/contracts.md).

## Notes / gotchas

- Every open `(ip, port, protocol)` appears at most once; closed and filtered ports do not.
- An exposure is reachable attack surface, not proof of a vulnerability. Findings remain separate.
- Evidence is sorted and bounded, credential-like material is redacted, and duplicate-port choice is
  deterministic.
- A legacy payload with no policy version remains readable, but readers show assessment as
  unavailable instead of reconstructing it.

# Citations

[1] [spec 047 — attack surface and IoT profiling](../../../specs/047-attack-surface-iot-profiling/TRUTH.md)
