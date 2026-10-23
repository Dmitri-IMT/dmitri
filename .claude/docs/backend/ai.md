---
type: Module
title: Backend AI — fix tasks, explanations, chat and usage
description: OpenAI Responses integration for researched scan fix tasks, cached structured scan/machine explanations, web-assisted contextual chat and scoped usage metadata.
resource: backend/src/api/services/ai/jobs.py
tags: [backend, ai, openai, worker, scans, chat, telemetry]
timestamp: 2026-10-23T14:36:51Z
---

# Backend AI — fix tasks, explanations, chat and usage

## Purpose

`services/ai/` uses OpenAI Responses with `store:false`, configurable model/effort and
versioned task instructions. Scan facts use finding_N/machine_N references. Product and
version come from port CPEs; raw banners, addresses and names are not provider inputs.
The R3 research cache supplies checked source URLs for fix tasks. Chat can search the web.

## Key classes / functions

| Name | What it does |
|------|--------------|
| `OpenAIResponsesProvider` | Structured scan/chunk/synthesis/research/explanation calls and annotated chat; records input/cached/output/reasoning tokens and latency. |
| `request_scan_ai_analysis` | Queues a completed scan's analysis per language. Old output shapes return not_requested without deleting stored rows. |
| `process_ready_ai_analyses` | Claims jobs when scan enrichment is idle, researches fixes, analyzes bounded groups and synthesizes validated output. |
| `materialize_scan_ai_analysis` | Turns provider references into finding IDs; code orders tasks, assigns ranks, counts coverage and attaches checked R3 sources. |
| `explanation_context` | Authorizes completed scan or latest host context; builds anonymous facts and language-specific allowed count lead-ins. |
| `materialize_explanation` | Checks prose, count lead-ins, duplicates and reference grounding; scrubs credentials and restores display references locally. |
| `explain_context` route | POST `/api/v1/ai/explain`; cached structured output or synchronous provider call. |
| `ask_context_chat` route | POST `/api/v1/ai/chat`; scoped question with secret/address scrubbing and checked citations; returns the saved message and conversation IDs. |
| `list_context_conversations` route | GET `/api/v1/ai/chat/conversations`; private, contextual conversation titles and timestamps, 50 per page. |
| `list_context_chat` route | GET `/api/v1/ai/chat/history`; private messages for a conversation, newest page first with chronological entries. |
| `persist_usage_events` | Saves operational metadata only, including failures; never saves prompts in ai_usage. |

## How it connects

- `ai_explanations` has unique `(scope, context_id, language, prompt_version)` and a scan
  foreign key. Each cache read first resolves organisation ownership. Host cache entries
  refresh when the latest scan ID changes.
- A transaction-scoped PostgreSQL advisory lock serializes explanation generation for each
  context/language/prompt version. Cached reads skip anonymous model-context construction.
- Chat messages have a `conversation_id`; the API checks ownership and context before reuse.
  Saved messages are retained, rather than deleting everything after ten entries. Message and
  conversation reads page in batches of 50 and filter by both organisation and caller.
- Migration `20261024_48` groups existing transcripts by caller/context and adds the indexed,
  non-null conversation ID without deleting messages.
- `explain_scan`, `explain_host` and `chat` share `AI_CHAT_DAILY_LIMIT`, counted per user
  over the last 24 hours. Cached explanations do not consume another call.
- Scan and machine deletion remove their cached explanations. Migration `20261024_47`
  enables RLS, revokes public API-role access and grants runtime CRUD plus sequence use.
- [frontend AI](/frontend/scan-ai.md) renders fix tasks; [explanation panels](/frontend/context-ai.md)
  render the structured text and code-owned task pointer.

## Notes / gotchas

- Prompt version is 11. Versioned instruction files include `explain-scan.md` and
  `explain-machine.md`, with shared voice rules.
- Explanations do not use web search; fixes and task pointers remain code-owned.
- Cancelling the HTTP client does not cancel an already-running synchronous provider call.
- Scan analysis progress stores research/group/synthesis stage and completed/total groups.
- Org AI-language settings remain a separate PRD item; this change preserves the existing
  automatic-language behavior.
