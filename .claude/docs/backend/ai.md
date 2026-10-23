---
type: Module
title: Backend AI — scan analysis, contextual chat, usage telemetry
description: Groq-backed scan overviews per language with bounded structured repair and KEV coverage, scoped Q&A on scans/hosts/findings, and org-scoped provider usage rows without storing prompts or answers in ai_usage.
resource: backend/src/api/services/ai/jobs.py
tags: [backend, ai, groq, worker, scans, chat, telemetry]
timestamp: 2026-10-12T00:00:00Z
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
   The claimed job calls `run_bounded_analysis`: Groq analyzes finding chunks, then synthesizes
   validated child results with explicit failed-finding references. The analyzer validates
   grounding, KEV coverage and writing style, with one provider repair per child or final result.
   Repair prompts include validation codes and guidance, never rejected prose. A repair that
   still omits KEV coverage fails; the worker never inserts actions or evicts recommendations.
   Coverage counts come from the analyzer. A failed job retry refreshes its prompt and writing
   skill versions.

2. **Contextual chat** — read-only Q&A grounded in org-scoped scan/host/finding evidence. Two
   routes, both on `routers/ai.py`: `POST /api/v1/ai/chat` and `GET /api/v1/ai/chat/history`, each
   taking `scope` (`scan`/`host`/`finding`) plus `context_id`. The per-resource paths
   (`/scans/{id}/chat`, `/hosts/{id}/explain`, `/findings/{id}/explain`) were deleted in PR #151.
   Every chat request body takes optional `language` (default `en`); the provider writes the answer
   in that language. History is capped at 10 messages per `(scope_type, scope_id)`. Host history
   spans all scans of that host, not only the latest one. A successful POST writes the usage rows
   and the transcript in one commit; when the provider fails, the usage rows are committed alone,
   because the tokens were spent.

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
   [explained reports](/backend/reports.md) add localized educational explanations and charts
   for every device and issue group even without a completed AI analysis. Available AI summaries,
   priorities and individual explanations are retained. Export reads existing advisory cache
   records without making new external advisory requests.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `ai_is_available()` / `build_ai_provider()` | Gate and construct `GroqProvider`. Accept `AI_API_KEY` as a `SecretStr` or a plain string. | `backend/src/api/services/ai/groq.py:536`, `:549` |
