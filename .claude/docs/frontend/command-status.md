---
type: Module
title: frontend command status
description: commandStatusPill maps every CommandStatus to tone and label; isTerminalCommandStatus stops the Agents poll.
resource: frontend/src/lib/commandStatus.ts
tags: [frontend, agents, commands]
timestamp: 2026-08-29T00:00:00Z
---

# frontend command status

## Purpose

A React-free sibling of [scan-status](./scan-status.md) for the Pi command lifecycle. The Agents
screen's status pill and the 5s poll's stop condition both branch here so the seven `CommandStatus`
values cannot drift from each other or from `ScanStatus`.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `commandStatusPill(status)` | Maps all seven `CommandStatus` values to a `StatusPillTone` and label. Unfinished (`queued`/`delivered`/`running`/`uploading`) → running tone; `done` → neutral; `failed` and `expired` share the failed tone but carry **different labels**. | `frontend/src/lib/commandStatus.ts:21` |
| `isTerminalCommandStatus(status)` | True for `done`, `failed`, and `expired` only; `undefined` is false so a failed poll does not stop asking. Drives `refetchInterval` in [agents-screen](./agents-screen.md)'s `useScanCommand`. | `frontend/src/lib/commandStatus.ts:25` |

## How it connects

- Consumed by [agents-screen](./agents-screen.md)'s `CommandStatus` and `useScanCommand`.
- Renders through [tables](./tables.md)'s `StatusPill` — same three tones as scan status; no fourth
  tone for `expired` (copy and next step disambiguate from `failed`).
- The `failed` sentence beside the pill comes from [scan-failure-reasons](./scan-failure-reasons.md)'s
  `scanFailureReason()`, not from this module.

## Notes / gotchas

- **Not an extension of `scanStatus.ts`.** `ScanStatus` and `CommandStatus` are different enums on
  different resources; one module switching on both would make predicates like `isUnfinished`
  ambiguous.
- **`expired` and `failed` share a tone deliberately.** TRUTH requires different words and next
  steps, not different ink — see spec 040 §6.5.

# Citations

[1] [specs/040-agents-scan-trigger/TRUTH.md](../../../specs/040-agents-scan-trigger/TRUTH.md)
