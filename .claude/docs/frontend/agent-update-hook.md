---
type: Module
title: frontend remote-agent-update hook
description: Queries update availability/history/operation, polls only active phases, posts manual requests with an idempotency key, reconciles caches, and deduplicates read-error notices.
resource: frontend/src/hooks/useAgentUpdate.ts
tags: [frontend, agents, updates, tanstack-query]
timestamp: 2026-10-20T00:00:00Z
---

# frontend remote-agent-update hook

## Purpose

`useAgentUpdate(agentId)` coordinates the device-update reads and manual request used by
[`AgentUpdateSection`](./agent-update-section.md). It keeps availability, history and operation in
separate query keys, polls operation state only while its phase is active, and immediately caches
an accepted POST response so the UI does not lose it if the follow-up history read fails.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `ACTIVE_PHASES` / `TERMINAL_PHASES` | Define the exact operation phases that continue polling and the phases that refresh device/availability state. | `frontend/src/hooks/useAgentUpdate.ts:13` |
| `useAgentUpdate(agentId)` | Queries availability, history and latest operation; active operations poll every five seconds. | `frontend/src/hooks/useAgentUpdate.ts:30` |
| `refresh()` | Re-reads availability, history, current operation and device detail using settled promises so one failure does not block other reads. | `:91` |
| `request(releaseId, expectedObservedVersion)` | Prevents duplicate in-flight submits, retains an idempotency UUID across retries, caches the accepted operation/history, then invalidates related reads. | `:102` |

## How it connects

- Used by [`AgentUpdateSection`](./agent-update-section.md) inside the device detail page.
- Calls the contract-derived `agentUpdates.ts` functions documented in [api](./api.md).
- Uses `queryKeys.agentUpdates` and `queryKeys.agents.detail` to keep update and device state
  independently invalidatable.

## Notes / gotchas

- The mutation is manual; the hook never starts or cancels a scan.
- Availability/history/operation reads report failure episodes to the section, which displays
  localized, deduplicated notifications and retains previously loaded data.
- A response can indicate local completion awaiting remote confirmation; the UI must not imply that
  the backend has observed the new package version until a later confirmation arrives.
