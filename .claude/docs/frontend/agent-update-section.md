---
type: Module
title: frontend device update section
description: DeviceDetail's localized update availability, readiness, versions, operation history and confirmed admin request interface.
resource: frontend/src/pages/agents/AgentUpdateSection.tsx
tags: [frontend, agents, updates, accessibility, i18n]
timestamp: 2026-10-20T00:00:00Z
---

# frontend device update section

## Purpose

`AgentUpdateSection` renders the remote-update status for a device detail page. The card shows
three facts on top: installed version, available version and one status line (the active phase,
else readiness, else catalog availability). Release notes sit under a "What's new" disclosure;
package versions, timestamps and the latest operation's details sit under "Technical details".
History is one line per operation. An administrator can request an eligible release after an
accessible confirmation dialog. The section is localized in English, Brazilian Portuguese and
Russian and stays separate from scan controls.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `phaseKeys` / `availabilityKeys` / `readinessKeys` / `errorKeys` | Exhaustive mappings from API literals to typed localized messages. | `frontend/src/pages/agents/AgentUpdateSection.tsx:19` |
| `OperationDetails` | Inside Technical details: version transition, local outcome, actor snapshot and timestamps of the latest operation. | `:107` |
| `HistoryItem` | One history line: date, version transition, actor and phase. | `:178` |
| `AgentUpdateSection({ agent })` | Applies role/revocation/readiness/catalog gates, shows current/history state and drives confirmation/request/refresh. Intervention, error, offline and revoked guidance stay visible above the buttons. | `:202` |
| `formatDate()` / `VersionRow` | Locale-aware timestamp and consistent definition-list rows. | `:78`, `:88` |

## How it connects

- Mounted by `DeviceDetail` via [`devices-screen`](./devices-screen.md).
- Uses [`useAgentUpdate`](./agent-update-hook.md), `useSession`, the toast layer and generated
  OpenAPI types through [api](./api.md).
- Its assertions live in `frontend/src/pages/DeviceDetail.updates.test.tsx`.

## Notes / gotchas

- Request action appears only for an admin, non-revoked device, available release, `ready` device
  and known observed version. Offline, revoked, busy, legacy or bootstrap-required states remain
  explanatory/read-only.
- Confirmation and POST pending state prevent duplicate actions; completion labels distinguish
  local install success from later backend confirmation. No percentage is invented.
- No badge or coloured tag: an available update is a plain muted note beside the title.
- Read errors are localized and deduplicated per failing query episode; a successful refetch clears
  that episode so a later failure can notify again.
