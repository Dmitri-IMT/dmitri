---
type: Entry Point
title: cli / headless / config / paths — entry points & configuration
description: The dmitri CLI dispatcher, the headless entrypoint, scan tuning (config.py), and persisted user prefs (paths.py).
resource: hardware-agent/src/agent/cli.py
tags: [hardware-agent, cli, headless, config, entrypoint]
timestamp: 2026-07-21T00:00:00Z
---

# cli / headless / config / paths

## Purpose

These four modules are how a scan is *started* and *tuned*. `cli.py` is the `dmitri` console-script
dispatcher; `headless.py` is the non-interactive entrypoint (and the foundation the planned Pi
daemon sits on); `config.py` holds the scan-tuning knobs and per-mode Nmap/NSE script sets;
`paths.py` holds persisted user preferences (the workspace location) and OS-aware defaults.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `main()` | Dispatches argv: bare/`start`→TUI; `agent <mode> <subnet>`→headless; else usage exit 2. | `cli.py:11` |
| `_run_tui()` | Nmap preflight, then `DmitriApp().run()`. | `cli.py:38` |
| `_run_agent()` | Validates args, runs `run_headless_scan` with a `StderrReporter`, prints a JSON result line, exits with `EXIT_CODES`. | `cli.py:50` |
| `run_headless_scan()` | Validates input, resolves the workspace, constructs a `ScanRunner` + `run_blocking()`, captures the payload via callbacks, `write_scan_result`, returns a `HeadlessScanResult`. | `headless.py:63` |
| `HeadlessScanResult` / `EXIT_CODES` | Outcome (`completed`/`partial`/`fatal`) + payload/path/error; exit map `{completed:0, partial:10, fatal:20}` (invalid input → 2). | `headless.py:22`, `headless.py:30` |
| `StderrReporter` | `ScanReporter` that prints each event message to stderr. | `headless.py:34` |
| `AgentSettings` | Scan-tuning dataclass: subnet, mode, `nmap_path`, `min_cvss`, `max_workers=4`, `host_batch_size=8`, `version_intensity`, deadline, `unit_failure_threshold=0.5`, `transient_retries`. | `config.py:11` |
| `SCAN_MODES` + script sets | `quick/standard/extensive/nspi/max`; `port_stage_scripts` / `deep_stage_scripts` / `min_cvss_for_mode` / `subprocess_timeout_for`. | `config.py:8`, `config.py:72`+ |
| `DmitriConfig` + `load_config` / `save_config` | Persisted `results_dir`; `load_config` returns `None` on first run (drives the Setup screen); `save_config` writes atomically. | `paths.py:15`, `paths.py:44`, `paths.py:56` |
| `default_results_dir` / `default_config_path` | OS-aware defaults (XDG on Linux/macOS, `LOCALAPPDATA` on Windows). | `paths.py:22`, `paths.py:33` |

## How it connects

- **Upstream** — `dmitri = agent.cli:main` (installed console script); `run_headless_scan` is also
  the in-process entry the future Pi daemon calls.
- **Downstream** — [`DmitriApp`](/hardware-agent/tui.md), [`ScanRunner`](/hardware-agent/scanner/runner.md),
  [`write_scan_result`](/hardware-agent/scanner/workspace.md),
  [`ScanPayload`](/hardware-agent/normalize.md), the [progress](/hardware-agent/scanner/progress.md)
  reporter protocol. `config.py`'s `AgentSettings` + script sets drive
  [discovery](/hardware-agent/discovery.md) and [stages](/hardware-agent/scanner/stages.md).

## Notes / gotchas

- **Two front doors, one runner.** `run_headless_scan` and the TUI's
  [`ScanProgressScreen`](/hardware-agent/tui.md) each construct a `ScanRunner` and thread
  `workspace_root` — the invariant the CLAUDE.md integration rule protects.
- `SCAN_MODES` has no `full`: the legacy `full` mode is being removed in favor of `max`.
- `config.py` (scan tuning, ephemeral per run) and `paths.py` (persisted user prefs, a config file)
  are deliberately separate concerns despite both being "configuration".

# Citations

[1] [ADR-012 — headless exit-code contract](../../../docs/adr/ADR-012-headless-exit-code-contract.md)
[2] [ADR-011 — Pi command channel](../../../docs/adr/ADR-011-pi-command-channel.md)
[3] [ADR-010 — scan contingency policy](../../../docs/adr/ADR-010-scan-contingency-policy.md)
