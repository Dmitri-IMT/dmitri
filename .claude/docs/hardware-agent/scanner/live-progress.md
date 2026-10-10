---
type: Module
title: scanner/live-progress — remote scan snapshots
description: Turns scanner events into bounded stage and counter snapshots for the command-channel daemon.
resource: hardware-agent/src/agent/scanner/live_progress.py
tags: [hardware-agent, scanner, progress, daemon]
timestamp: 2026-10-02T00:00:00Z
---

# scanner/live-progress — remote scan snapshots

## Purpose

`live_progress.py` maps the existing `ScanEvent` stream and `ProgressMapper` into small snapshots
that the daemon can send while a headless scan runs. It tracks confirmed machine, port, industrial
service, and vulnerability counts, caps unfinished scans below 100%, and performs no I/O.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `LiveProgressSnapshot` | Immutable stage, percentage, nullable counters, and internal revision. | `live_progress.py:42` |
| `LiveProgressReporter` | Updates counters from events and publishes stage boundaries immediately; in-stage events are coalesced to two seconds. | `live_progress.py:53` |
| `reconcile_payload()` | Replaces interim counts with exact normalized payload totals and sets stage `uploading` at 99%. | `live_progress.py:102` |
| `_stage_for()` | Maps event kinds and scan mode to the public stage vocabulary. | `live_progress.py:133` |

## How it connects

- Implements [`ScanReporter`](/hardware-agent/scanner/progress.md) and is passed through
  `run_headless_scan(reporter=...)` by the [daemon](/hardware-agent/daemon.md).
- The daemon hands each published snapshot to the command channel as `AgentProgress`; final payload
  reconciliation happens before the `uploading` lifecycle status and HTTP ingest.

## Notes / gotchas

- A missing count means its stage has not confirmed it; confirmed zero remains `0`.
- The TUI keeps its own reporter and does not use this remote adapter.
- Snapshots contain no hosts, findings, ports, or raw evidence arrays.
