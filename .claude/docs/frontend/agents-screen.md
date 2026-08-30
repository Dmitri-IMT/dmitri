---
type: Module
title: Agents screen and scan command hook
description: usePrimaryAgent reads list+detail and useAgentScreen folds them into AgentScreen; useScanCommand latches the followed command, polls GET /commands/{id}, and invalidates read caches on done.
resource: frontend/src/pages/Agents.tsx
tags: [frontend, agents, commands, tanstack-query]
timestamp: 2026-08-30T12:00:00Z
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
| `usePrimaryAgent()` | The shared read pair behind both Agents and Home: `GET /agents` then `GET /agents/{id}` with `skipToken` when there is no id. Its `refetch()` retries the list always and the detail **only when `agentId` is present**. | `frontend/src/hooks/usePrimaryAgent.ts:5` |
| `useAgentScreen()` | Folds that pair into one page union. Resolution: **data outranks error** (background refetch failure must not drop a run in progress), then error, loading, blank (`data.length === 0`), loading. | `frontend/src/hooks/useAgentScreen.ts:12` |
| `AgentScreen` | `'loading' \| 'error' \| 'blank' \| 'ready'` — the page switches on this, not raw query flags. | `frontend/src/hooks/useAgentScreen.ts:6` |
| `useScanCommand(agent)` | Latches `followedCommandId` (never cleared on terminal — only replaced by a newer id). Polls `GET /commands/{id}` every 5s until [command-status](./command-status.md)'s `isTerminalCommandStatus`. On `done`, invalidates `scans`, `hosts`, `findings`, and `agents.detail` once per command id. `trigger()` posts `{ scan_mode: 'quick', subnet }` via [api](./api.md) and resolves to **one** `TriggerOutcome`. | `frontend/src/hooks/useScanCommand.ts:23` |
| `TriggerOutcome` | `'followed' \| 'subnet-stale' \| 'refused'` — the hook's whole answer to one press. The caller dispatches: focus the status region, reopen the chooser, or do nothing. The hook owns no UI callback. | `frontend/src/hooks/useScanCommand.ts:15` |
| `subnetLabel()` / `subnetOptionSuffix()` / `findAvailableSubnet()` | Pure interface→label mapping (`eth*`/`en*` → Ethernet, `wl*` → Wi-Fi, else raw name) plus the internet-route suffix. No React. | `frontend/src/lib/subnetLabel.ts:15` |
| `Agents` | Composes `PageHeader`, the `useAgentScreen` branch, and the permanent Pi note + Scans/Hosts links. | `frontend/src/pages/Agents.tsx:10` |
| `AgentCard` | Owns chooser vs scan-control exclusivity; wires `useScanCommand` and `TargetSubnetSection`. Reopens the chooser on `'subnet-stale'`, and passes `autoFocus` to `ScanControl` after a subnet save. | `frontend/src/pages/agents/AgentCard.tsx:11` |
| `TargetSubnetSection` | "Scanning: …" read line + `[Change]`; `AdminOnly` chooser with `[Set this Network]` confirm, PATCH + `setQueryData` (no refetch). Refusals are toasts; chooser stays open. | `frontend/src/pages/agents/TargetSubnetSection.tsx:16` |
| `ScanControl` | One slot: `[Scan now]` or `CommandStatus`. Trigger stays visible when offline; disabled only while POST in flight. Dispatches the `TriggerOutcome`: `'followed'` bumps `focusEpoch` (a `useLayoutEffect` then focuses `statusRef`), `'subnet-stale'` calls `onSubnetStale`. | `frontend/src/pages/agents/ScanControl.tsx:7` |
| `CommandStatus` | **One** `role="status"` root that stays mounted from `Starting…` through every fetched state — `className` is the only branch, and the a11y attributes are written once. Inside: pill + terminal next steps (`[View scan]` when `done` and `scan_id` present; `scanFailureReason` sentence on `failed`; expired copy + `[Retry]` for admin). Takes a React 19 `ref` prop on that root so the caller can focus a stable node. | `frontend/src/pages/agents/CommandStatus.tsx:13` |
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
- **Focus follows the accepted action, through refs — never through test ids.** `ScanControl` holds
  a plain `statusRef` on `CommandStatus`'s single status root and increments `focusEpoch` when
  `trigger()` returns `'followed'`; a `useLayoutEffect` keyed on that epoch does the focusing. The
  Scan now button uses `autoFocus` gated on a subnet save — that path genuinely remounts. Passive
  mount, reload, and background adoption never move focus. Two shapes are forbidden here: a
  `querySelector('[data-testid=…]')` (production a11y must not depend on test ids), and the
  mount-latch-plus-inline-callback-ref this replaced — that one set its flag *after* `trigger()` had
  already committed `followedCommandId`, so it worked only because an inline ref gets a fresh
  identity every render, and retry focus died the moment anyone wrapped it in `useCallback`. The
  epoch is keyed to the user action, so it survives both the first mount and every retry.
- **Never refetch the `skipToken` detail query.** With no Pi, `agentId` is undefined and
  `agents.detail('')` is a sentinel key whose `queryFn` is `skipToken`; TanStack v5 rejects a
  `refetch()` on it with `Missing queryFn`, which marks the key errored. Since `useAgentScreen`
  reads `detailQuery.isError` as a page failure, an unguarded retry after a transient list error
  would strand a no-device install on the error screen instead of the blank one — and `useHomeReview`
  shares the hook, so the leak was shared too. The guard lives in `usePrimaryAgent.refetch`; do not
  teach `useAgentScreen` to special-case `detail('')` errors instead.
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
