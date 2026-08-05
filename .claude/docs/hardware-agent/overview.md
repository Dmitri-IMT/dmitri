---
type: Package Overview
title: hardware-agent — package overview
description: What the hardware-agent package is, its scan pipeline, and the three front doors that drive it.
resource: hardware-agent/src/agent/
tags: [hardware-agent, scan-pipeline, overview]
timestamp: 2026-08-05T00:00:00Z
---

# hardware-agent — package overview

`hardware-agent` is the Python package (`hardware-agent/src/agent/`) that *performs* scans — the
[agent](/glossary.md) in domain terms. It runs an Nmap + NSE pipeline over a subnet, normalizes the
raw XML into the shared [`ScanPayload`](/hardware-agent/normalize.md) contract, and writes the
result to disk. Since DMI-65 it also *has* a signed upload client —
[transport](/hardware-agent/transport.md) — but nothing in the package calls it yet; the pipeline
still ends at the local file. `AGENT_VERSION` / `APP_VERSION` is `0.1.4`.

## The scan pipeline

The pipeline is **linear** and lives inside one method — [`ScanRunner._run()`](/hardware-agent/scanner/runner.md).
There is no separate orchestrator class:

1. **Host discovery** — `-sn -PE -T4` over the subnet → live [`HostInfo`](/hardware-agent/scanner/models.md).
   See [discovery](/hardware-agent/discovery.md).
2. **Port discovery** — hosts chunked into batches, scanned across a thread pool (`-F` / top-ports /
   `-p-` per mode). See [stages](/hardware-agent/scanner/stages.md).
3. **Deep inspection** — per host, `-sV` + NSE scripts with `vulners` CVE correlation.
4. **Normalize** — NSE output → [findings](/hardware-agent/normalize.md); hosts → `HostPayload`s;
   assembled into a `ScanPayload` and written to `results/` by
   [workspace](/hardware-agent/scanner/workspace.md).

Each stage runs under cancellation and deadline guards, with a per-unit retry + circuit-breaker
contingency policy (ADR-010) so a partial result is preserved when a late stage fails.

## Front doors

The same [`ScanRunner`](/hardware-agent/scanner/runner.md) is constructed from three places, each
threading `workspace_root` through (this is the dual-front-door design the CLAUDE.md integration
rule guards):

| Front door | Entry | How it runs |
|-----------|-------|-------------|
| TUI | [`ScanProgressScreen`](/hardware-agent/tui.md) via `dmitri` / `dmitri start` | `ScanRunner.start()` on a worker thread; events bridged to Textual messages. |
| Headless CLI | `dmitri agent <mode> <subnet>` → [`run_headless_scan`](/hardware-agent/cli.md) | `ScanRunner.run_blocking()`; prints a JSON outcome line and exits 0/10/20 (ADR-012). |
| In-process | direct `run_headless_scan(...)` call | Same blocking path; returns a `HeadlessScanResult`. |

## Package layout

| Area | Doc |
|------|-----|
| CLI / headless / config / paths | [cli](/hardware-agent/cli.md) |
| Scan engine | [scanner](/hardware-agent/scanner/index.md) |
| Discovery stages | [discovery](/hardware-agent/discovery.md) |
| Contracts + findings | [normalize](/hardware-agent/normalize.md) |
| Network + XML helpers | [utils](/hardware-agent/utils.md) |
| Signed ingest client (unwired) | [transport](/hardware-agent/transport.md) |
| Textual TUI | [tui](/hardware-agent/tui.md) |

## Tech stack

Python 3.13, Textual (TUI), Pydantic v2 (contracts), Nmap + NSE (engine), `psutil`, stdlib threads,
`uv`, plus `httpx` + `cryptography` (added by DMI-65 for the ingest client). Installed console
script: `dmitri = agent.cli:main`.

# Citations

[1] [ADR-004 — scan methodology](../../../docs/adr/ADR-004-scan-methodology.md)
[2] [ADR-010 — scan contingency policy](../../../docs/adr/ADR-010-scan-contingency-policy.md)
[3] [ADR-012 — headless exit-code contract](../../../docs/adr/ADR-012-headless-exit-code-contract.md)
