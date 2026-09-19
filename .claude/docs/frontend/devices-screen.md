---
type: Module
title: Devices list, detail, scan and revocation
description: Devices shows Online, Offline or Revoked; DeviceDetail owns scanning plus admin revoke/restore and hides controls while revoked.
resource: frontend/src/pages/Devices.tsx
tags: [frontend, agents, devices, commands, tanstack-query]
timestamp: 2026-09-17T00:00:00Z
---

# Devices list, detail, scan and revocation

## Purpose

The scan trigger moved off a single `/agents` page onto a two-level devices IA: `Devices` lists every
box in the org; `DeviceDetail` at `/devices/:agentId` owns identity, subnet choice, scan-type
selection and `[Scan now]`. `useScanCommand()` still latches the followed command id, polls every 5s,
and invalidates read caches on `done`. Revoked devices replace presence with the revocation time,
hide scan/network-change controls, and expose admin revoke/restore actions. `readAgentPresence()` is
the single revoked/online/offline mode decision; the detail parent derives interactivity from it and
children never inspect lifecycle fields. Screen-specific pieces live under `pages/agents/`; pure
subnet labelling lives in `subnetLabel.ts`; scan-mode labels and defaults live in `lib/scanModes.ts`.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `Devices` | `GET /agents` through `ListSurface`. `readAgentPresence()` makes offline and revoked rows muted. | `frontend/src/pages/Devices.tsx:9` |
| `readAgentPresence(agent)` | Canonical discriminated mode: `revoked` wins over the briefly stale `online`; otherwise Online or Offline. | `frontend/src/lib/agentPresence.ts:11` |
| `AgentPresence` | The one presence renderer for list and detail, including revoked timestamp and full hover title. | `frontend/src/pages/agents/AgentPresence.tsx:7` |
| `deviceListColumns(now)` | Box, network, shared presence mode + timestamp, and last report. | `frontend/src/pages/agents/deviceListColumns.tsx:9` |
| `DeviceDetail` | One `getAgent` read through `ReadDetailGate`; ready view is `DeviceDetailBody`. | `frontend/src/pages/DeviceDetail.tsx:108` |
| `DeviceDetailBody` | Keeps back link and `AgentIdentity` mounted (so focus survives revoke/restore), then picks one tree from `readAgentPresence`: `RevokedDeviceSections` (read-only network, restore, history) or `LiveDeviceSections` (network + chooser, scan, history, revoke). | `frontend/src/pages/DeviceDetail.tsx:94`, `:31`, `:46` |
| `DeviceRevoke` | Admin-only revoke section. POSTs revoke inside the shared `ConfirmDialog` (which owns pending), invalidates `queryKeys.agents.all`, and raises the success toast. | `frontend/src/pages/agents/DeviceRevoke.tsx:13` |
| `DeviceRestore` | Revoked banner; viewers get explanation only. Admins get an inline restore button that owns its pending and error state, invalidates `queryKeys.agents.all`, and raises the success toast. | `frontend/src/pages/agents/DeviceRestore.tsx:13` |
| `ScanTypeTabs` / `ScanTypeReadOnly` | Radix `Tabs` over `SCAN_MODE_ORDER` with per-mode description; read-only shows the default mode label for viewers. | `frontend/src/pages/agents/ScanTypeTabs.tsx:13` |
| `DEFAULT_SCAN_MODE` / `SCAN_MODE_LABEL` / `SCAN_MODE_DESCRIPTION` | Pure scan-mode vocabulary; default is `standard`, not `quick`. | `frontend/src/lib/scanModes.ts:5` |
| `useScanCommand(agent)` | Latches `followedCommandId` (never cleared on terminal — only replaced by a newer id). Polls `GET /commands/{id}` every 5s until [command-status](./command-status.md)'s `isTerminalCommandStatus`. On `done`, invalidates `scans`, `hosts`, `findings`, and `agents.detail` once per command id. `trigger(scanMode)` posts `{ scan_mode, subnet }` and resolves to **one** `TriggerOutcome`. | `frontend/src/hooks/useScanCommand.ts:24` |
| `TriggerOutcome` | `'followed' \| 'subnet-stale' \| 'refused'` — the hook's whole answer to one press. | `frontend/src/hooks/useScanCommand.ts:15` |
| `subnetLabel()` / `subnetOptionSuffix()` / `findAvailableSubnet()` | Pure interface→label mapping plus the internet-route suffix. No React. | `frontend/src/lib/subnetLabel.ts:15` |
| `TargetSubnetSection` | Watched-network read line plus `[Change]`; it reads `readAgentPresence(agent)` itself and renders neither `[Change]` nor the chooser for a revoked device. Its `AdminOnly` chooser PATCHes and updates query data. | `frontend/src/pages/agents/TargetSubnetSection.tsx:49` |
| `ScanControl` | One slot: `[Scan now]` or `CommandStatus`. Trigger stays visible when offline; disabled only while POST in flight. Dispatches the `TriggerOutcome` and passes `selectedMode` into `trigger()`. | `frontend/src/pages/agents/ScanControl.tsx:11` |
| `CommandStatus` | **One** `role="status"` root that stays mounted from `Starting…` through every fetched state. Renders `commandStatusLabel` text — no pill chrome. Terminal next steps unchanged (`[View scan]`, failure sentence, expired copy + `[Retry]` for admin). | `frontend/src/pages/agents/CommandStatus.tsx:12` |
| `FirstScanCta` / `FirstScanNote` | Admin link to `/devices` and viewer line for Home/Scans/Network blank states. | `frontend/src/components/FirstScanCta.tsx:6` |

