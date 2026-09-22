---
type: Module
title: frontend contextual AI assistant
description: One-shot "Explain with AI" on a finding and a machine, both through ContextChat's presetQuestion mode against /ai/chat. The floating multi-turn GlobalAssistant was deleted (DMI-179); ContextChat's own multi-turn/history UI is now dead code with no caller.
resource: frontend/src/components/ContextChat.tsx
tags: [frontend, ai, chat, dialog]
timestamp: 2026-09-22T00:00:00Z
---

# frontend contextual AI assistant

## Purpose

**One SPA pattern remains** for interactive AI: **one-shot "Explain with AI"** — an inline card that
POSTs a translated default question to `/ai/chat`, scoped to the resource:

- **Finding** — [`FindingPanel`](./screens.md) → `askContextAI('finding', id, …)` (expand row on
  scan or host findings tables).
- **Host** — `HostAIExplanation` on [`HostDetail`](./screens.md) → `askContextAI('host', id, …)`.

Both render `ContextChat` with `presetQuestion` set (its "one-shot" mode). Since DMI-179, a one-shot
`ContextChat` can only be asked **once per mount**: the ask button disappears as soon as an answer
exists, so it cannot be re-triggered to produce a second, different, unsaved answer for the same
mount. The answer itself is still not persisted anywhere — closing and reopening the panel (which
remounts it) allows asking again.

**`GlobalAssistant`** — the floating bottom-right "Ask Dmitri" button that opened a multi-turn
`ContextChat` (no `presetQuestion`, with a history toggle) on scan and host detail — was **deleted**
(DMI-179), file and all. `ContextChat`'s multi-turn/history branch (the free-text form, `Show
history`/`Hide history`, `getContextAIHistory`) is therefore **dead code**: no current caller renders
`ContextChat` without `presetQuestion`. The backend route still accepts `scope: 'scan'` /
`scope: 'host'` for it; nothing in the SPA sends those scopes any more.

Every AI question in the app goes through `POST /ai/chat`; history through `GET /ai/chat/history`
(unreachable from the UI now — see above). The per-resource `/scans/{id}/chat`, `/hosts/{id}/explain`
and `/findings/{id}/explain` routes were deleted in PR #151, together with the unmounted `ScanChat`
screen.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `askContextAI` / `getContextAIHistory` | POST `/ai/chat` (body adds `language`, default `en`) and GET `/ai/chat/history` with `scope` + `context_id`. | `frontend/src/api/ai.ts:19`, `:34` |
| `ContextChat` | `presetQuestion` set → one-shot: a single ask button that self-removes once `visibleMessages` is non-empty (DMI-179). `presetQuestion` unset → multi-turn UI with a free-text form and a history toggle, but nothing mounts it this way today. Sends the [`useI18n`](./i18n.md) language with each question. Optimistic rows use `message_id` prefix `local-`. | `frontend/src/components/ContextChat.tsx:26` |
| `FindingPanel` | `ai.explainFinding` button via one-shot `ContextChat`. Sends the [`useI18n`](./i18n.md) language. | `frontend/src/pages/scans/FindingPanel.tsx:34` |
| `HostAIExplanation` | Host-level explain card on network machine detail, same one-shot pattern. Sends the [`useI18n`](./i18n.md) language. | `frontend/src/pages/HostDetail.tsx:84` |

## How it connects

- Backend: [ai](/backend/ai.md) (one chat route, scoped history).
- Scan overview (separate feature): [scan-ai](./scan-ai.md).
- Mounted from [`AppShell`](./app.md) only indirectly, via whichever page renders `FindingPanel` or
  `HostAIExplanation` — `AppShell` itself no longer mounts any AI-ask surface directly.

## Notes / gotchas

- All paths require AI enabled on the API (`AI_ENABLED` + `AI_API_KEY`); failures now raise a
  `Toast` (DMI-179) rather than writing error text inside the card.
- Every caller sends `language` from `useI18n`, including the finding and host one-shots. Their
  default questions are translation keys (`ai.defaultFindingQuestion`, `ai.defaultMachineQuestion`),
  not hardcoded strings.
- The finding and host cards do not surface `getContextAIHistory` today — only the POST path is
  wired in the panel components.
- If a future change needs multi-turn chat back, `ContextChat`'s non-`presetQuestion` branch already
  does it — it just needs a caller (`GlobalAssistant`'s old shape) again.
