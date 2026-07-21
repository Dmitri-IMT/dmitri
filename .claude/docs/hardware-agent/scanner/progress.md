---
type: Module
title: scanner/progress — scan events & progress mapping
description: The ScanEvent stream, the ScanReporter protocol, and the ProgressMapper that turns events into a monotonic 0-100% for the UI.
resource: hardware-agent/src/agent/scanner/progress.py
tags: [hardware-agent, scanner, progress, events]
timestamp: 2026-07-21T00:00:00Z
---

# scanner/progress — events & progress mapping

## Purpose

`progress.py` defines the event vocabulary the pipeline emits and the machinery that maps those
events to a monotonic progress percentage. It is the decoupling seam between the worker thread and
whatever renders progress — a TUI screen or a stderr reporter — via the `ScanReporter` protocol.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `ScanEventKind` | `Literal` of every event: `discovery_started`, `hosts_found`, `port_stage_*`, `port_batch_done`, `deep_stage_*`, `host_inspected`, `unit_timed_out`/`unit_failed`, `normalize_started`, `completed`, `failed`. | `progress.py:6` |
| `ScanEvent` | Frozen dataclass carrying the kind plus optional counts (`hosts_*`, `batches_*`, `ports_open`, `units_*`, `ip`). | `progress.py:24` |
| `ScanReporter` | `Protocol` with `emit(event)` — the reporter interface the runner writes to. | `progress.py:37` |
| `StageWeights` / `STAGE_WEIGHTS` | Per-mode weight of each stage's contribution to 100%. | `progress.py:42`, `progress.py:49` |
| `target_pct()` | Maps a single event to its target percentage given the mode's weights. | `progress.py:58` |
| `ProgressMapper` | Stateful wrapper over `target_pct` that never lets the percentage go backwards. | `progress.py:85` |

## How it connects

- **Upstream** — `ScanEvent`s are emitted by [`ScanRunner`](/hardware-agent/scanner/runner.md) and
  the [stages](/hardware-agent/scanner/stages.md) through the reporter.
- **Downstream** — implementations of `ScanReporter`: the TUI's `_ScreenReporter` and
  `ProgressMapper` in [tui](/hardware-agent/tui.md), and `StderrReporter` in
  [headless](/hardware-agent/cli.md).

## Notes / gotchas

- `ProgressMapper.update` is deliberately monotonic — a smoother UI, at the cost of never regressing
  even if a later event would map lower.
- `STAGE_WEIGHTS` has no `full` key: the legacy `full` mode is being removed in favor of `max`.