## How it connects

- Seven API calls through [api](./api.md)'s `agents.ts` and `commands.ts`; keys from `queryKeys.agents`
  and `queryKeys.commands`.
- Status copy from [command-status](./command-status.md); chrome from [screens](./screens.md) and
  [tables](./tables.md).
- Routes in [app](./app.md): `/devices` → `Devices`, `/devices/:agentId`
  → `DeviceDetail`. Both roles reach the list; admin-only controls use `AdminOnly` inside the detail
  page.
- MSW defaults and per-test overrides: `mswHandlers.ts` fixtures + `test/agentsHarness.ts`. Tests
  split across `Devices.test.tsx`, `DeviceDetail.test.tsx`,
  `DeviceDetail.command.test.tsx`, `DeviceDetail.invalidation.test.tsx`, and
  `DeviceDetail.revocation.test.tsx`.
- Completion invalidates the read surfaces documented in [screens](./screens.md) without those
  screens polling.

## Notes / gotchas

- **`usePrimaryAgent` and `useAgentScreen` are gone.** The list page reads `listAgents` directly; the
  detail page reads `getAgent` by route param. Do not reintroduce the list+detail fold for the table.
- **This is the app's only `refetchInterval`.** Scan list, scan detail, and host detail keep static
  reads; invalidation on command `done` is the refresh path.
- **`followedCommandId` is latched state, not derived from `active_command_id`.** When the server
  clears `active_command_id` at terminal, the status region must stay visible.
- **Focus follows accepted actions.** `ScanControl` holds a plain `statusRef` on `CommandStatus` and
  increments `focusEpoch` when `trigger()` returns `'followed'`. Revoke/restore re-read the detail,
  then `DeviceDetailBody` focuses the newly rendered `agents-presence` target.
- **`409 device_busy` with no `active_command_id` is a plain start failure.** Nothing is adopted and
  `[Scan now]` stays on screen.
- **POST uses plain `async`, not `useMutation`.** Matches `Users.tsx` — one write path in the app.
- **`readAgentPresence()` owns lifecycle precedence.** A revoke response may still say
  `online: true` until the socket handler unregisters; callers consume its discriminated mode
  instead of reproducing the `revoked_at` check.

# Citations

[1] [specs/040-agents-scan-trigger/TRUTH.md](../../../specs/040-agents-scan-trigger/TRUTH.md)
[2] [specs/042-design-system/TRUTH.md](../../../specs/042-design-system/TRUTH.md)
[3] [docs/adr/ADR-011-pi-command-channel.md](../../../docs/adr/ADR-011-pi-command-channel.md)
[4] [specs/048-parked-channel-recovery](../../../specs/048-parked-channel-recovery/TRUTH.md)
