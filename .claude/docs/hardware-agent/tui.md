---
type: Module
title: tui — Textual application
description: The Textual application — app root, screens (setup, home, wizard, progress, view, past scans), and shared widgets.
resource: hardware-agent/src/agent/tui/
tags: [hardware-agent, tui, textual, ui]
timestamp: 2026-07-21T00:00:00Z
---

# tui — Textual application

## Purpose

`tui/` is the interactive front door: a Textual app whose screens walk the operator from first-run
setup through a scan wizard into live progress and result views. The one screen that actually binds
to the scan engine is `ScanProgressScreen`, which constructs and drives a
[`ScanRunner`](/hardware-agent/scanner/runner.md) — the second of the two runner constructor sites
the CLAUDE.md integration rule requires to stay in sync.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `DmitriApp` | Root `App`; bindings `ctrl+q` (quit, aborts an active scan first) / `ctrl+t` (settings, blocked during a scan); `on_ready` pushes setup (no config) or home. | `tui/app.py:18` |
| `DmitriScreen` | Base screen = header + `compose_body()` hook + footer. | `tui/screens/base.py:11` |
| `DmitriHeader` / `CircleSpinner` / `SPINNER_FRAMES` / `APP_VERSION` | Shared widgets; `APP_VERSION = "0.1.4"`. | `tui/widgets.py:15`, `:34`, `:12`, `:10` |
| `SetupScreen` (S0) | First-run workspace picker; validates, `save_config`, `ensure_workspace_layout`, pushes home. | `tui/screens/setup.py:22` |
| `SettingsScreen` (S1) | Modal (`ctrl+t`) to edit `results_dir`; Save/Cancel. | `tui/screens/settings.py:23` |
| `HomeScreen` (H) | Central `OptionList`: Start scan → wizard; View scan → last payload; Past scans. Receives `(subnet, mode)` and pushes `ScanProgressScreen`; writes the result + summary band on completion. | `tui/screens/home.py:25` |
| `NetworkScreen` (S2) | Lists IPv4 interfaces/subnets via `psutil` (`ctrl+r` refresh) → `ScanCategoryScreen`. | `tui/screens/network.py:36` |
| `ScanCategoryScreen` / `ScanModeScreen` (S3) | General vs NSPi → mode picker (General: quick/standard/extensive/max; NSPi: nspi) → dismisses `(subnet, mode)`. | `tui/screens/scan_category.py:13`, `tui/screens/scan_mode.py:32` |
| `ScanProgressScreen` (S4) | Constructs `ScanRunner(..., reporter=_ScreenReporter, on_complete, on_error, workspace_root)` and `.start()`s it; smoothed `ProgressBar` (`ProgressMapper`), `RichLog` feed, terminal success/partial/fatal states; `ctrl+x` → `runner.request_cancel()`. | `tui/screens/scan_progress.py:26` |
| `ScanViewScreen` (S7) | Renders a `ScanPayload` (in-memory or JSON) into devices/ports/vulns/summary; `MODE_LABELS`, `SEVERITY_COLORS`, IO-Link banner detection. | `tui/screens/scan_view.py:49` |
| `PastScansScreen` (S6) | Lists `results/*.json` (`ScanEntry`), newest-first (`ctrl+r`) → `ScanViewScreen`. | `tui/screens/past_scans.py:29` |

## How it connects

- **Upstream** — launched by [`cli._run_tui`](/hardware-agent/cli.md) (`DmitriApp().run()`).
- **Downstream** — [`ScanRunner`](/hardware-agent/scanner/runner.md),
  [progress](/hardware-agent/scanner/progress.md) (`ProgressMapper`, `ScanEvent`, `ScanReporter`),
  [`ScanPayload`](/hardware-agent/normalize.md), [paths](/hardware-agent/cli.md) (`load_config` /
  `save_config`), and [workspace](/hardware-agent/scanner/workspace.md)
  (`ensure_workspace_layout` / `write_scan_result`).

Navigation: `setup?` → home → Start scan → network → category → mode → (home) → progress (runs
`ScanRunner`) → view. Side paths: home → view (last), home → past scans → view. Settings is a global
modal.

## Notes / gotchas

- `ScanProgressScreen._ScreenReporter.emit` runs on the worker thread and only `post_message`s into
  Textual; `on_complete`/`on_error` cross back via `call_from_thread`. This thread boundary is why
  the reporter/callback seam exists.
- The screen surfaces the **device** wording from the payload (e.g. "Done — N devices"); the
  in-agent concept is a [host](/glossary.md) — the rename boundary is the ingest payload only.
- A partial result with no devices dismisses silently; a fatal error keeps nothing and hides the
  "View scan" button.
