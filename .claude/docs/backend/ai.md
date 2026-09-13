---
type: Module
title: Backend AI scan analysis
description: On-demand Groq overview of a completed scan. A member POSTs to request it; a separate worker loop claims one job after enrichment for that scan is idle; scan completion never enqueues AI.
resource: backend/src/api/services/ai/jobs.py
tags: [backend, ai, groq, worker, scans]
timestamp: 2026-09-13T16:40:00Z
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
| `ai_is_available()` | `AI_ENABLED` and a stripped non-empty `AI_API_KEY`. | `backend/src/api/services/ai/factory.py:10` |
| `build_ai_provider()` | Builds `GroqProvider` or `None`. | `backend/src/api/services/ai/factory.py:18` |
| `request_scan_ai_analysis()` | Org-scoped scan; `unavailable` if AI off or scan not completed; insert/`failed`→`pending`; else already-requested. | `backend/src/api/services/ai/jobs.py:38` |
| `get_scan_ai_analysis()` | `unavailable` / `not_requested` / row status. Foreign scan → `None` (404). | `backend/src/api/services/ai/read.py:54` |
| `claim_ai_analyses()` | Skip while enrichment is active for that `scan_id`. `FOR UPDATE SKIP LOCKED` on Postgres. Batch size 1 from the worker. | `backend/src/api/services/ai/jobs.py:133` |
| `process_ready_ai_analyses()` | Claim then `_process_claimed_analysis`. | `backend/src/api/services/ai/jobs.py:101` |
| `run_ai_worker_loop()` / `run_ai_worker_once()` | Own session and `AI_POLL_INTERVAL_SECONDS` (default 5). Provider required on `once`. | `backend/src/api/services/ai/worker.py:15`, `:36` |
| `build_scan_ai_context()` | Caps findings at `AI_MAX_FINDINGS` (default 10, max 15). Raises `ScanAINotReadyError` if the scan is not ready. | `backend/src/api/services/ai/context.py:23` |
| `generate_scan_analysis()` | Provider call then `validate_scan_analysis`. | `backend/src/api/services/ai/analyzer.py:8` |
| `GroqProvider.analyze_scan()` | OpenAI-compatible HTTP to `AI_API_BASE_URL` (Groq). Structured `ScanAIAnalysis`. | `backend/src/api/services/ai/groq.py:33` |
| `validate_scan_analysis()` | Finding ids and CVEs must already be in context; no invented hosts. | `backend/src/api/services/ai/validation.py:12` |
| `AI_PROMPT_VERSION` / `SYSTEM_PROMPT` | Prompt version `"2"`. English prose only; context is untrusted evidence. | `backend/src/api/services/ai/prompts.py:1` |
| `ScanAIAnalysis` / `ScanAIContext` | Internal JSON shapes (not the HTTP envelope). | `backend/src/api/services/ai/schemas.py:44`, `:84` |
| `ScanAIAnalysisResponse` | HTTP envelope. | `backend/src/api/schemas/ai.py:21` |
| `AIScanAnalysisRecord` | Table `ai_scan_analyses`; unique `scan_id`; completed requires `analysis_json`. | `backend/src/api/models/persistence.py:335` |

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
- **Failed POST retry** is the same button: status `failed` → POST 202 → `pending`, `attempts=0`.
- **Do not set `DATABASE_URL_DIRECT` on Railway.** Migrations stay operator-run.

# Citations

[1] [docs/adr/ADR-020-ai-scan-analysis.md](../../../docs/adr/ADR-020-ai-scan-analysis.md)
[2] [specs/047-pr-144-review-remediation/ARCHITECTURE.md](../../../specs/047-pr-144-review-remediation/ARCHITECTURE.md)