| `GroqProvider` | OpenAI-compatible HTTP to `AI_API_BASE_URL`. Active scan-job path uses `analyze_chunk` and `synthesize_scan` through the bounded analyzer; adapters without bounded support use `analyze_scan`. `repair_*` sends validation codes and concise corrections without rejected prose. Chat: `answer_question`. Every method takes keyword `language`; `_language_name()` maps it to English / Brazilian Portuguese / Russian in the system prompt. `AI_PROMPT_VERSION` is `"6"` (bumped for the evidence-completeness and CVE-correlation rules). `_coverage_notice` reads `evidence_completeness`: `partial` prepends the stop-reason notice from `stopped_by` (DMI-145), `unknown` prepends a notice that the scan does not report whether every check finished, `complete` adds nothing. The system prompt also says an NVD record proves a CVE exists, not that the target is affected; treats `cve_correlation` as unverified; and forbids claiming a clean target when `evidence_completeness` is `partial`/`unknown`. The synthesis aggregate carries `evidence_completeness` and `incomplete_check_count`; there is no `partial_result` key. Each HTTP round-trip records a `GroqUsageEvent` drained after the route returns. | `backend/src/api/services/ai/groq.py` |
| `ScanAIContext` | Scan-analysis context version `"4"`: includes `evidence_completeness` and `stopped_by` (`operator` \| `timeout` \| `error` \| null), mapped from `scan_terminated_by` (the same typed reader the scan list and detail use). A `cancelled` scan with no results gets no analysis. Also carries `evidence_completeness` and `incomplete_check_count` from `scan_evidence` (metadata plus typed coverage); `split_context` copies both into each chunk. `ScanChatContext` carries the same two fields; chat takes `evidence_completeness` straight from `ScanDetailResponse`. | `backend/src/api/services/ai/context.py:64` |
| `AIFindingContext.evidence_basis` | `cve_correlation` when `scan_evidence.is_cve_correlation` holds, else `target_observation`. Tells the model whether the finding was seen on the target or only correlated by version. | `backend/src/api/services/ai/context.py:42` |
| `drain_provider_usage()` / `persist_usage_events()` | Move provider events into `AIUsageRecord` rows (org/scan/user when known). | `backend/src/api/services/ai/telemetry.py:12`, `:17` |
| `answer_interactive_question()` | Calls `GroqProvider.answer_question`, then `materialize_chat_response` (finding refs to UUIDs and placeholder text to display values). | `backend/src/api/services/ai/chat.py` |
| `build_scan_chat_bundle()` / `build_host_chat_bundle()` / `build_finding_chat_bundle()` | Placeholder-only JSON for chat (`finding_N`, `machine_N`, `service_N`); no subnet, UUIDs, or raw evidence to Groq. | `backend/src/api/services/ai/chat.py` |
| `save_chat_message()` / `list_chat_messages()` | Persist Q&A under `scope_type` + `scope_id`; trim to `MAX_CHAT_HISTORY` (10). `list_chat_messages` takes `scan_id=None`; it filters on `scan_id` only for non-host scopes. | `backend/src/api/services/ai/chat.py:275`, `:316` |
| `lint_provider_analysis()` | Versioned writing skill in the requested language. The analyzer allows one provider repair; the result must pass both grounding and style checks. | `backend/src/api/services/ai/writing.py:10` |
| `validate_analysis_with_repair()` | Validates references, duplicate explanations, KEV action coverage and writing; repairs once, then accepts or fails without local action insertion. | `backend/src/api/services/ai/analyzer.py` |
| `materialize_chat_response()` / `scrub_secrets()` | Chat answers are plain text from `answer_question` (`web_search`, `ProviderChatAnswer` of text parts, `url_citation` spans and consulted sources). Only citations whose cleaned URL is in the sources become `[host](url)` links; other links, raw URLs, HTML, headings and code marks are removed. `scrub_secrets` removes credentials and addresses from the question and history, credentials only from answers. | `backend/src/api/services/ai/chat.py` |
| `describe_observed_products()` | Sets `service`, `product` and `version` on finding contexts from the port's application CPE. Raw banners are never used. | `backend/src/api/services/ai/context.py` |
| `attach_fix_records()` | Runs in the analysis job before `run_bounded_analysis` when the provider has `research_fix`. One target per CVE + observed product + version (product from the port CPE, else service name and banner). Reads current `ai_fix_records` rows, researches the rest in parallel (`MAX_PARALLEL_RESEARCH` 5) with `web_search`, keeps only options whose `source_url` is in that response's `action.sources`, strips `utm_source` and Markdown links, saves, and sets `fix_options` / `version_affected` on each `AIFindingContext`. A rate limit re-raises after saving the other records; other provider errors skip that CVE. | `backend/src/api/services/ai/research.py` |
| `AIFixRecord` | Table `ai_fix_records`, shared across orgs. Current while `expires_at` (14 days with a full fix, 2 without; `AI_FIX_RECORD_TTL_*`) has not passed and the KEV fingerprint and NVD `lastModified` (from the `cve:` NVD cache row) are unchanged. | `backend/src/api/models/persistence.py` |
| `run_bounded_analysis()` | Canonical worker analysis path. Runs and validates child chunks, records failed references, synthesizes and validates the final result, and returns coverage counts. | `backend/src/api/services/ai/analyzer.py`, `backend/src/api/services/ai/jobs.py` |
| `request_scan_ai_analysis()` / `get_scan_ai_analysis()` | On-demand analysis request and read, both keyed by `(scan_id, language)`. `request_scan_ai_analysis(commit=False)` leaves the commit to the caller. | `backend/src/api/services/ai/jobs.py:121`, `:89` |
| `enqueue_auto_scan_analysis()` | Insert the pending `en` row when `AI_AUTO_ANALYSIS` + `AI_ENABLED` + key; no-op if enrichment still active or row already exists. Called from `persist_scan` (`commit=False`) and after enrichment. | `backend/src/api/services/ai/jobs.py:191`, `backend/src/api/services/persistence.py:188` |
| `_enqueue_auto_analysis_safely()` | Called from enrichment job completion paths; logs and swallows enqueue failures. | `backend/src/api/services/enrichment.py:115` |
| `claim_ai_analyses()` / `process_ready_ai_analyses()` | Worker claim (enrichment gate) and processing in the row's `language`. | `backend/src/api/services/ai/jobs.py:270`, `:238` |
| `run_ai_worker_loop()` / `run_ai_worker_once()` | Dedicated poll loop in `services/worker.py`. | `backend/src/api/services/worker.py:46`, `:57` |
| `get_ai_usage()` / `list_context_chat()` / `ask_context_chat()` | Org usage dashboard and unified chat API. | `backend/src/api/routers/ai.py:50`, `:112`, `:137` |
| `read_scan_ai_chat()` / `ask_scan_ai()` | Scan-scoped chat (scope `scan`). | `backend/src/api/routers/scans.py:63`, `:218` |
| `build_scan_report()` / `render_scan_report_pdf()` | [Explained reports](/backend/reports.md) combine scan/risk facts, optional AI and deterministic educational guidance: all devices, five vector visuals, endpoint-specific impacts and correction checks, glossary and complete finding register. Technical reports download as JSON; only explained reports use PDF. | `backend/src/api/services/reports.py:24`, `backend/src/api/services/report_pdf.py` |
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
  (`/ai/chat` everywhere: the floating assistant plus the one-shot cards in `FindingPanel`
  and `HostDetail`),
  [ai-usage](/frontend/ai-usage.md), [home-ai-overview](/frontend/home-ai-overview.md).
