---
type: Module
title: Devices list, device detail and scan command hook
description: Devices lists every box; DeviceDetail owns subnet choice, scan-type tabs and useScanCommand; trigger() posts the selected ScanMode and invalidates read caches on done.
resource: frontend/src/pages/Devices.tsx
tags: [frontend, agents, devices, commands, tanstack-query]
timestamp: 2026-09-04T00:00:00Z
---

# Devices list, device detail and scan command hook

## Purpose

The scan trigger moved off a single `/agents` page onto a two-level devices IA: `Devices` lists every
box in the org; `DeviceDetail` at `/devices/:agentId` owns identity, subnet choice, scan-type
selection and `[Scan now]`. `useScanCommand()` still latches the followed command id, polls every 5s,
and invalidates read caches on `done`. Screen-specific pieces live under `pages/agents/`; pure subnet
labelling lives in `subnetLabel.ts`; scan-mode labels and defaults live in `lib/scanModes.ts`.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `Devices` | `GET /agents` → `DataTable` of every box. Own error / pending / blank / table ladder inline (not `ListSurface`). Offline rows render muted via `rowTone`. Blank is `DevicesBlank` — note only, no action. | `frontend/src/pages/Devices.tsx:13` |
| `deviceListColumns(now)` | Box name, watched network (or "No network chosen yet"), online/offline label, last report with `Timestamp`. | `frontend/src/pages/agents/deviceListColumns.tsx:8` |
| `DevicesBlank` | No-device blank: `EmptyState` with `note` only — **no `action`**. | `frontend/src/pages/agents/DevicesBlank.tsx:3` |
| `DeviceDetail` | One `getAgent` read through `readDetailState` into `ReadDetailGate` with `backTo="/devices"`. Ready view is `DeviceDetailBody`. | `frontend/src/pages/DeviceDetail.tsx:79` |
| `DeviceDetailBody` | Back link, `AgentIdentity`, `TargetSubnetSection`, then scan section gated on chooser state. Admin picks scan type via `ScanTypeTabs`; viewers see `ScanTypeReadOnly`. | `frontend/src/pages/DeviceDetail.tsx:22` |
| `ScanTypeTabs` / `ScanTypeReadOnly` | Radix `Tabs` over `SCAN_MODE_ORDER` with per-mode description; read-only shows the default mode label for viewers. | `frontend/src/pages/agents/ScanTypeTabs.tsx:13` |
| `DEFAULT_SCAN_MODE` / `SCAN_MODE_LABEL` / `SCAN_MODE_DESCRIPTION` | Pure scan-mode vocabulary; default is `standard`, not `quick`. | `frontend/src/lib/scanModes.ts:5` |
| `useScanCommand(agent)` | Latches `followedCommandId` (never cleared on terminal — only replaced by a newer id). Polls `GET /commands/{id}` every 5s until [command-status](./command-status.md)'s `isTerminalCommandStatus`. On `done`, invalidates `scans`, `hosts`, `findings`, and `agents.detail` once per command id. `trigger(scanMode)` posts `{ scan_mode, subnet }` and resolves to **one** `TriggerOutcome`. | `frontend/src/hooks/useScanCommand.ts:24` |
| `TriggerOutcome` | `'followed' \| 'subnet-stale' \| 'refused'` — the hook's whole answer to one press. | `frontend/src/hooks/useScanCommand.ts:15` |
| `subnetLabel()` / `subnetOptionSuffix()` / `findAvailableSubnet()` | Pure interface→label mapping plus the internet-route suffix. No React. | `frontend/src/lib/subnetLabel.ts:15` |
| `TargetSubnetSection` | "Scanning: …" read line + `[Change]`; `AdminOnly` chooser with `[Set this Network]` confirm, PATCH + `setQueryData` (no refetch). Refusals are toasts; chooser stays open. | `frontend/src/pages/agents/TargetSubnetSection.tsx:16` |
| `ScanControl` | One slot: `[Scan now]` or `CommandStatus`. Trigger stays visible when offline; disabled only while POST in flight. Dispatches the `TriggerOutcome` and passes `selectedMode` into `trigger()`. | `frontend/src/pages/agents/ScanControl.tsx:11` |
| `CommandStatus` | **One** `role="status"` root that stays mounted from `Starting…` through every fetched state. Renders `commandStatusLabel` text — no pill chrome. Terminal next steps unchanged (`[View scan]`, failure sentence, expired copy + `[Retry]` for admin). | `frontend/src/pages/agents/CommandStatus.tsx:12` |
| `FirstScanCta` / `FirstScanNote` | Admin link to `/devices` and viewer line for Home/Scans/Network blank states. | `frontend/src/components/FirstScanCta.tsx:6` |

## How it connects

- Five API calls through [api](./api.md)'s `agents.ts` and `commands.ts`; keys from `queryKeys.agents`
  and `queryKeys.commands`.
- Status copy from [command-status](./command-status.md); chrome from [screens](./screens.md) and
  [tables](./tables.md).
- Routes in [app](./app.md): `/devices` → `Devices`, `/devices/:agentId`
  → `DeviceDetail`. Both roles reach the list; admin-only controls use `AdminOnly` inside the detail
  page.
- MSW defaults and per-test overrides: `mswHandlers.ts` fixtures + `test/agentsHarness.ts`. Tests
  split across `Devices.test.tsx`, `DeviceDetail.test.tsx`,
  `DeviceDetail.command.test.tsx`, and `DeviceDetail.invalidation.test.tsx`.
- Completion invalidates the read surfaces documented in [screens](./screens.md) without those
  screens polling.

## Notes / gotchas

- **`usePrimaryAgent` and `useAgentScreen` are gone.** The list page reads `listAgents` directly; the
  detail page reads `getAgent` by route param. Do not reintroduce the list+detail fold for the table.
- **This is the app's only `refetchInterval`.** Scan list, scan detail, and host detail keep static
  reads; invalidation on command `done` is the refresh path.
- **`followedCommandId` is latched state, not derived from `active_command_id`.** When the server
  clears `active_command_id` at terminal, the status region must stay visible.
- **Focus follows the accepted action, through refs — never through test ids.** `ScanControl` holds a
  plain `statusRef` on `CommandStatus`'s single status root and increments `focusEpoch` when
  `trigger()` returns `'followed'`.
- **`409 device_busy` with no `active_command_id` is a plain start failure.** Nothing is adopted and
  `[Scan now]` stays on screen.
- **POST uses plain `async`, not `useMutation`.** Matches `Users.tsx` — one write path in the app.

# Citations

[1] [specs/040-agents-scan-trigger/TRUTH.md](../../../specs/040-agents-scan-trigger/TRUTH.md)
[2] [specs/042-design-system/TRUTH.md](../../../specs/042-design-system/TRUTH.md)
[3] [docs/adr/ADR-011-pi-command-channel.md](../../../docs/adr/ADR-011-pi-command-channel.md)
