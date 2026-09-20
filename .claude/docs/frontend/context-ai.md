---
type: Module
title: frontend contextual AI assistant
description: Floating Assistente IA on scan and host detail routes; ContextChat uses /ai/chat with multi-turn history. Finding and host one-shot explains post to the same /ai/chat route from FindingPanel and HostDetail.
resource: frontend/src/components/ContextChat.tsx
tags: [frontend, ai, chat, dialog]
timestamp: 2026-09-19T21:00:00Z
---

# frontend contextual AI assistant

## Purpose

The product has **two SPA patterns** for interactive AI:

1. **Multi-turn contextual chat** — `GlobalAssistant` (fixed bottom-right in [`AppShell`](./app.md))
   opens a dialog with `ContextChat` on **scan detail** (`/scans/:id`) and **host detail**
   (`/network/:hostId`). It calls `askContextAI` / `getContextAIHistory` → `/api/v1/ai/chat` with
   `scope` `scan` or `host`. The backend also accepts `scope` `finding`, but the SPA never passes
   that to `ContextChat`.

2. **One-shot “Explain with AI”** — inline cards that POST a translated default question to
   the same `/ai/chat` route, with the scope of the resource:
   - **Finding** — [`FindingPanel`](./screens.md) → `askContextAI('finding', id, …)`
     (expand row on scan or host findings tables).
   - **Host** — `HostAIExplanation` on [`HostDetail`](./screens.md) →
     `askContextAI('host', id, …)`. This is separate from the floating assistant on the
     same page.

Every AI question in the app goes through `POST /ai/chat`; history through
`GET /ai/chat/history`. The per-resource `/scans/{id}/chat`, `/hosts/{id}/explain` and
`/findings/{id}/explain` routes were deleted in PR #151, together with the unmounted
`ScanChat` screen.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `askContextAI` / `getContextAIHistory` | POST `/ai/chat` (body adds `language`, default `en`) and GET `/ai/chat/history` with `scope` + `context_id`. | `frontend/src/api/ai.ts:19`, `:34` |
| `ContextChat` | Multi-turn UI; sends the [`useI18n`](./i18n.md) language with each question. Server history loads only when the user expands history. Optimistic rows use `message_id` prefix `local-`. | `frontend/src/components/ContextChat.tsx:20` |
| `GlobalAssistant` | Path regex for scan and host only; other routes prompt to pick a scan. | `frontend/src/components/GlobalAssistant.tsx:21` |
| `FindingPanel` | `ai.explainFinding` button; shows answer inline, no `ContextChat`. Sends the [`useI18n`](./i18n.md) language. | `frontend/src/pages/scans/FindingPanel.tsx:34` |
| `HostAIExplanation` | Host-level explain card on network machine detail. Sends the [`useI18n`](./i18n.md) language. | `frontend/src/pages/HostDetail.tsx:84` |

## How it connects

- Backend: [ai](/backend/ai.md) (one chat route, scoped history).
- Scan overview (separate feature): [scan-ai](./scan-ai.md).

## Notes / gotchas

- All paths require AI enabled on the API (`AI_ENABLED` + `AI_API_KEY`); failures are inline copy, not
  route guards.
- `ContextChat` history fetch failures are non-fatal; the user can still send a new question.
- Every caller sends `language` from `useI18n`, including the finding and host one-shots. Their
  default questions are translation keys (`ai.defaultFindingQuestion`, `ai.defaultMachineQuestion`),
  not hardcoded strings.
- The finding and host cards do not surface `getContextAIHistory` today — only the POST path is
  wired in the panel components.
