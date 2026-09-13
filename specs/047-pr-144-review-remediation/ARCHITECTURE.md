# ARCHITECTURE — Review and remediate PR #144

Linear: DMI-158 (+ DMI-160) · Source of truth: [`TRUTH.md`](TRUTH.md) · PR: #144 (head branch
`feature/ia-implementation`) · Working branch: `feature/dmi-158-review-pr-144` · Integrated
with `origin/main` `0333077` (merge `4ab33eb`).

This is a review/remediation spec, not a new feature. §1 records what PR #144 built at
`7997383`, before any remediation. §2 maps each decision in the TRUTH decision log to the code it
changes, split into PR #144 changes and Epic targets. Decisions are made in `TRUTH.md`, not here. Where this file and the TRUTH decision log
disagree, TRUTH wins and this file is the bug.

**Hardware agent: not touched.** PR #144 changes no file under `hardware-agent/`. The CLAUDE.md
`ScanRunner` / `ScanProgressScreen` rule does not apply. The integration rule is applied to the
backend call paths that do change (worker loop, enrichment clients, AI job flow), see §4.

---

## 1. System context (as built at `7997383`, before remediation)

Historic record. Paths, revision ids (`20260911_20`, `20260912_21`, `20260912_22`) and the
import command below describe the PR as opened. Current state is in `TRUTH.md` "Integration
status" and §2.

Base facts found while reading:

- The branch forks from `08c1284` (merge of PR #139, the revert of PR #138). It is **not** on
  current `main`: `main` has since merged PR #141 and PR #143 (DMI-139 machine inventory).
- Commit `1b072dd` reverts the revert (re-applies PR #138). Commits `1946c94`…`7997383` add
  parts 2–4.
- 73 files, +5395/−85. Backend is the bulk; frontend adds two surfaces; the OpenAPI contract grows
  by 365 lines.

End-to-end flow after the PR:

```
Pi / backend-import-scan ──► ingest_scan (persistence.py) ──► scans, scan_hosts(+industrial_services_json),
                                                               findings, enrichment_jobs
backend-worker loop (worker.py)
  ├─ sweep_stale_commands
  ├─ process_pending_enrichment_jobs ──► NvdClient (rate-spaced, NvdTemporaryError → retry)
  └─ if AI available: process_ready_ai_analyses
         enqueue (completed scan, no active enrichment, no analysis row)
         claim → build_scan_ai_context → GroqProvider.analyze_scan → validate → ai_scan_analyses
FastAPI reads ──► /scans/{id}, /scans/{id}/risk-summary, /scans/{id}/analysis, /findings/{id}, /hosts/{id}
Frontend ScanDetail ──► ScanAIAnalysis (polls /analysis) + ScanIndustrialServices; HostDetail ──► IndustrialServices
```

### Part 1 — Industrial services and risk context (re-applied PR #138)

| Aspect | As built |
|--------|----------|
| Migration | `backend/alembic/versions/20260911_20_industrial_services_inventory.py` — revision `20260911_20`, `down_revision = ("20260905_19", "20260908_19")` (a merge revision). Adds `industrial_services_json JSON NOT NULL` (server default `'[]'` then dropped) to `scan_hosts` and `hosts`. Downgrade drops both. |
| Models | `backend/src/api/models/persistence.py:61`, `:85` — `ScanHostRecord.industrial_services_json`, `HostRecord.industrial_services_json`. |
| Ingest | `backend/src/api/services/persistence.py:294` — dumps `HostPayload.industrial_services` (`ModbusTcpServicePayload`, `schemas/scan.py:103`) into the row. This closes the DMI-142 gap. |
| Host rollup | `backend/src/api/services/hosts.py:64`, `:94` — copied on create; overwritten on update only when non-empty. |
| Read schemas | `backend/src/api/schemas/read.py` — `ScanHostView.industrial_services`, `HostDetailResponse.industrial_services` (type `ModbusTcpServicePayload`, which carries `values`, `value_min`, `value_max`, `nonzero_count`, and `validations` with `original_value` / `test_value` / `final_value`); `FindingRead` gains `risk_score`, `exploitability`, `confidence`, `risk_rationale`; new `SeverityBreakdown`, `ScanRiskSummaryResponse`. |
| Read services | `backend/src/api/services/read.py` — `get_finding_detail` (`:335`), `get_scan_risk_summary` (`:352`, `top_limit=10`), `_to_industrial_services` (`:499`), `findings_with_risk` (`:505`); `services/home.py` switches to `findings_with_risk`. |
| Routes | `GET /api/v1/scans/{scan_id}/risk-summary` (`routers/scans.py:95`, `getScanRiskSummary`); `GET /api/v1/findings/{finding_id}` (`routers/findings.py:18`, `getFindingById`). |
| Frontend | `frontend/src/pages/hosts/IndustrialServices.tsx` (renders min/max and validation counts), `frontend/src/pages/scans/ScanIndustrialServices.tsx`, wired in `pages/HostDetail.tsx:60` and `pages/ScanDetail.tsx`; risk fields in `pages/scans/FindingPanel.tsx`; fixtures `src/test/industrialFixtures.ts`. |
| Other | `.gitattributes` (LF for `docker/pi-simulator/*.sh`); `backend/tests/conftest.py` `_migrate` now handles multiple current heads. |
| Tests | `test_industrial_services_migration.py`, `test_finding_risk_read.py`, `test_host_materialisation.py`, `test_ingest_scan.py`, `test_read_findings.py`, `test_read_hosts.py`, `test_read_scans.py`; frontend `HostDetail.test.tsx`, `ScanDetail.test.tsx`, `IndustrialServices.test.tsx`, `FindingPanel.test.tsx`. |

### Part 2 — AI scan analysis (Groq)

| Aspect | As built |
|--------|----------|
| Settings | `backend/src/api/core/config.py:25-46` — `AI_ENABLED` (default `false`), `AI_PROVIDER` (`Literal["groq"]`), `AI_MODEL` (`openai/gpt-oss-120b`), `AI_API_KEY` (`SecretStr \| None`), `AI_API_BASE_URL` (`https://api.groq.com/openai/v1`), `AI_MAX_FINDINGS` (10, 1–15), `AI_TIMEOUT_SECONDS` (30), `AI_MAX_OUTPUT_TOKENS` (4096), `AI_REASONING_EFFORT` (`low`), `AI_MAX_ATTEMPTS` (2), `AI_RETRY_DELAY_SECONDS` (30). Mirrored in `backend/.env.example`. |
| Availability | `services/ai/factory.py` — `ai_is_available()` = enabled **and** non-blank key. `build_ai_provider()` always returns `GroqProvider` (ignores `ai_provider`). |
| Provider boundary | `services/ai/provider.py` — `AIProvider` Protocol (`analyze_scan`), `AIProviderError(code, retryable)`. |
| Adapter | `services/ai/groq.py` — raw `httpx` POST to `{base_url}/chat/completions` with `response_format=json_schema` (strict, `ScanAIAnalysis.model_json_schema()`), `max_completion_tokens`, `reasoning_effort`, `include_reasoning=False`. HTTP status → error code map in `_http_error`. |
| Prompt | `services/ai/prompts.py` — `AI_PROMPT_VERSION="1"`; system prompt forbids inventing facts and asks for **Brazilian Portuguese** prose; user prompt embeds `context.model_dump_json()`. |
| Context | `services/ai/context.py` — `build_scan_ai_context` (field list in §2 D2). |
| Schemas | `services/ai/schemas.py` — `AIFindingContext`, `ScanAIContext` (`context_version="1"`), `ScanAIAnalysis`, `AIRecommendedAction`, `AIFindingExplanation`; all `extra="forbid"`. |
| Grounding check | `services/ai/validation.py` — rejects finding ids outside the context and duplicate explanations. `analyzer.py` = provider call + validation. |
| Jobs | `services/ai/jobs.py` — `process_ready_ai_analyses` → `enqueue_ready_ai_analyses` (completed scans with `org_id`, no active enrichment job, no analysis row; `FOR UPDATE SKIP LOCKED`) → `claim_ai_analyses` (pending past retry delay, or stale `processing`; exhausted stale → `failed/processing_timeout`) → `_process_claimed_analysis` (success stores `analysis_json` + SHA-256 `context_hash`; errors via `_handle_attempt_error`). |
| Worker wiring | `services/worker.py:70-82` — after enrichment in the **same** `run_worker_once` loop; `stale_after_seconds=max(ai_timeout_seconds*2, 60)`. |
| Table | `backend/alembic/versions/20260912_21_ai_scan_analyses.py` — revision `20260912_21`, down `20260911_20`. Table `ai_scan_analyses` (unique `scan_id`, FK `scans.scan_id ON DELETE CASCADE`, status check, completed-needs-payload check, `attempts >= 0`), RLS on, `anon`/`authenticated` revoked, `dmitri_runtime` gets SELECT/INSERT/UPDATE. Model `AIScanAnalysisRecord` at `models/persistence.py:250`. |
| Read | `services/ai/read.py` `get_scan_ai_analysis` → `unavailable` when AI off or scan failed; `pending` when no row; else row status (+ payload when completed). Response `schemas/ai.py` `ScanAIAnalysisResponse` (validator ties payload to `completed`). |
| Route | `GET /api/v1/scans/{scan_id}/analysis` (`routers/scans.py:111`, `getScanAIAnalysis`, `require_user`, 404 for foreign scan). |
| Frontend | `frontend/src/api/scans.ts` `getScanAnalysis`; `api/queryKeys.ts` `scans.analysis`; `pages/scans/ScanAIAnalysis.tsx` (states: unavailable → render nothing; request error → retry card; pending/processing → poll every 3 s; failed → notice; completed → summary); mounted at top of `pages/ScanDetail.tsx`; MSW handler in `src/test/mswHandlers.ts`. |
| Contract | `contracts/openapi/openapi.yaml` adds the path + `AIRecommendedAction`, `AIFindingExplanation`, `ScanAIAnalysis`, `ScanAIAnalysisResponse`; `frontend/src/types/openapi.d.ts` regenerated. |
| Docs | `docs/roadmap/AI.md` rewritten (Groq pilot, chat, reports, Home summary); `docs/roadmap/README.md` row; `backend/README.md` (Portuguese AI + import section); `docs/implementation/INTELLIGENCE-IA-ASSESSMENT-ROADMAP.md` +3 lines. No ADR. |
| Tests | `test_ai_analysis.py`, `test_ai_analysis_read.py`, `test_ai_context.py`, `test_ai_groq.py`, `test_ai_jobs.py`, `test_worker_sweep.py` (AI after enrichment), `test_contract_fidelity.py`, `test_health.py`; frontend `ScanAIAnalysis.test.tsx`, `ScanDetail.test.tsx`. |

### Part 3 — NVD enrichment retries

| Aspect | As built |
|--------|----------|
| Settings | `config.py:63` `NVD_MIN_REQUEST_INTERVAL_SECONDS` (6); `config.py:77-94` `ENRICHMENT_MAX_ATTEMPTS` (3), `ENRICHMENT_RETRY_DELAY_SECONDS` (30), `ENRICHMENT_STALE_AFTER_SECONDS` (120). |
| Migration | `backend/alembic/versions/20260912_22_enrichment_retries.py` — revision `20260912_22`, down `20260912_21`; adds indexed `enrichment_jobs.next_attempt_at`. Model `models/persistence.py:176`. |
| NVD client | `services/nvd.py:16` `NvdTemporaryError(code, retry_after_seconds)`; per-instance `threading.Lock` spacing requests (`:32`, `:60`, sleeps while holding the lock); transport error / 5xx → `nvd_unavailable` (30 s); 429 → `nvd_rate_limited` with `Retry-After` (`_retry_after_seconds`, `:108`). |
| Claim | `services/enrichment.py:24` `claim_pending_enrichment_jobs(now=…)` reads `get_settings()` inside; marks stale exhausted `running` jobs `failed`; claims `pending` with `next_attempt_at` due, or stale `running`. |
| Process | `enrichment.py:115` `except NvdTemporaryError` → back to `pending` with `next_attempt_at = now + max(retry_after, retry_delay)` or `failed`; `:137` generic `except Exception` still writes `last_error = str(exc)` untruncated (`:145`). |
| Worker | `services/worker.py:28` — one `NvdClient` for the loop lifetime, passed into `run_worker_once(nvd_client=…)`. |
| Tests | `test_enrichment_retries.py`, `test_nvd_resilience.py`, `test_worker_sweep.py`, `test_settings.py`. |

### Part 4 — Local scan import

| Aspect | As built |
|--------|----------|
| Command | `backend/src/api/management/import_scan.py`; console script `backend-import-scan` in `backend/pyproject.toml`. |
| Behaviour | `--file` + exactly one of `--agent-id` / `--org-id`. Validates JSON against `ScanIngestRequest` before any DB write. `--org-id` finds or **creates** an `Agent` named `Local JSON importer` with a freshly generated public key whose private key is discarded. Calls `ingest_scan` (same path as `POST /api/v1/scans`), prints `status=imported`, ids and counts. |
| Docs | `backend/README.md` (Windows paths). Not in `docs/DEV-SETUP.md`, not in `.claude/docs/backend/management.md`. |
| Tests | `test_import_scan.py` (8 tests), `test_migrations.py` (console-script set). |

---

## 2. Decisions applied to code

The TRUTH decision log splits every decision into **PR** scope (built in PR #144) and **Epic**
scope (target design for an issue under the "Improve AI scan analysis" epic). This section
lists PR changes first, then the Epic targets that issues will carry. PR #144 keeps the
author's features: Groq adapter, context builder, job table, analysis card, NVD retries,
industrial and risk UI.

### 2.1 PR #144 changes

#### D10 — `Explain this scan` replaces automatic analysis

| Change | Where |
|--------|-------|
| New route `POST /api/v1/scans/{scan_id}/analysis`, `operationId: requestScanAIAnalysis`, `require_user` (any member), 404 for a foreign scan. AI unavailable or scan not completed → returns `unavailable`, creates nothing. No row → insert `pending`, return 202 with the response. `failed` row → reset to `pending`, `attempts=0`, clear `last_error_code`, return 202. `pending` / `processing` / `completed` row → **409**, no change. Insert uses the unique `scan_id` constraint so two concurrent presses create one row and the loser gets 409. Response `ScanAIAnalysisResponse` | `routers/scans.py`, `services/ai/jobs.py` (`request_scan_ai_analysis`) |
| Remove `enqueue_ready_ai_analyses` and its call; the worker only claims existing rows. The "no active enrichment job" condition moves into the claim, so a requested job waits for enrichment | `services/ai/jobs.py` |
| Read route: no row → new status `not_requested` (was `pending`). `unavailable` unchanged | `services/ai/read.py`, `schemas/ai.py` (`AIAnalysisReadStatus`) |
| Contract: new operation; `not_requested` added to the status enum; regenerate types | `contracts/openapi/openapi.yaml`, `frontend/src/types/openapi.d.ts` |
| Frontend: only `not_requested` and `failed` render the outline `Explain this scan` button in the card footer; every other status renders no button. Pressing it disables it, calls the POST, writes the response into the query cache, and polls every 3 s only while `pending`/`processing`, for at most 5 minutes. A 409 refetches the analysis status (someone else already asked) | `api/scans.ts` (`requestScanAnalysis`), `pages/scans/ScanAIAnalysis.tsx`, `test/mswHandlers.ts` |
| No org setting, no requester column, no audit event | — |

Call sites to check (CLAUDE.md integration rule): `process_ready_ai_analyses` (`services/worker.py`,
`tests/test_ai_jobs.py`, `tests/test_worker_sweep.py`), `get_scan_ai_analysis`
(`routers/scans.py`, `tests/test_ai_analysis_read.py`), `ScanAIAnalysis` (`pages/ScanDetail.tsx`,
`ScanDetail.test.tsx`).

#### D3 — AI loop outside the enrichment loop (P6)

| Change | Where |
|--------|-------|
| Remove the AI block from `run_worker_once`; it returns the enrichment count only | `services/worker.py` |
| New `run_ai_worker_loop()` and `run_ai_worker_once()`: own `get_session()`, own poll interval (`AI_POLL_INTERVAL_SECONDS`, default 5), builds the provider once, claims and processes at most one job per tick, catches and logs exceptions per tick | `services/ai/worker.py` (new) |
| `worker_main.main()` starts `run_ai_worker_loop` in a daemon thread when `ai_is_available(settings)`, then runs `run_worker_loop()` as today | `worker_main.py` |
| Setting `AI_POLL_INTERVAL_SECONDS` | `core/config.py`, `backend/.env.example`, `tests/test_settings.py` |

No new Railway service: both loops run in the existing `worker` service.

#### Production database (`HUMAN_INFRA_REQUIRED`)

The hosted database is at `20260907_20` while Railway runs main. Operator runbook
(`docs/cloud/supabase/SETUP.md`): pre-flight backup, export `DATABASE_URL_DIRECT` in the local
shell only, `uv run alembic upgrade head`, unset it, confirm `alembic current` is the head, then
let Railway restart. Run once, after the feature is built and merged, before the deploy restarts the
services; one run applies `20260903_18` through `20260912_25`. Set `AI_ENABLED=true` and a Groq
`AI_API_KEY` on both `api` and `worker` in the same step (TASKS #6). No code change: all missing revisions add
nullable columns or new tables.

#### Cleanup (P7, P12, P13, P14, P17)

| Change | Where |
|--------|-------|
| Prompt asks for English prose instead of Brazilian Portuguese; bump `AI_PROMPT_VERSION` | `services/ai/prompts.py` |
| Remove `AI_PROVIDER`; `provider` column value becomes the constant `"groq"` in the job code | `core/config.py`, `services/ai/factory.py`, `services/worker.py`, `tests/test_settings.py`, `backend/.env.example` |
| Remove the stale provider-credential comment | `backend/.env.example` |
| Remove branch-added explanatory docstrings | `services/ai/*.py`, `schemas/read.py` |
| Rewrite the AI roadmap to state this spec's decisions (merged feature + epic targets); chat, reports and Home summary are "not decided" | `docs/roadmap/AI.md`, `docs/roadmap/README.md` via `roadmap-sync` |

#### D6 — industrial UI on main's contract (F1)

`IndustrialServices.tsx`, `ScanIndustrialServices.tsx`, `HostDetail.tsx`, `industrialFixtures.ts`
and their tests use `IndustrialServiceView` (`schemas/read.py`). Rendering of `values`,
`value_min`, `value_max`, `nonzero_count` and `validations` is removed because the fields no
longer exist. Other copy changes are Epic E10.

#### D4 and DMI-160 — done

Import command removed (P10). Main's `20260912_20`…`20260912_23` are unchanged; `20260912_24`
(AI) and `20260912_25` (enrichment) extend main's head; `test_alembic_single_head.py` covers the
head. The D10 change needs no migration: the job table already allows `pending` without a
payload.

#### ADR-020

`docs/adr/ADR-020-ai-scan-analysis.md` records: Groq and `openai/gpt-oss-120b` as the merged
provider; the as-built context (including subnet, host IP and evidence) accepted while there are
no customers; `Explain this scan` as the only trigger, AI on for every organisation, no consent
record; failure never hides scan results; English output; `AI_API_KEY` handling (ADR-005). A
"Planned changes" section lists D1, D2, D3, D5, D8, D9 and the research assistant with links to
the epic issues.

### 2.2 Epic targets (not built in PR #144)

| Issue | Target | Main code areas |
|-------|--------|-----------------|
| E1 DMI-162 (D2) | Allow-listed public facts + request-local placeholders, local substitution, boundary tests | `services/ai/schemas.py`, `context.py`, `validation.py`, `read.py`, `tests/test_ai_context.py` |
| E2 DMI-163 (D1) | Replace `groq.py` with an OpenAI Responses adapter: `gpt-5.6-luna`, medium reasoning, strict `text.format`, `store=false`, no tools; refusal/incomplete → terminal; 400/401/403/404/422 terminal (P11) | `services/ai/openai_responses.py`, `factory.py`, `core/config.py` |
| E4 DMI-166 (D3) | Bounded child tasks, synthesizer on validated records, coverage | `services/ai/analyzer.py`, `jobs.py`, migration |
| E5 DMI-167 (D8) | Output validation, OWASP 2026 invisible-character stripping at ingest and render, computed priority bands, adversarial tests | `services/ai/context.py`, `validation.py`, `ScanAIAnalysis.tsx`, `tests/test_ai_injection.py` |
| E6 DMI-168 (D9) | Writing skill + linter + schema v2 | `services/ai/skills/`, `writing_lint.py`, `schemas.py`, contract |
| E7 DMI-164 (D5) | KEV/EPSS/NVD independent retries, NVD 403, sleep outside lock, `unknown` source outcomes (`last_error` truncation stays in DMI-120) | `services/nvd.py`, `kev.py`, `epss.py`, `enrichment.py`, `risk.py` |
| E8 DMI-165 (D5) | Refresh open scan page after late enrichment (F2) | `ScanDetail.tsx`, `FindingPanel.tsx` |
| E9 DMI-169 (D8 research) | Solution-finding research assistant with web search, ranked easiest first | new `services/ai/research*.py`, cache table |
| E10 DMI-170 (DESIGN) | Card placement, provenance caption, copy, priority labels | `ScanAIAnalysis.tsx`, `docs/ui/SCREENS.md` |

Each epic issue carries its own ARCHITECTURE detail when it is picked up; the TRUTH sections
"D3 context engineering", "D5 partial-enrichment behaviour" and "D8 prompt-injection
architecture" are their source.

---

## 3. Remediation plan per phase

### Phase 0 — Baseline

Record results in `TRUTH.md` (new "Baseline" section) for the working branch.

```bash
git switch feature/dmi-158-review-pr-144
git fetch origin && git merge-base --is-ancestor origin/main HEAD   # must exit 0
git rev-parse HEAD                                                  # record tested head
(cd backend && uv run alembic heads)                                # exactly one head
./database.sh --test                                                # record passed / skipped
(cd backend && uv run ruff check src tests)
(cd frontend && npm run gen:types && git diff --exit-code src/types/openapi.d.ts)
(cd frontend && npm run lint && npm run typecheck && npm test && npm run build)
```

Never run `ruff format`, `black .`, or root `./lint.sh`. Known before running: frontend
typecheck fails (F1).

### Phase 1 — Code review

Done; findings in `TRUTH.md` with PR or Epic scope.

### Phase 2 — Decisions

PR-scoped rows are decided. Linear: DMI-157 linked (D6); DMI-120 keeps `last_error` truncation; DMI-160 in this PR. Epic
DMI-161 with DMI-162…DMI-170 created 2026-09-13 (D11).

### Phase 3 — ADR and roadmap

Write ADR-020 per §2.1 (re-check the next free number on open branches). Run `roadmap-sync`.

### Phase 4 — Remediation

PR-scoped changes in §2.1 only. `/create-tasks` → `TASKS.md`. Backend code is formatted by hand.

### Phase 5 — Gates

Same commands as Phase 0. Pass = backend 0 failed / **0 skipped**, `ruff check` clean, one
Alembic head, `npm run gen:types` produces no diff, frontend lint/typecheck/test/build pass.

### Phase 6 — Docs sync

Run `docs-sync`:

| Target | What must be true |
|--------|-------------------|
| `.claude/docs/backend/services.md`, `routers.md`, `schemas.md`, `api.md` | AI package as merged, request route, `not_requested` status, settings without `AI_PROVIDER` |
| `.claude/docs/backend/models.md`, `migrations.md` | `ai_scan_analyses`, `next_attempt_at`, revisions `20260912_24` / `_25` |
| `.claude/docs/backend/management.md` | no import command |
| `.claude/docs/contracts.md`, frontend concept docs | analysis operations; `Explain this scan`; industrial components on `IndustrialServiceView` |
| `.claude/docs/log.md` | entry for this sync |
| `docs/DEV-SETUP.md` | every `AI_*`, `ENRICHMENT_*`, `NVD_MIN_REQUEST_INTERVAL_SECONDS` setting |
| `docs/roadmap/AI.md` (+ `README.md`) | this spec's decisions |
| `contracts/openapi/openapi.yaml` | via `openapi-contract-sync` |
| `docs/architecture/ARCHITECTURE.md`, `docs/README.md` | ADR-020 |
| `backend/README.md` | consistent with DEV-SETUP; no import section |

### Phase 7 — Merge readiness

PR description (no session URL): decisions with scope, ADR-020 and epic links, gate results,
"Fixes DMI-158", "Fixes DMI-160". Push the working branch to the PR head first.

---

## 4. Review checklist (PR #144)

- [ ] CLAUDE.md: no temporary code beyond what an epic issue owns; every changed line traces to a PR-scoped row or finding.
- [ ] Backend files not run through `ruff format`.
- [ ] No new test files where existing tests cover the behaviour.
- [ ] Alembic: one head; main's revisions unchanged.
- [ ] Contract first; `npm run gen:types` no diff; `test_contract_fidelity.py` lists the new operation.
- [ ] Backend suite on real `dmitri_test`, zero skips.
- [ ] Opening a completed scan starts no job and does not wait for AI.
- [ ] POST on a scan with a pending, processing or completed analysis returns 409; concurrent presses create one row.
- [ ] AI runs in its own loop; `run_worker_once` makes no provider call.
- [ ] Hosted database migrated to head before the deploy restarts services.
- [ ] No code path creates a job except `POST /scans/{id}/analysis`.
- [ ] AI off or blank key: no card, no provider built, no HTTP call.
- [ ] Failed job: results visible, button offered again, no partial analysis.
- [ ] Polling stops on terminal status and after 5 minutes.
- [ ] Prompt asks for English; `AI_PROVIDER` gone; docstrings removed.
- [ ] Frontend compiles against `IndustrialServiceView`; no process values rendered.

---

## 5. Files and naming (mandatory)

| Phase | Layer | Path | Driven by |
|-------|-------|------|-----------|
| 0–2, 7 | Spec | `specs/047-pr-144-review-remediation/TRUTH.md`, `ARCHITECTURE.md`, `DESIGN.md` | always |
| 2 | Spec | `specs/047-pr-144-review-remediation/WRITING-SKILL.md` | E6 source |
| 2 | Research | `docs/research/ai-scan-analysis-agent-web-research-and-trigger.md` | E5, E9 source |
| 4 | Spec | `specs/047-pr-144-review-remediation/TASKS.md` | `/create-tasks` |
| 3 | ADR | `docs/adr/ADR-020-ai-scan-analysis.md` | always |
| 3, 6 | Docs | `docs/roadmap/AI.md`, `docs/roadmap/README.md` | P17 |
| 6 | Docs | `docs/README.md`, `docs/DEV-SETUP.md`, `backend/README.md` | always |
| 6 | Code map | `.claude/docs/backend/{services,models,migrations,routers,schemas,api,management}.md`, `.claude/docs/contracts.md`, `.claude/docs/frontend/*` scan/host detail docs, `.claude/docs/log.md` | always |
| 4 | Router | `backend/src/api/routers/scans.py` | D10 |
| 4 | AI | `backend/src/api/services/ai/jobs.py`, `read.py`, `prompts.py`, `factory.py`, all `services/ai/*.py` (docstrings) | D10; P7, P12, P14 |
| 4 | Schemas | `backend/src/api/schemas/ai.py`, `schemas/read.py` (docstrings) | D10; P14 |
| 4 | Config | `backend/src/api/core/config.py`, `backend/.env.example` | P12, P13, D3 |
| 4 | Worker | `backend/src/api/services/worker.py`, new `backend/src/api/services/ai/worker.py`, `backend/src/api/worker_main.py` | D3; P6 |
| 7 | Infra | hosted Supabase database (`alembic upgrade head`) | production schema, `HUMAN_INFRA_REQUIRED` |
| 4 | Contract | `contracts/openapi/openapi.yaml` → `frontend/src/types/openapi.d.ts` (generated) | D10 |
| 4 | Frontend | `frontend/src/api/scans.ts`, `pages/scans/ScanAIAnalysis.tsx`, `test/mswHandlers.ts` | D10 |
| 4 | Frontend | `frontend/src/pages/hosts/IndustrialServices.tsx`, `pages/scans/ScanIndustrialServices.tsx`, `pages/HostDetail.tsx`, `test/industrialFixtures.ts` | D6; F1 |
| 4 | Backend tests (existing) | `test_ai_jobs.py`, `test_ai_analysis_read.py`, `test_worker_sweep.py`, `test_settings.py`, `test_contract_fidelity.py`, `test_health.py` | D10; P12 |
| 4 | Frontend tests (existing) | `ScanAIAnalysis.test.tsx`, `ScanDetail.test.tsx`, `IndustrialServices.test.tsx`, `HostDetail.test.tsx` | D10; F1 |
| — | Hardware agent | none | not touched |

---

## 6. Constraints

- No PR #144 change for an Epic-scoped row.
- Never `ruff format` / `black .` / root `./lint.sh`; backend gate is `ruff check` only.
- Backend suite only via `./database.sh --test` with 0 skipped; DB name exactly `dmitri_test`.
- Do not rewrite a revision that ran on a shared database; confirm with the teammate that the old PR head never ran on a shared Supabase instance, otherwise `HUMAN_INFRA_REQUIRED` (stamp).
- `openapi.d.ts` is generated from `openapi.yaml`; the contract is edited first.
- No live provider calls in tests; `GroqProvider` gets an injected `httpx.Client` / `MockTransport`.
- Hosted `AI_API_KEY` is set by a human in Railway (`HUMAN_INFRA_REQUIRED`).
- Out of scope: Epic-scoped rows, chat, reports, Home AI summary, Pi agent changes, unrelated formatting.

## 7. Testing expectations (PR #144)

Extend existing tests; add no new test files.

### Backend (`backend/tests/`, real DB)

| Area | Test | File |
|------|------|------|
| Request creates one job | POST on a completed scan → 202 and one `pending` row; second POST → 409, no change; POST after `completed` → 409; foreign scan → 404; AI off → `unavailable`, no row | `test_ai_analysis_read.py` |
| Retry after failure | POST on a `failed` row → `pending`, `attempts=0` | `test_ai_jobs.py` |
| No automatic jobs, AI outside enrichment | `run_worker_once` never builds a provider; `run_ai_worker_once` processes only requested rows | `test_worker_sweep.py`, `test_ai_jobs.py` |
| Read status | no row → `not_requested` | `test_ai_analysis_read.py` |
| Settings | no `AI_PROVIDER` | `test_settings.py` |
| Contract | new operation published | `test_contract_fidelity.py`, `test_health.py` |

### Frontend (Vitest + Testing Library + MSW)

| Scenario | File |
|----------|------|
| `not_requested` → `Explain this scan` button; findings render | `ScanAIAnalysis.test.tsx` |
| Press button → POST sent → pending → completed; polling stops | `ScanAIAnalysis.test.tsx` |
| `failed` → failed text and the button again | `ScanAIAnalysis.test.tsx` |
| `pending`/`processing`/`completed` → no button; 409 on press → status refetched | `ScanAIAnalysis.test.tsx` |
| `unavailable` → no card | `ScanAIAnalysis.test.tsx` |
| Scan page renders findings with the analysis request never resolving | `ScanDetail.test.tsx` |
| Industrial fixtures on `IndustrialServiceView` | `IndustrialServices.test.tsx`, `HostDetail.test.tsx` |

Gate: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, plus `npm run gen:types`
with no diff.
