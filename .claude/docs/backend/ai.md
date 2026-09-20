---
type: Module
title: Backend AI — scan analysis, contextual chat, usage telemetry
description: Groq-backed scan overviews per scan and output language (on-demand, or auto at ingest and after enrichment), scoped Q&A on scans/hosts/findings, and org-scoped provider usage rows without storing prompts or answers in ai_usage.
resource: backend/src/api/services/ai/jobs.py
tags: [backend, ai, groq, worker, scans, chat, telemetry]
timestamp: 2026-09-19T21:00:00Z
---

# Backend AI — scan analysis, contextual chat, usage telemetry

## Purpose

`services/ai/` is the Groq integration layer. Three product surfaces share one provider (`GROQ_PROVIDER_ID =
"groq"`; no `AI_PROVIDER` setting):

1. **Scan analysis** — a structured overview for a **completed** scan (`ai_scan_analyses`), one row
   per `(scan_id, language)`. `language` is `AILanguage` (`en`, `pt-BR`, `ru`; default `en`) and is
   sent as a query parameter on GET/POST `/scans/{id}/analysis`. Members POST to request it. The
   automatic path (`AI_AUTO_ANALYSIS=true`) always enqueues the `en` row: `persist_scan` calls
   `enqueue_auto_scan_analysis(commit=False)` inside the ingest transaction (this covers scans with no
   enrichment jobs), and the enrichment worker calls it again when the last job is terminal. The **worker process**
   (`worker_main`) runs `run_ai_worker_loop` in a daemon thread when `ai_is_available` (`AI_ENABLED`
   plus a non-empty `AI_API_KEY`). That loop is separate from enrichment; it claims at most one
   analysis row per tick and only when no `enrichment_jobs` for that scan are `pending` or `running`.

2. **Contextual chat** — read-only Q&A grounded in org-scoped scan/host/finding evidence. Routes live
   on `routers/ai.py` (`/api/v1/ai/chat`, `/api/v1/ai/chat/history`) and on legacy per-resource paths
   (`/scans/{id}/chat`, `/hosts/{id}/explain`, `/findings/{id}/explain`). Every chat request body
   takes optional `language` (default `en`); the provider writes the answer in that language. History
   is capped at 10 messages per `(scope_type, scope_id)`. Host history (`GET /hosts/{id}/explain`)
   spans all scans of that host, not only the latest one.

3. **Usage telemetry** — each provider call appends operational metadata to `ai_usage` via
   `drain_provider_usage` / `persist_usage_events`. Prompts and model text are **not** stored there.

Read status for scan analysis (`ScanAIAnalysisResponse.status`):

| Status | Meaning |
|--------|---------|
| `unavailable` | AI off, or the scan is not `completed`. No row. |
| `not_requested` | Completed scan, AI on, no row yet. |
| `pending` / `processing` | Row exists; worker has not finished. |
| `completed` | `analysis_json` stored; GET returns the validated `ScanAIAnalysis`. |
| `failed` | Terminal error; the same POST may reset the row to `pending`. |

A second POST for the same language while `pending`/`processing`/`completed` raises
`AIAnalysisAlreadyRequestedError` (router `409`). Concurrent first inserts rely on the unique
`(scan_id, language)` constraint (`uq_ai_scan_analyses_scan_language`); the loser is also `409`.
Each language is a separate job and a separate provider run.

4. **Reports** — `build_scan_report(language=…)` reads the analysis row for the requested language;
   the explained PDF uses per-language copy (`_COPY`, `_LEVELS` in `report_pdf.py`) and localized
   fallback text when no completed analysis exists.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `ai_is_available()` / `build_ai_provider()` | Gate and construct `GroqProvider`. Accept `AI_API_KEY` as a `SecretStr` or a plain string. | `backend/src/api/services/ai/groq.py:466`, `:479` |
