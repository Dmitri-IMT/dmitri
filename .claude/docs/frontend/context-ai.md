---
type: Module
title: frontend explanations and assistant
description: Structured explanation side panels and a clean Focused chat modal with saved conversations behind the clock and new chat behind the pencil.
resource: frontend/src/components/ExplainPanel.tsx
tags: [frontend, ai, chat, accessibility]
timestamp: 2026-10-23T14:36:51Z
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
| `ExplainPanel` | Query cache includes caller, language and latest scan; completed entries remain cached for the app session. Closing or changing language keeps generation running; explicit Cancel stops waiting. |
| `GlobalAssistant` | Top-bar trigger on scan and machine routes; retains the selected conversation per route when the centred modal closes. |
| `ContextChat` | Clock opens dated saved conversations; pencil starts a separate chat. Paginated TanStack queries retain history, and mutations keep saving after the modal closes. The scrollable conversation and anchored multiline composer use design-system tokens without context/evidence tags. |
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
- Chat questions appear immediately while waiting. Successful responses use server message IDs;
  no temporary local transcript replaces the saved one. History failures use toasts and retry.
- Chat caches include the caller ID. Conversation contents are fetched only when selected,
  with an earlier-messages control for older pages.
- Inline finding chats were removed. Both problem tables use `VulnerabilityView`.
