---
type: Module
title: scanner/nmap — NmapRunner & LoggedNmapRunner
description: NmapRunner / LoggedNmapRunner — run Nmap as a subprocess, parse XML, classify failures, and stream per-invocation logs.
resource: hardware-agent/src/agent/scanner/nmap.py
tags: [hardware-agent, scanner, nmap, subprocess, logging]
timestamp: 2026-07-21T00:00:00Z
---

# scanner/nmap — Nmap process execution

## Purpose

`nmap.py` is the only place the pipeline shells out to the Nmap CLI. `NmapRunner` always requests
XML output, parses it with a namespace-stripped `ElementTree`, classifies non-zero exits into the
scan error hierarchy, and tracks live subprocesses so a scan can be terminated. `LoggedNmapRunner`
is a workspace-aware subclass that additionally streams each invocation to a timestamped run folder
under `logs/`.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `NmapRunner` | Thin Nmap CLI wrapper; resolves the binary, holds a lock + set of active procs. | `nmap.py:89` |
| `NmapRunner.run_xml()` | Runs `nmap <args> -oX -`, maps timeout→`BudgetExceeded`, missing binary→`FatalScanError`, bad XML→`UnitScanError`; returns the parsed root. | `nmap.py:105` |
| `NmapRunner.run_streamed()` | Runs Nmap streaming stdout/stderr to files in a run dir (Nmap writes XML itself via `-oX`). | `nmap.py:136` |
| `NmapRunner.terminate_active()` | Sets the cancelled flag and `kill()`s all tracked procs. | `nmap.py:98` |
| `_classify_nonzero()` | Maps stderr markers to `TransientScanError`, else `UnitScanError`. | `nmap.py:38` |
| `_resolve_nmap_path()` | Finds the Nmap binary (arg → PATH → common locations), else `FatalScanError`. | `nmap.py:58` |
| `_strip_namespaces()` | Strips XML namespaces so plain tag names parse. | `nmap.py:201` |
| `LoggedNmapRunner` | Workspace-aware subclass: per-invocation run folder, streamed output, `meta.json`, and log pruning; overrides `run_xml`. | `nmap.py:207` |
| `LoggedNmapRunner.set_stage()` | Records the current stage for run-folder naming. | `nmap.py:231` |
| `build_runner()` | Returns a caller-supplied runner if given, else a `LoggedNmapRunner` when `workspace_root` is set, else a plain `NmapRunner`. | `nmap.py:318` |
| `AGENT_VERSION` | `"0.1.4"` — stamped into metadata and `meta.json`. | `nmap.py:30` |

## How it connects

- **Upstream** — `build_runner` is called by [`ScanRunner._run()`](/hardware-agent/scanner/runner.md);
  the discovery functions ([discovery](/hardware-agent/discovery.md)) call `run_xml` on whatever
  runner they are handed.
- **Downstream** — the scan errors ([errors](/hardware-agent/scanner/errors.md)); for the logged
  subclass, `build_nmap_argv` / `make_run_folder_name` / `write_meta_json` / `prune_logs`
  ([workspace](/hardware-agent/scanner/workspace.md)).

## Notes / gotchas

- `LoggedNmapRunner.run_xml` is transparent to callers: discovery code calls `run_xml` exactly as it
  would on a plain runner, and the logging/pruning happens behind the interface.
- `terminate_active()` is what makes cancellation *immediate* — `ScanRunner.request_cancel()` calls
  it so in-flight Nmap processes are killed rather than waited out.
- `run_streamed` imports its workspace helpers lazily inside `run_xml` to avoid an import cycle with
  [workspace](/hardware-agent/scanner/workspace.md).

# Citations

[1] [ADR-002 — scanning-tools selection](../../../../docs/adr/ADR-002-scanning-tools-selection.md)