| `GroqProvider` | OpenAI-compatible HTTP to `AI_API_BASE_URL`. Scan path: `analyze_scan`, chunked `analyze_chunk`, `repair_*`, `synthesize_scan`. Chat: `answer_question`. Every method takes keyword `language`; `_language_name()` maps it to English / Brazilian Portuguese / Russian in the system prompt. `AI_PROMPT_VERSION` is `"4"`. Each HTTP round-trip records a `GroqUsageEvent` drained after the route returns. | `backend/src/api/services/ai/groq.py:73`, `:419`, `:22` |
| `drain_provider_usage()` / `persist_usage_events()` | Move provider events into `AIUsageRecord` rows (org/scan/user when known). | `backend/src/api/services/ai/telemetry.py:12`, `:17` |
| `AIOrchestrator.answer_question()` | Thin coordinator; passes `language` to the provider (falls back to a call without it on a `TypeError` naming `language`); `materialize_chat_response` maps provider finding refs to UUIDs. | `backend/src/api/services/ai/orchestrator.py:25` |
| `build_chat_context()` / `build_host_context()` / `build_finding_context()` | Bounded JSON contexts for chat; scan context can include a clipped completed overview. | `backend/src/api/services/ai/chat.py:21`, `:157`, `:130` |
| `save_chat_message()` / `list_chat_messages()` | Persist Q&A under `scope_type` + `scope_id`; trim to `MAX_CHAT_HISTORY` (10). `list_chat_messages` takes `scan_id=None`; it filters on `scan_id` only for non-host scopes. | `backend/src/api/services/ai/chat.py:275`, `:316` |
| `lint_provider_analysis()` | Versioned writing skill after structural validation. | `backend/src/api/services/ai/writing.py` |
| `run_bounded_analysis()` | Chunked scan analysis pipeline; threads `language` to every provider call through `_call_with_language`. | `backend/src/api/services/ai/analyzer.py:28`, `:133` |
| `request_scan_ai_analysis()` / `get_scan_ai_analysis()` | On-demand analysis request and read, both keyed by `(scan_id, language)`. `request_scan_ai_analysis(commit=False)` leaves the commit to the caller. | `backend/src/api/services/ai/jobs.py:121`, `:89` |
| `enqueue_auto_scan_analysis()` | Insert the pending `en` row when `AI_AUTO_ANALYSIS` + `AI_ENABLED` + key; no-op if enrichment still active or row already exists. Called from `persist_scan` (`commit=False`) and after enrichment. | `backend/src/api/services/ai/jobs.py:191`, `backend/src/api/services/persistence.py:188` |
| `_enqueue_auto_analysis_safely()` | Called from enrichment job completion paths; logs and swallows enqueue failures. | `backend/src/api/services/enrichment.py:115` |
| `claim_ai_analyses()` / `process_ready_ai_analyses()` | Worker claim (enrichment gate) and processing in the row's `language`. | `backend/src/api/services/ai/jobs.py:270`, `:238` |
| `run_ai_worker_loop()` / `run_ai_worker_once()` | Dedicated poll loop in `services/worker.py`. | `backend/src/api/services/worker.py:46`, `:57` |
| `get_ai_usage()` / `list_context_chat()` / `ask_context_chat()` | Org usage dashboard and unified chat API. | `backend/src/api/routers/ai.py:50`, `:112`, `:137` |
| `read_scan_ai_chat()` / `ask_scan_ai()` | Scan-scoped chat (scope `scan`). | `backend/src/api/routers/scans.py:63`, `:218` |
| `build_scan_report()` / `render_scan_report_pdf()` | Report JSON and PDF for one `language` (`?language=` on `/scans/{id}/reports/{kind}` and `/download`). | `backend/src/api/services/reports.py:20`, `backend/src/api/services/report_pdf.py:46` |
| `AIScanAnalysisRecord` | Table `ai_scan_analyses`; `language` column, unique `(scan_id, language)`, coverage + writing-skill versions. | `backend/src/api/models/persistence.py:360` |
| `AIChatMessageRecord` | Table `ai_chat_messages`; `scope_type` + `scope_id` index the thread. | `backend/src/api/models/persistence.py:407` |
| `AIUsageRecord` | Table `ai_usage`; token/latency metadata only. | `backend/src/api/models/persistence.py:47` |
| `AILanguage` / `ScanAIAnalysis` / `ScanAIAnalysisResponse` / `AIChatResponse` | Wire models in `schemas/ai.py`. `AILanguage = Literal["en", "pt-BR", "ru"]`. | `backend/src/api/schemas/ai.py:12` |

## How it connects

- Analysis HTTP: [routers](/backend/routers.md) on `scans.py` (`read_scan_ai_analysis`,
  `request_scan_ai_analysis_route`).
- Chat HTTP: `ai.router` plus `scans.py`, `hosts.py`, and `findings.py` explain/chat routes —
  mounted from [`main.py`](/backend/api.md) (`app.include_router(ai.router)` at `:170`).
- Worker boot: [`worker_main.main`](/backend/api.md) starts the AI thread, then enrichment
  ([services](/backend/services.md)).
- Settings: `AI_*` including `AI_AUTO_ANALYSIS` on [`Settings`](/backend/api.md).
- SPA: [scan-ai](/frontend/scan-ai.md) (overview jobs), [context-ai](/frontend/context-ai.md)
  (`/ai/chat` on scan/host routes plus `/explain` one-shots in `FindingPanel` and `HostDetail`),
  [ai-usage](/frontend/ai-usage.md), [home-ai-overview](/frontend/home-ai-overview.md).
- Decision record: [ADR-020](../../docs/adr/ADR-020-ai-scan-analysis.md).

## Notes / gotchas

- **Enrichment blocks analysis claim, not the POST or auto-enqueue check.** Auto-enqueue runs only when
  no enrichment jobs remain active for that scan.
- **Ingest can write `ai_scan_analyses`.** With `AI_AUTO_ANALYSIS` on, `persist_scan` enqueues the
  `en` row in the same transaction. Other languages are only ever created by a member POST.
- **`_call_with_language` exists twice** (`analyzer.py:133`, `jobs.py:406`) and in
  `AIOrchestrator`: each retries a provider call without `language` when the `TypeError` names it, so
  older test doubles keep working.
- **PDF rendering needs a Unicode TTF on the host.** `_register_unicode_fonts()`
  (`report_pdf.py:68`) looks only at fixed paths — Windows Arial, Linux DejaVu Sans, Linux Liberation
  Sans — and raises `RuntimeError` when none exists. macOS keeps Arial at another path, so a local PDF
  download fails there.
- **Chat errors** — `ai_unavailable` (503), `ai_rate_limited` (429, Portuguese body), `ai_context_too_large`
  (413), `ai_provider_error` (502). Scan chat adds `scan_not_ready` (409) when the scan is not
  `completed`.
- **Usage rows** may omit `user_id` on worker-driven scan analysis; interactive chat sets org, scan,
  and user when persisting events.
- **Do not set `DATABASE_URL_DIRECT` on Railway.** Migrations stay operator-run.

# Citations

[1] [docs/adr/ADR-020-ai-scan-analysis.md](../../../docs/adr/ADR-020-ai-scan-analysis.md)