- Decision record: [ADR-020](../../docs/adr/ADR-020-ai-scan-analysis.md).

## Notes / gotchas

- **Enrichment blocks analysis claim, not the POST or auto-enqueue check.** Auto-enqueue runs only when
  no enrichment jobs remain active for that scan.
- **Ingest can write `ai_scan_analyses`.** With `AI_AUTO_ANALYSIS` on, `persist_scan` enqueues the
  `en` row in the same transaction. Other languages are only ever created by a member POST.
- **`supports_bounded_scan_analysis()`** selects chunked analysis inside the worker's `run_bounded_analysis()` call. Failed children remain visible in coverage counts.
- **Retired vocabulary must be named in the prompt.** `services/ai/instructions/voice.md` and the `retired_vocabulary` repair guidance in `_writing_guidance()` list every word in `_RETIRED_WORDS` with its replacement (vulnerability, machine). The lint matches those English words in any language; when the prompt stopped naming them, English overviews failed `style_violation` even after repair.
- **The AI job's stale window is `AI_TIMEOUT_SECONDS × 10`.** One job makes the research calls plus several chunk, synthesis and repair calls; a shorter window let a slow but live job be claimed twice.
- **Fix-task shape (prompt 11+)** — `ScanAIAnalysis` is `summary`, `tasks` (`AIFixTask`, ranked by `materialize_scan_ai_analysis`: time, highest risk, problems fixed; sources from `AIFindingContext._fix_sources`), `findings` (`AIFindingNote` with `task_rank`) and `not_checked`. `get_scan_ai_analysis` returns `not_requested` for completed rows older than `FIX_TASK_SHAPE_SINCE`, and a new request resets them.
- **Analysis progress** — `_process_claimed_analysis` commits `progress_stage` / `progress_done` / `progress_total` before research (`fixes`), before each chunk (`groups`, done = chunks finished) and before synthesis (`summary`); `scan_ai_analysis_response` returns them as `progress` only while `processing`.
- **Chat daily limit** — `AI_CHAT_DAILY_LIMIT` counts the user's `ai_usage` rows with operation `chat` in the last 24 hours; 429 `ai_daily_limit`.
- **Fix research never sees org data.** Its input is the CVE, product, version, service type and feed values. Analysis and synthesis receive fix records, never web page text.
- **Writing and grounding repairs** log only the validation phase and category. The worker never logs provider response text; rejected prose is not sent back to Groq.
- **PDF rendering needs a Unicode TTF on the host.** `_register_unicode_fonts()`
  (`_register_unicode_fonts` in `report_pdf.py`) looks only at fixed paths — macOS Supplemental Arial,
  Windows Arial, Linux DejaVu Sans, Linux Liberation Sans — and raises `RuntimeError` when none exists.
- **Chat errors** — `ai_unavailable` (503), `ai_rate_limited` (429, localized body from `chat_api_error_message`), `ai_context_too_large`
  (413), `ai_provider_error` (502). Scan chat adds `scan_not_ready` (409) when the scan is not
  `completed`.
- **Usage rows** may omit `user_id` on worker-driven scan analysis; interactive chat sets org, scan,
  and user when persisting events.
- **Do not set `DATABASE_URL_DIRECT` on Railway.** Migrations stay operator-run.

# Citations

[1] [docs/adr/ADR-020-ai-scan-analysis.md](../../../docs/adr/ADR-020-ai-scan-analysis.md)
