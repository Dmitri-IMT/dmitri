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

`AgentUpdateSection` renders the remote-update status for a device detail page. It shows catalog
availability/readiness, observed and package versions, active/history outcomes and the latest
contact. An administrator can request an eligible release after an accessible confirmation
dialog. The section is localized in English, Brazilian Portuguese and Russian and stays separate
from scan controls.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `phaseKeys` / `availabilityKeys` / `readinessKeys` / `errorKeys` | Exhaustive mappings from API literals to typed localized messages. | `frontend/src/pages/agents/AgentUpdateSection.tsx:19` |
| `OperationDetails` | Displays version transition, local/remote outcome, actor snapshot, timestamps and intervention/error guidance. | `:105` |
| `AgentUpdateSection({ agent })` | Applies role/revocation/readiness/catalog gates, shows current/history state and drives confirmation/request/refresh. | `:205` |
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
- Read errors are localized and deduplicated per failing query episode; a successful refetch clears
  that episode so a later failure can notify again.
