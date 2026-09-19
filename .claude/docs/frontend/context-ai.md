---
type: Module
title: frontend contextual AI assistant
description: Floating Assistente IA on scan and host detail routes; ContextChat calls the unified /ai/chat API with optional persisted history per scope.
resource: frontend/src/components/ContextChat.tsx
tags: [frontend, ai, chat, dialog]
timestamp: 2026-09-19T18:20:00Z
---

# frontend contextual AI assistant

## Purpose

Signed-in operators can ask grounded security questions on **completed scan detail** and **host detail**.
`GlobalAssistant` is a fixed bottom-right trigger in [`AppShell`](./app.md). It opens a dialog with
`ContextChat`, passing `scope` `scan` or `host` and the route id. Finding-level chat is wired on the
backend (`/findings/{id}/explain`) but the SPA does not mount a finding chat surface yet.

`ScanChat` in `pages/scans/ScanChat.tsx` is a parallel UI that calls the legacy
`/scans/{id}/chat` wrappers in `api/scans.ts`; it is **not** mounted in `ScanDetail` — production
chat goes through `ContextChat` + `api/ai.ts`.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `askContextAI` / `getContextAIHistory` | POST `/ai/chat` and GET `/ai/chat/history` with `scope` + `context_id`. | `frontend/src/api/ai.ts:18`, `:31` |
| `ContextChat` | Local message list; server history loads only when the user expands history. Optimistic rows use `message_id` prefix `local-`. Maps API errors to Portuguese operator copy. | `frontend/src/components/ContextChat.tsx:19` |
| `GlobalAssistant` | Regex on `location.pathname` for `/scans/:id` and `/network/:hostId`; otherwise the dialog explains that chat needs a scan or host context. | `frontend/src/components/GlobalAssistant.tsx:20` |
| `AppShell` | Mounts `GlobalAssistant` beside `<Outlet />`. | `frontend/src/components/AppShell.tsx:14` |

## How it connects

- Backend: [ai](/backend/ai.md) (`ask_context_chat`, scoped history).
- Scan overview (separate feature): [scan-ai](./scan-ai.md).

## Notes / gotchas

- Chat requires AI enabled on the API (`AI_ENABLED` + `AI_API_KEY`); failures surface as inline error
  text, not a route guard.
- History fetch failures are non-fatal; the user can still send a new question.
