---
type: Package Overview
title: hardware-agent — package overview
description: What the hardware-agent package is, its scan pipeline, and the front doors that drive it — TUI, headless CLI, and the remote command daemon.
resource: hardware-agent/src/agent/
tags: [hardware-agent, scan-pipeline, overview]
timestamp: 2026-09-12T21:23:47Z
---

# hardware-agent — package overview

`hardware-agent` is the Python package (`hardware-agent/src/agent/`) that *performs* scans — the
[agent](/glossary.md) in domain terms. It runs an Nmap + NSE pipeline over a subnet, normalizes the
raw XML into the shared [`ScanPayload`](/hardware-agent/normalize.md) contract, and writes the
result to disk. Since DMI-65 it has a signed upload client
([transport](/hardware-agent/transport.md)), and since DMI-66 something finally calls it: the
[daemon](/hardware-agent/daemon.md) takes commands off the backend's WebSocket
([command-channel](/hardware-agent/command-channel.md)), runs the headless scan, and uploads the
result. `AGENT_VERSION` / `APP_VERSION` is `0.1.4`.

## The scan pipeline

The pipeline is **linear** and lives inside one method — [`ScanRunner._run()`](/hardware-agent/scanner/runner.md).
There is no separate orchestrator class:

1. **Host discovery** — `-sn -PE -T4` over the subnet → live [`HostInfo`](/hardware-agent/scanner/models.md).
   See [discovery](/hardware-agent/discovery.md).
2. **Port discovery** — hosts chunked into batches and scanned across a thread pool: default
   top-1000, top-10000, all ports, or NSPi's two merged passes. It runs no `-sV` or NSE scripts;
   regular modes retain `-O`, while NSPi's bounded OS probe remains in deep inspection. See
   [stages](/hardware-agent/scanner/stages.md).
3. **Deep inspection** — the primary enrichment pass per eligible host: `-sV` + the mode's full NSE
   set, including `vulners` CVE correlation. A failed or empty pass can retry service detection
   alone; a failed recovery leaves that host incomplete and preserves earlier port evidence.
4. **OT inspection** (NSPi) — bounded Modbus inventory or read-only mapping via [`ot/`](/hardware-agent/ot.md)
   (`pymodbus`). Wall-clock ceilings are `MAX_OT_STAGE_SECONDS` / `MAX_OT_HOST_SECONDS`; a host's
   limit does not stop later hosts while the stage still has time.
5. **Normalize** — NSE output → [findings](/hardware-agent/normalize.md); hosts → `HostPayload`s
   including `industrial_services`; assembled into a `ScanPayload` and written to `results/` by
   [workspace](/hardware-agent/scanner/workspace.md).

Each stage runs under cancellation and deadline guards, with a per-unit retry + circuit-breaker
contingency policy (ADR-010). Successful evidence is preserved and the result is marked partial if
any port batch or eligible deep-inspection host is skipped.

## Front doors

The same [`ScanRunner`](/hardware-agent/scanner/runner.md) is constructed from two places, each
threading `workspace_root` through (this is the dual-front-door design the CLAUDE.md integration
rule guards). The remote entries reach it *through* `run_headless_scan` rather than constructing a
runner of their own:

| Front door | Entry | How it runs |
|-----------|-------|-------------|
| TUI | [`ScanProgressScreen`](/hardware-agent/tui.md) via `dmitri` / `dmitri start` | `ScanRunner.start()` on a worker thread; events bridged to Textual messages. |
| Headless CLI | `dmitri agent <mode> <subnet>` → [`run_headless_scan`](/hardware-agent/cli.md) | `ScanRunner.run_blocking()`; prints a JSON outcome line and exits 0/10/20 (ADR-012). |
| Remote daemon | bare `dmitri agent` → [`AgentDaemon`](/hardware-agent/daemon.md) | Backend command → `run_headless_scan` in an `asyncio.to_thread` worker → ingest upload; lifecycle reported on the WS channel. |
| In-process | direct `run_headless_scan(...)` call | Same blocking path; returns a `HeadlessScanResult`. |

## Package layout

| Area | Doc |
|------|-----|
| CLI / headless / config / paths | [cli](/hardware-agent/cli.md) |
| Scan engine | [scanner](/hardware-agent/scanner/index.md) |
| Discovery stages | [discovery](/hardware-agent/discovery.md) |
| Contracts + findings | [normalize](/hardware-agent/normalize.md) |
| Network + XML helpers | [utils](/hardware-agent/utils.md) |
| Signed ingest client | [transport](/hardware-agent/transport.md) |
| Signed WS command client + shared signer | [command-channel](/hardware-agent/command-channel.md) |
| Remote command daemon | [daemon](/hardware-agent/daemon.md) |
| Textual TUI | [tui](/hardware-agent/tui.md) |

## Tech stack

Python 3.13, Textual (TUI), Pydantic v2 (contracts), Nmap + NSE (engine), `psutil`, stdlib threads,
`uv`, plus `httpx` + `cryptography` (added by DMI-65 for the ingest client) and `websockets` (added
by DMI-66 for the command channel). Installed console script: `dmitri = agent.cli:main`.

# Citations

[1] [ADR-004 — scan methodology](../../../docs/adr/ADR-004-scan-methodology.md)
[2] [ADR-010 — scan contingency policy](../../../docs/adr/ADR-010-scan-contingency-policy.md)
[3] [ADR-012 — headless exit-code contract](../../../docs/adr/ADR-012-headless-exit-code-contract.md)
