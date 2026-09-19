---
type: Module
title: frontend contextual AI assistant
description: Floating Assistente IA on scan and host detail routes; ContextChat uses /ai/chat with multi-turn history. Finding and host one-shot explains use separate /explain endpoints in FindingPanel and HostDetail.
resource: frontend/src/components/ContextChat.tsx
tags: [frontend, ai, chat, dialog]
timestamp: 2026-09-19T18:30:00Z
---

# frontend contextual AI assistant

## Purpose

The product has **two SPA patterns** for interactive AI:

1. **Multi-turn contextual chat** — `GlobalAssistant` (fixed bottom-right in [`AppShell`](./app.md))
   opens a dialog with `ContextChat` on **scan detail** (`/scans/:id`) and **host detail**
   (`/network/:hostId`). It calls `askContextAI` / `getContextAIHistory` → `/api/v1/ai/chat` with
   `scope` `scan` or `host`. The backend also accepts `scope` `finding`, but the SPA never passes
   that to `ContextChat`.

2. **One-shot “Explicar com IA”** — inline cards that POST a default question to the per-resource
   explain routes (same chat stack on the server, different HTTP paths):
   - **Finding** — [`FindingPanel`](./screens.md) → `explainFinding` →
     `POST /findings/{id}/explain` (expand row on scan or host findings tables).
   - **Host** — `HostAIExplanation` on [`HostDetail`](./screens.md) → `explainHost` →
     `POST /hosts/{id}/explain`. This is separate from the floating assistant on the same page.

`ScanChat` in `pages/scans/ScanChat.tsx` calls legacy `/scans/{id}/chat` via `api/scans.ts`; it is
**not** mounted in `ScanDetail`. Production multi-turn scan chat is `ContextChat` with `scope: scan`.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `askContextAI` / `getContextAIHistory` | POST `/ai/chat` and GET `/ai/chat/history` with `scope` + `context_id`. | `frontend/src/api/ai.ts:18`, `:31` |
| `explainFinding` / `getFindingAIHistory` | Finding one-shot + history on `/findings/{id}/explain`. | `frontend/src/api/findings.ts:38`, `:49` |
| `explainHost` / `getHostAIHistory` | Host one-shot + history on `/hosts/{id}/explain`. | `frontend/src/api/hosts.ts:48`, `:59` |
| `ContextChat` | Multi-turn UI; server history loads only when the user expands history. Optimistic rows use `message_id` prefix `local-`. | `frontend/src/components/ContextChat.tsx:19` |
| `GlobalAssistant` | Path regex for scan and host only; other routes prompt to pick a scan. | `frontend/src/components/GlobalAssistant.tsx:20` |
| `FindingPanel` | `Explicar com IA` button; shows answer inline, no `ContextChat`. | `frontend/src/pages/scans/FindingPanel.tsx:33` |
| `HostAIExplanation` | Host-level explain card on network machine detail. | `frontend/src/pages/HostDetail.tsx:82` |

## How it connects

- Backend: [ai](/backend/ai.md) (unified chat, explain routes, scoped history).
- Scan overview (separate feature): [scan-ai](./scan-ai.md).

## Notes / gotchas

- All paths require AI enabled on the API (`AI_ENABLED` + `AI_API_KEY`); failures are inline copy, not
  route guards.
- `ContextChat` history fetch failures are non-fatal; the user can still send a new question.
- Finding/host explain UIs do not surface `getFindingAIHistory` / `getHostAIHistory` today — only the
  POST path is wired in the panel components.
