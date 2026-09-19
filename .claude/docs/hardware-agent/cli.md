---
type: Entry Point
title: cli / headless / config / paths — entry points & configuration
description: The dmitri CLI dispatcher, the headless entrypoint, scan tuning (config.py), and persisted user prefs (paths.py).
resource: hardware-agent/src/agent/cli.py
tags: [hardware-agent, cli, headless, config, entrypoint]
timestamp: 2026-09-12T21:23:47Z
---

# cli / headless / config / paths

## Purpose

These four modules are how a scan is *started* and *tuned*. `cli.py` is the `dmitri` console-script
dispatcher; `headless.py` is the non-interactive entrypoint (and the foundation the
[Pi daemon](/hardware-agent/daemon.md) sits on); `config.py` holds the scan-tuning knobs and
per-mode Nmap/NSE script sets; `paths.py` holds persisted user preferences (the workspace location)
and OS-aware defaults.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `main()` | Dispatches argv: bare/`start`→TUI; `agent …`→`_run_agent`; else usage exit 2. | `cli.py:11` |
| `_run_tui()` | Nmap preflight, then `DmitriApp().run()`. | `cli.py:41` |
| `_run_agent()` | Arity guard → `_check_nmap()` → zero args start the daemon; two args run a general or default NSPi scan; three args select an explicit NSPi submode. One-shot scans print a JSON result line and exit with `EXIT_CODES`. | `cli.py:53` |
| `run_headless_scan()` | Validates input and NSPi depth, resolves the workspace, constructs a `ScanRunner` + `run_blocking()`, captures the payload via callbacks, writes the result, and returns a `HeadlessScanResult`. Optional `bind_cancel` receives `ScanRunner.request_cancel` before the run starts; the daemon uses it to stop a scan when the channel parks. | `headless.py:89` |
| `HeadlessScanResult` / `EXIT_CODES` | Outcome (`completed`/`partial`/`fatal`) + payload/path/error; exit map `{completed:0, partial:10, fatal:20}` (invalid input → 2). | `headless.py:25`, `headless.py:32` |
| `StderrReporter` | `ScanReporter` that prints each event message to stderr. | `headless.py:36` |
| `AgentSettings` | Scan-tuning dataclass: subnet, mode, `nmap_path`, `min_cvss`, workers/batching, version intensity, deadline, retry/breaker policy, and NSPi submode. | `config.py:20` |
| `validate_nspi_depth()` | Rejects unsupported NSPi depths before the runner sends active requests. | `config.py:139` |
| `SCAN_MODES` + deep-scan tuning | `quick/standard/extensive/nspi/max`; the sole NSE catalog (`deep_stage_scripts`), the effective `-sV` intensity floor, CVSS thresholds, and subprocess timeouts. | `config.py:10`, `config.py:83`, `config.py:96`, `config.py:134` |
| `DmitriConfig` + `load_config` / `save_config` | Persisted `results_dir`; `load_config` returns `None` on first run (drives the Setup screen); `save_config` writes atomically. | `paths.py:16`, `paths.py:44`, `paths.py:56` |
| `default_results_dir` / `default_config_path` | OS-aware defaults (XDG on Linux/macOS, `LOCALAPPDATA` on Windows). | `paths.py:22`, `paths.py:33` |

## How it connects

- **Upstream** — `dmitri = agent.cli:main` (installed console script); `run_headless_scan` is also
  the in-process entry the [Pi daemon](/hardware-agent/daemon.md) calls, in a worker thread.
- **Downstream** — [`DmitriApp`](/hardware-agent/tui.md), [`ScanRunner`](/hardware-agent/scanner/runner.md),
  [`write_scan_result`](/hardware-agent/scanner/workspace.md),
  [`ScanPayload`](/hardware-agent/normalize.md), the [progress](/hardware-agent/scanner/progress.md)
  reporter protocol. `config.py`'s `AgentSettings` + deep-stage script/tuning helpers drive
  [discovery](/hardware-agent/discovery.md) and [stages](/hardware-agent/scanner/stages.md).

## Notes / gotchas

- **Two front doors, one runner.** `run_headless_scan` and the TUI's
  [`ScanProgressScreen`](/hardware-agent/tui.md) each construct a `ScanRunner` and thread
  `workspace_root` — the invariant the CLAUDE.md integration rule protects. The daemon is a *third*
  front door but not a third runner: it calls `run_headless_scan` with one extra hook, `bind_cancel`,
  and adds no parameter to `ScanRunner`.
- **`_check_nmap()` runs once, before dispatch, for both arities.** A missing scanner exits `20`
  with the installation guidance before the daemon module is even imported, so no socket is ever
  dialed. There is no version probe or background health check; if nmap disappears later, the
  affected command just fails through `failed/scan_failed`.
- `dmitri agent` accepts zero, two, or three scan arguments; the three-argument form must start
  with `nspi`. `active_validation` is refused before any active request.
- `SCAN_MODES` has no `full`: the legacy `full` mode is being removed in favor of `max`.
- `config.py` (scan tuning, ephemeral per run) and `paths.py` (persisted user prefs, a config file)
  are deliberately separate concerns despite both being "configuration".

# Citations

[1] [ADR-012 — headless exit-code contract](../../../docs/adr/ADR-012-headless-exit-code-contract.md)
[2] [ADR-011 — Pi command channel](../../../docs/adr/ADR-011-pi-command-channel.md)
[3] [ADR-010 — scan contingency policy](../../../docs/adr/ADR-010-scan-contingency-policy.md)
