---
type: Module
title: scanner/workspace — results & logs layout
description: The on-disk results/ + logs/ workspace layout — result serialization, per-run Nmap logging, and pruning.
resource: hardware-agent/src/agent/scanner/workspace.py
tags: [hardware-agent, scanner, workspace, persistence]
timestamp: 2026-10-17T00:00:00Z
---

# scanner/workspace — results & logs layout

## Purpose

`workspace.py` manages everything the agent writes to disk under the workspace root: the `results/`
directory of normalized scan JSON and the `logs/` directory of per-invocation Nmap traces. It
serializes the `ScanPayload`, names and populates run folders, and prunes both trees to bounded
sizes. The daemon persists each result before submitting the same payload to the ingest client.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `ensure_workspace_layout()` | Creates `results/` + `logs/` (idempotent) and migrates legacy root-level JSON into `results/`. | `workspace.py:17` |
| `write_scan_result()` | Serializes a `ScanPayload` to `results/<ISO-ts>_<subnet-slug>.json`, then prunes to 10. | `workspace.py:158` |
| `make_run_folder_name()` | Builds a unique, timestamped run-folder basename `{date}-{time}-{stage}-{uniq}`. | `workspace.py:29` |
| `build_nmap_argv()` | Injects `-oX`, `-v`, and `--stats-every 30s` into Nmap args without duplicating. | `workspace.py:40` |
| `write_meta_json()` | Writes `meta.json` (run id, argv, timing, exit code, `terminated_by`, parent scan id) per the metadata schema. | `workspace.py:55` |
| `prune_logs()` | Keeps the newest `max_scans` run groups (grouped by parent scan id), always retaining the most recent failed group; skips protected/active dirs. | `workspace.py:100` |
| `prune_results()` | Deletes the oldest `results/*.json` beyond `max_count`. | `workspace.py:135` |

## How it connects

- **Upstream** — `ensure_workspace_layout` from [tui/app](/hardware-agent/tui.md), setup, and
  settings; `write_scan_result` from [headless](/hardware-agent/cli.md) and the TUI home/progress
  flow; the run-folder + `meta.json` helpers from
  [`LoggedNmapRunner`](/hardware-agent/scanner/nmap.md).
- **Downstream** — the [`ScanPayload`](/hardware-agent/normalize.md) contract it serializes.

## Notes / gotchas

- A completed scan on disk is the domain [scan](/glossary.md) result — the `ScanPayload` written
  here, later read back by the TUI's scan-view and past-scans screens.
- Current results include finding-evidence policy metadata when emitted by the runner. Legacy files
  without that version remain readable and are presented as unavailable.
- `prune_logs` groups run folders by `parent_scan_id` from each `meta.json`, so all Nmap runs of one
  scan are kept or dropped together, and the newest failed scan's logs survive for debugging.
