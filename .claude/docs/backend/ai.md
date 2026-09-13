---
type: Module
title: Backend AI scan analysis
description: On-demand Groq overview of a completed scan. A member POSTs to request it; a separate worker loop claims one job after enrichment for that scan is idle; scan completion never enqueues AI.
resource: backend/src/api/services/ai/jobs.py
tags: [backend, ai, groq, worker, scans]
timestamp: 2026-09-13T20:00:00Z
---

# Backend AI scan analysis

## Purpose

`services/ai/` turns a **completed** scan into a structured English overview. Nothing in ingest or
`run_worker_once` starts a job. A signed-in member of any role calls
`POST /api/v1/scans/{scan_id}/analysis`. The API inserts (or, after `failed`, resets) one
`ai_scan_analyses` row at `pending`. The **worker process** (`worker_main`) starts
`run_ai_worker_loop` in a **daemon thread** only when `ai_is_available` (`AI_ENABLED` and a
non-empty `AI_API_KEY`). That loop is outside the enrichment loop. It claims **at most one**
requested row per tick, and only when the scan has **no** `enrichment_jobs` in `pending` or
`running`. Groq is the only provider (`GROQ_PROVIDER_ID = "groq"`). There is no `AI_PROVIDER`
setting.

Read status on the wire (`ScanAIAnalysisResponse.status`):

| Status | Meaning |
|--------|---------|
| `unavailable` | AI off, or the scan is not `completed`. No row. |
| `not_requested` | Completed scan, AI on, no row yet. |
| `pending` / `processing` | Row exists; worker has not finished. |
| `completed` | `analysis_json` stored; GET returns the validated `ScanAIAnalysis`. |
| `failed` | Terminal error; the same POST may reset the row to `pending`. |

A second POST while `pending`/`processing`/`completed` raises `AIAnalysisAlreadyRequestedError`
(router `409`). Concurrent first inserts rely on the unique `scan_id` constraint; the loser is
also `409`.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `ai_is_available()` | `AI_ENABLED` and a stripped non-empty `AI_API_KEY`. | `backend/src/api/services/ai/groq.py:142` |
| `build_ai_provider()` | Builds `GroqProvider` or `None`. | `backend/src/api/services/ai/groq.py:150` |
| `GroqProvider.analyze_scan()` | OpenAI-compatible HTTP to `AI_API_BASE_URL` (Groq). Structured `ScanAIAnalysis`. Errors raise `AIProviderError(code, retryable=...)`. | `backend/src/api/services/ai/groq.py:63` |
| `AI_PROMPT_VERSION` / `SYSTEM_PROMPT` | Prompt version `"2"`. English prose only; context is untrusted evidence. | `backend/src/api/services/ai/groq.py:14` |
| `request_scan_ai_analysis()` | Org-scoped scan; `unavailable` if AI off or scan not completed; insert/`failed`→`pending`; else already-requested. | `backend/src/api/services/ai/jobs.py:102` |
| `get_scan_ai_analysis()` | `unavailable` / `not_requested` / row status. Foreign scan → `None` (404). | `backend/src/api/services/ai/jobs.py:72` |
| `scan_ai_analysis_response()` | Picks the response variant from `record.status`. | `backend/src/api/services/ai/jobs.py:47` |
| `claim_ai_analyses()` | Calls the shared [`claim_jobs`](/backend/services.md) with running status `processing` and an extra filter: no `enrichment_jobs` in `pending`/`running` for that `scan_id`. | `backend/src/api/services/ai/jobs.py:197` |
| `process_ready_ai_analyses()` | Claim, build context, call the provider, check grounding, then `completed` or one `retry_or_fail`. | `backend/src/api/services/ai/jobs.py:165` |
| `_check_grounded()` | Every finding id in explanations and actions must be in the context; no duplicate explanations. Failure → `invalid_analysis`, not retried. | `backend/src/api/services/ai/jobs.py:279` |
| `build_scan_ai_context()` | Loads `ScanRecord` (not Scan Detail) plus `get_scan_risk_summary`, a host count and EPSS/KEV. Caps findings at `AI_MAX_FINDINGS` (default 10, max 15). Raises `ScanAINotReadyError` if the scan is not completed. | `backend/src/api/services/ai/context.py:82` |
| `ScanAIContext` / `AIFindingContext` | Internal prompt context shapes. | `backend/src/api/services/ai/context.py:58`, `:32` |
| `run_ai_worker_loop()` / `run_ai_worker_once()` | In `services/worker.py`. Own session and `AI_POLL_INTERVAL_SECONDS` (default 5); batch size 1; no command sweep. | `backend/src/api/services/worker.py:46`, `:57` |
| `ScanAIAnalysis` | Wire body of a completed analysis. | `backend/src/api/schemas/ai.py:33` |
| `ScanAIAnalysisResponse` | HTTP union keyed on `status`: `Unavailable` / `NotRequested` (`scan_id`, `status` only), `Queued` (`pending`/`processing`, job fields), `Failed` (+`completed_at`), `Completed` (+`completed_at`, `analysis`). | `backend/src/api/schemas/ai.py:86` |
| `AIScanAnalysisRecord` | Table `ai_scan_analyses`; unique `scan_id`; completed requires `analysis_json`; `next_attempt_at` and `last_error` like `enrichment_jobs`; `updated_at` set on update. | `backend/src/api/models/persistence.py:335` |

## How it connects

- HTTP: [routers](/backend/routers.md) `read_scan_ai_analysis` / `request_scan_ai_analysis_route`
  (`require_user`).
- Worker boot: [`worker_main.main`](/backend/api.md) starts the AI thread, then
  `run_worker_loop` ([services](/backend/services.md)) for enrichment only.
- Settings: `AI_*` on [`Settings`](/backend/api.md). The API and the worker both need
  `AI_ENABLED` + `AI_API_KEY` or GET stays `unavailable` even if jobs exist.
- SPA: [scan-ai](/frontend/scan-ai.md).
- Decision record: [ADR-020](../../docs/adr/ADR-020-ai-scan-analysis.md).

## Notes / gotchas

- **Enrichment blocks claim, not the POST.** A Samba/NSPi scan can leave hundreds of
  `nvd_cve` jobs. NVD is paced (`NVD_MIN_REQUEST_INTERVAL_SECONDS`, default 6). The card stays
  `pending` until those jobs leave `pending`/`running`.
- **Completing a scan never writes `ai_scan_analyses`.** There is no `enqueue_ready_ai_analyses`.
- **Retries** use `next_attempt_at = now + AI_RETRY_DELAY_SECONDS` through the shared `retry_or_fail`. Only retryable `AIProviderError`s retry, up to `AI_MAX_ATTEMPTS`.
- **Failed POST retry** is the same button: status `failed` → POST 202 → `pending`, `attempts=0`.
- **Do not set `DATABASE_URL_DIRECT` on Railway.** Migrations stay operator-run.

# Citations

[1] [docs/adr/ADR-020-ai-scan-analysis.md](../../../docs/adr/ADR-020-ai-scan-analysis.md)
[2] [specs/047-pr-144-review-remediation/ARCHITECTURE.md](../../../specs/047-pr-144-review-remediation/ARCHITECTURE.md)
