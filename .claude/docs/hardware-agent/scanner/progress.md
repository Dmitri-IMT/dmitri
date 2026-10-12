---
type: Module
title: scanner/progress — scan events & progress mapping
description: The ScanEvent stream, the ScanReporter protocol, and the ProgressMapper that turns events into a monotonic 0-100% for the UI.
resource: hardware-agent/src/agent/scanner/progress.py
tags: [hardware-agent, scanner, progress, events]
timestamp: 2026-10-02T20:00:00Z
---

# scanner/progress — events & progress mapping

## Purpose

`progress.py` defines the event vocabulary the pipeline emits and the machinery that maps those
events to a monotonic progress percentage. It is the decoupling seam between the worker thread and
whatever renders progress — a TUI screen or a stderr reporter — via the `ScanReporter` protocol.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `ScanEventKind` | Event vocabulary for discovery, ports, deep inspection, OT inspection (`modbus_host_inspected`, `ot_stage_deadline`), normalization, completion, and failure. | `progress.py:6` |
| `ScanEvent` | Frozen dataclass: kind, message, stage counters, open/filtered port totals, industrial service total, `ip`, and `deadline_seconds` for `ot_stage_deadline`. | `progress.py:28` |
| `ScanReporter` | `Protocol` with `emit(event)` — the reporter interface the runner writes to. | `progress.py:42` |
| `StageWeights` / `STAGE_WEIGHTS` | Per-mode weight of each stage's contribution to 100%. | `progress.py:47`, `progress.py:54` |
| `target_pct()` | Maps a single event to its target percentage given the mode's weights. | `progress.py:64` |
| `ProgressMapper` | Stateful wrapper over `target_pct` that never lets the percentage go backwards. | `progress.py:97` |

## How it connects

- **Upstream** — `ScanEvent`s are emitted by [`ScanRunner`](/hardware-agent/scanner/runner.md) and
  the [stages](/hardware-agent/scanner/stages.md) through the reporter.
- **Downstream** — implementations of `ScanReporter`: the TUI's `_ScreenReporter` and
  `ProgressMapper` in [tui](/hardware-agent/tui.md), and `StderrReporter` in
  [headless](/hardware-agent/cli.md).
- The headless daemon also passes `LiveProgressReporter` through the existing reporter argument.
  It maps stage events and confirmed counters to compact snapshots, throttles in-stage updates to
  one every two seconds, and leaves WebSocket and disk I/O to the daemon. Port completion reports
  open and filtered counts separately; OT completion reports industrial service totals.

## Notes / gotchas

- `ProgressMapper.update` is deliberately monotonic — a smoother UI, at the cost of never regressing
  even if a later event would map lower.
- `STAGE_WEIGHTS` has no `full` key: the legacy `full` mode is being removed in favor of `max`.
