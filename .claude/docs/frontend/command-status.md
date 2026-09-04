---
type: Module
title: frontend command status
description: commandStatusLabel maps every CommandStatus to a label; isTerminalCommandStatus stops the device-detail command poll.
resource: frontend/src/lib/commandStatus.ts
tags: [frontend, agents, commands]
timestamp: 2026-09-04T00:00:00Z
---

# frontend command status

## Purpose

A React-free sibling of [scan-status](./scan-status.md) for the Pi command lifecycle. The device
detail status region and the 5s poll's stop condition both branch here so the seven `CommandStatus`
values cannot drift from each other or from `ScanStatus`.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `commandStatusLabel(status)` | Maps all seven `CommandStatus` values to a string. `failed` and `expired` carry **different labels** but the same plain-text presentation. | `frontend/src/lib/commandStatus.ts:15` |
| `isTerminalCommandStatus(status)` | True for `done`, `failed`, and `expired` only; `undefined` is false so a failed poll does not stop asking. Drives `refetchInterval` in [devices-screen](./devices-screen.md)'s `useScanCommand`. | `frontend/src/lib/commandStatus.ts:19` |

## How it connects

- Consumed by [devices-screen](./devices-screen.md)'s `CommandStatus` and `useScanCommand`.
- The `failed` sentence beside the label comes from [scan-failure-reasons](./scan-failure-reasons.md)'s
  `scanFailureReason()`, not from this module.

## Notes / gotchas

- **Not an extension of `scanStatus.ts`.** `ScanStatus` and `CommandStatus` are different enums on
  different resources; one module switching on both would make predicates like `isUnfinished`
  ambiguous.
- **`commandStatusPill` and `StatusPill` are gone** (spec 042). Copy and next steps disambiguate
  `expired` from `failed` — not tone.

# Citations

[1] [specs/040-agents-scan-trigger/TRUTH.md](../../../specs/040-agents-scan-trigger/TRUTH.md)
[2] [specs/042-design-system/TRUTH.md](../../../specs/042-design-system/TRUTH.md)
