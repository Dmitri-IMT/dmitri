---
type: Module
title: frontend command status
description: commandStatusLabel maps every CommandStatus including cancelled; isSettledCommand stops the device-detail command poll once no late results can land.
resource: frontend/src/lib/commandStatus.ts
tags: [frontend, agents, commands, cancel]
timestamp: 2026-10-01T00:00:00Z
---

# frontend command status

## Purpose

A React-free sibling of [scan-status](./scan-status.md) for the Pi command lifecycle. The device
detail status region and the 5s poll's stop condition both branch here so every `CommandStatus`
value cannot drift from each other or from `ScanStatus`.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `commandStatusLabel(status)` | Maps all eight `CommandStatus` values to a string. `cancelled` → "Scan stopped"; `failed` and `expired` carry **different labels** but the same plain-text presentation. | `frontend/src/lib/commandStatus.ts:17` |
| `isTerminalCommandStatus(status)` | True for `done`, `failed`, `cancelled`, and `expired`; `undefined` is false so a failed poll does not stop asking. Ends `cancelling` in [devices-screen](./devices-screen.md)'s `useScanCommand`. | `frontend/src/lib/commandStatus.ts:21` |
| `isSettledCommand(command)` | Terminal, except `cancelled` without `has_results`: a Pi stopped while offline can still upload its partial scan on reconnect (spec 049, decision 5). Drives `refetchInterval` in `useScanCommand`. | `frontend/src/lib/commandStatus.ts:43` |

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
- **`cancelled` is terminal but not always settled.** Invalidation on `cancelled` matches `done`
  (scans, hosts, findings, agent detail), and runs again when a cancelled command gains results.
  An empty stop keeps polling every 5s while the page is open.

# Citations

[1] [specs/040-agents-scan-trigger/TRUTH.md](../../../specs/040-agents-scan-trigger/TRUTH.md)
[2] [specs/042-design-system/TRUTH.md](../../../specs/042-design-system/TRUTH.md)
[3] [specs/049-remote-scan-cancel/plan.md](../../../specs/049-remote-scan-cancel/plan.md)
