---
type: Module
title: frontend explanations and assistant
description: Structured scan and machine explanations in a right side panel, plus contextual chat launched from the top bar or the explanation footer.
resource: frontend/src/components/ExplainPanel.tsx
tags: [frontend, ai, chat, accessibility]
timestamp: 2026-10-23T00:00:00Z
---

# frontend explanations and assistant

## Purpose

`ExplainPanel` sends `/ai/explain` only when opened. Scan results contain an introduction,
checked-count lead-ins and scan limitations; the task-one pointer comes from analysis data.
Machine results contain identity and problem sentences. These are structured tasks, separate
from chat. `SidePanel` uses Radix Dialog for a 560px right sheet, focus containment, Escape,
outside dismissal and focus return.

## Key classes / functions

| Name | What it does |
|------|--------------|
| `explainAIContext` | Contract-typed POST accepting scope, context ID and language, with AbortSignal. |
| `ExplainPanel` | TanStack Query cache includes language and latest scan; waiting, Cancel, toast and retry states. |
| `GlobalAssistant` | Top-bar trigger on scan and machine routes; derives the context from the current route. |
| `ContextChat` | Contextual questions, safe answer rendering, history and client cancellation; compact mode puts the input below the conversation. |
| `ChatAnswer` | Renders paragraphs, lists, bold text and backend-checked citation links (`assistant-source-link`). |

## How it connects

- The panel footer closes the sheet and emits `dmitri:assistant-open`; the top-bar
  assistant opens for the same route context.
- [backend AI](/backend/ai.md) authorizes every scope and records usage.
- [scan to-do list](./scan-ai.md) supplies the code-owned pointer.

## Notes / gotchas

- Cancel aborts the browser request. A provider call already running on the server can
  still finish, be cached and count against the daily limit.
- Explanation failures appear in toasts, with a retry control in the panel.
- Inline finding chats were removed. Both problem tables use `VulnerabilityView`.
