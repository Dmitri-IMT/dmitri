---
type: Module
title: Agents screen and scan command hook
description: useAgentScreen folds list+detail reads into AgentScreen; useScanCommand latches the followed command, polls GET /commands/{id}, and invalidates read caches on done.
resource: frontend/src/pages/Agents.tsx
tags: [frontend, agents, commands, tanstack-query]
timestamp: 2026-08-30T00:00:00Z
---

# Agents screen and scan command hook

## Purpose

The only place a human causes a scan. `useAgentScreen()` discovers the single MVP agent and folds
list + detail into one page union; `useScanCommand()` owns the followed command id, the 5s poll, the
done-sweep invalidation, and `trigger()` (including `409 device_busy` adoption). Screen-specific
pieces live under `pages/agents/`; pure subnet labelling lives in `subnetLabel.ts`.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `useAgentScreen()` | `GET /agents` then `GET /agents/{id}` with `skipToken` when no id. Resolution: **data outranks error** (background refetch failure must not drop a run in progress), then error, loading, blank (`data.length === 0`), loading. | `frontend/src/hooks/useAgentScreen.ts:14` |
| `AgentScreen` | `'loading' \| 'error' \| 'blank' \| 'ready'` — the page switches on this, not raw query flags. | `frontend/src/hooks/useAgentScreen.ts:8` |
| `useScanCommand(agent)` | Latches `followedCommandId` (never cleared on terminal — only replaced by a newer id). Polls `GET /commands/{id}` every 5s until [command-status](./command-status.md)'s `isTerminalCommandStatus`. On `done`, invalidates `scans`, `hosts`, `findings`, and `agents.detail` once per command id. `trigger()` posts `{ scan_mode: 'quick', subnet }` via [api](./api.md) and resolves to **one** `TriggerOutcome`. | `frontend/src/hooks/useScanCommand.ts:23` |
| `TriggerOutcome` | `'followed' \| 'subnet-stale' \| 'refused'` — the hook's whole answer to one press. The caller dispatches: focus the status region, reopen the chooser, or do nothing. The hook owns no UI callback. | `frontend/src/hooks/useScanCommand.ts:15` |
| `subnetLabel()` / `subnetOptionSuffix()` / `findAvailableSubnet()` | Pure interface→label mapping (`eth*`/`en*` → Ethernet, `wl*` → Wi-Fi, else raw name) plus the internet-route suffix. No React. | `frontend/src/lib/subnetLabel.ts:15` |
| `Agents` | Composes `PageHeader`, the `useAgentScreen` branch, and the permanent Pi note + Scans/Hosts links. | `frontend/src/pages/Agents.tsx:10` |
| `AgentCard` | Owns chooser vs scan-control exclusivity; wires `useScanCommand` and `TargetSubnetSection`. Reopens the chooser on `'subnet-stale'`, and passes `autoFocus` to `ScanControl` after a subnet save. | `frontend/src/pages/agents/AgentCard.tsx:11` |
| `TargetSubnetSection` | "Scanning: …" read line + `[Change]`; `AdminOnly` chooser with `[Set this Network]` confirm, PATCH + `setQueryData` (no refetch). Refusals are toasts; chooser stays open. | `frontend/src/pages/agents/TargetSubnetSection.tsx:16` |
| `ScanControl` | One slot: `[Scan now]` or `CommandStatus`. Trigger stays visible when offline; disabled only while POST in flight. Dispatches the `TriggerOutcome`: `'followed'` arms a focus-on-mount ref for the status region, `'subnet-stale'` calls `onSubnetStale`. | `frontend/src/pages/agents/ScanControl.tsx:7` |
| `CommandStatus` | Pill + terminal next steps: `[View scan]` when `done` and `scan_id` present; `scanFailureReason` sentence on `failed`; expired copy + `[Retry]` for admin. Takes a React 19 `ref` prop on its `role="status"` root so the caller can focus it. | `frontend/src/pages/agents/CommandStatus.tsx:13` |
| `AgentsBlank` | No-device blank: `EmptyState` with `note` only — **no `action`** (TRUTH rule 25). | `frontend/src/pages/agents/AgentsBlank.tsx:3` |
| `FirstScanCta` / `FirstScanNote` | Admin link to `/agents` and viewer line for Home/Scans/Hosts blank states. | `frontend/src/components/FirstScanCta.tsx:6` |

## How it connects

- Five API calls through [api](./api.md)'s `agents.ts` and `commands.ts`; keys from `queryKeys.agents`
  and `queryKeys.commands`.
- Pill tone/labels from [command-status](./command-status.md); chrome from [tables](./tables.md)'s
  `StatusPill`.
- Route and nav unchanged from [app](./app.md) — both roles reach `/agents`; admin-only controls
  use `AdminOnly` inside the page ([screens](./screens.md)).
- MSW defaults and per-test overrides: `mswHandlers.ts` fixtures + `test/agentsHarness.ts`. Tests
  split three ways: `Agents.test.tsx` (screen states and roles), `Agents.command.test.tsx`
  (trigger, poll, adopt, refuse, retry, focus — it owns fake timers), and
  `Agents.invalidation.test.tsx` (the done-sweep, the only case mounting `Scans`, `Hosts` and
  `HostFindings` beside the card).
- Completion invalidates the read surfaces documented in [screens](./screens.md) (Scans, Hosts, Home
  findings) without those screens polling.

## Notes / gotchas

- **This is the app's only `refetchInterval`.** Scan list, scan detail, and host detail keep static
  reads; invalidation on command `done` is the refresh path.
- **`followedCommandId` is latched state, not derived from `active_command_id`.** When the server
  clears `active_command_id` at terminal, the pill must stay visible — see
  `docs/research/tanstack-query-followed-resource-lifetime.md`.
- **Focus follows the accepted action, through refs — never through test ids.** `ScanControl` arms a
  flag when `trigger()` returns `'followed'` and focuses the status node from its callback ref as it
  mounts; the Scan now button uses `autoFocus` gated on a subnet save. Passive mount, reload, and
  background adoption never move focus. Do not reintroduce a generation counter or a
  `querySelector('[data-testid=…]')` — production a11y must not depend on test ids.
- **`409 device_busy` with no `active_command_id` is a plain start failure.** Nothing is adopted and
  `[Scan now]` stays on screen, so the toast is "Couldn't start the scan." — the adopt copy would
  describe a state the UI never enters (ARCHITECTURE §5.5).
- **POST uses plain `async`, not `useMutation`.** Matches `Users.tsx` — one write path in the app.
- **Home's Pi-status footer line is still not built.** Agent reads exist; `HomeFooter` does not call
  them yet.

# Citations

[1] [specs/040-agents-scan-trigger/TRUTH.md](../../../specs/040-agents-scan-trigger/TRUTH.md)
[2] [specs/040-agents-scan-trigger/ARCHITECTURE.md](../../../specs/040-agents-scan-trigger/ARCHITECTURE.md)
[3] [docs/adr/ADR-011-pi-command-channel.md](../../../docs/adr/ADR-011-pi-command-channel.md)
