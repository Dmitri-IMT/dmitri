# ARCHITECTURE — Review and remediate PR #144

Linear: DMI-158 · Source of truth: [`TRUTH.md`](TRUTH.md) · Branch: `feature/ia-implementation`
(head `7997383`) · PR: #144 · Read against: `main` at `1c14653` (2026-09-12).

This is a review/remediation spec, not a new feature. It maps what PR #144 built, where each
decision D1–D7 lands in the code, and how phases 0–7 run. It decides nothing.

**Hardware agent: not touched.** PR #144 changes no file under `hardware-agent/`. The template
sections on `ScanRunner` (`hardware-agent/src/agent/scanner/runner.py`) and `ScanProgressScreen`
(`hardware-agent/src/agent/tui/screens/scan_progress.py`) do not apply: no orchestrator or runner
parameter changes. The CLAUDE.md integration rule is applied here to the backend call paths that
do change (worker loop, `NvdClient`, `ingest_scan`), see §4.

---

## 1. System context (as built)

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

## 2. Decision points (D1–D7)

Each row names the code a decision touches and what changes. "Keep" = as built.

### D1 — LLM provider and model

Touches: `core/config.py:25-46`, `.env.example`, `services/ai/factory.py`, `services/ai/groq.py`,
`services/ai/prompts.py`, `tests/test_ai_groq.py`, `tests/test_settings.py`,
`docs/roadmap/AI.md`, `backend/README.md`, the new AI ADR.

| Option | Consequence |
|--------|-------------|
| Keep Groq + `openai/gpt-oss-120b` | No code change. ADR must record the choice against the old roadmap line ("default to the latest capable Claude model", `main:docs/roadmap/AI.md:37`), Groq's data retention/training terms, and the region. Roadmap keeps the Groq text. |
| Switch to Claude | New adapter `services/ai/anthropic.py` (or SDK dependency in `pyproject.toml` — ADR-003 stack impact), `factory.py` returns it, `AI_PROVIDER` Literal and `AI_MODEL`/`AI_API_BASE_URL` defaults change, `AI_REASONING_EFFORT` and `include_reasoning` have no direct equivalent, structured output mechanism changes (tool/JSON schema), `test_ai_groq.py` replaced, `groq.py` removed. Existing `ai_scan_analyses.provider` rows stay valid (free text). |
| Provider-neutral, one default | `AI_PROVIDER` becomes a real switch in `factory.py` (today ignored); one adapter per provider; one contract test per adapter against the same `ScanAIAnalysis` schema. Adds a second adapter now — check "no speculative flexibility" (CLAUDE.md §2) and require a named second provider. |

### D2 — Data sent to the provider; organisation opt-out

`services/ai/context.py` builds `ScanAIContext`; `groq.py:43` sends `context.model_dump_json()`
verbatim inside the user prompt, plus the static system prompt and the JSON schema.

Fields sent, per scan (`ScanAIContext`):

| Field | Source | Sensitivity note |
|-------|--------|------------------|
| `context_version` | constant `"1"` | none |
| `scan_id` | `get_scan_detail` | internal UUID |
| `timestamp` | scan | when the network was scanned |
| `subnet` | scan | **customer network range** |
| `scan_mode` | scan | quick/standard/extensive/nspi/max |
| `duration_seconds` | scan | none |
| `host_count` | scan | network size |
| `total_findings`, `scored_findings`, `confirmed_findings`, `kev_findings` | `get_scan_risk_summary` | counts |
| `average_risk_score`, `max_risk_score` | risk summary | scores |
| `severity` | `SeverityBreakdown` (critical/high/medium/low counts) | counts |
| `top_findings[]` | up to `AI_MAX_FINDINGS` (default 10, hard max 15) ranked findings | see below |

Fields sent per finding (`AIFindingContext`):

| Field | Bound | Sensitivity note |
|-------|-------|------------------|
| `finding_id`, `host_id` | UUID | internal ids |
| `host_ip` | IPv4 | **customer host address** |
| `port`, `protocol`, `service` | — | exposed service map |
| `cve_id`, `cvss_score`, `severity`, `confidence`, `risk_score`, `exploitability` | — | vulnerability posture |
| `epss_score`, `epss_percentile`, `is_kev`, `known_ransomware` | from `EpssRecord` / `KevRecord` | public intel joined to host |
| `title` | 500 chars | scanner text |
| `description` | 4000 chars | scanner text |
| `recommendation` | 2000 chars | scanner text |
| `evidence` | 4000 chars | **raw NSE/scanner output — may carry banners, versions, hostnames, share or account names** |
| `references` | 10 × 2000 chars | URLs |

Not sent: org id/name, user data, agent id, hostnames, MAC, vendor, operating system,
open-port list beyond the top findings, industrial services / Modbus data, ports without
findings.

Scope of sending: `jobs.py:enqueue_ready_ai_analyses` selects **every completed scan of every
org** that has no analysis row. The only switch is the deployment-wide `AI_ENABLED` +
`AI_API_KEY`. Turning AI on also back-fills all historical scans.

| Option | Consequence |
|--------|-------------|
| Full context as built | No code change. ADR lists the tables above as the boundary and records the back-fill behaviour. The D2 boundary test (§6) still has to be added to pin the field set. |
| Reduced / anonymised | `context.py` and `schemas.py` change (e.g. drop or tokenise `subnet`, `host_ip`; drop or redact `evidence`; lower clip limits). If ids are tokenised, `validation.py` and the frontend finding-title lookup (`ScanAIAnalysis.tsx` `findingTitles`) must map back. `AI_CONTEXT_VERSION` → `"2"`; `test_ai_context.py` updated. |
| Off by default per org, explicit opt-in | New org-level flag: model field on `Org` (`backend/src/api/models/identity.py`) + new Alembic revision; `enqueue_ready_ai_analyses` filters by it; `services/ai/read.py` returns `unavailable` for non-opted orgs; admin surface to toggle (new route + contract + Settings UI) — that is a new feature, so check TRUTH "Out of scope" and likely ticket the UI. Decide whether opt-in back-fills old scans. |

### D3 — AI job execution and retries

Touches: `services/ai/jobs.py`, `services/worker.py:70-82`, `ai_scan_analyses` columns
(`status`, `attempts`, `started_at`, `last_error_code`), `tests/test_ai_jobs.py`,
`tests/test_worker_sweep.py`.

Fact: the AI flow already runs **inside** the existing worker loop, but with its own table and its
own claim/stale/exhaust state machine that duplicates the one Part 3 adds to
`enrichment.py:24`. Provider calls are synchronous: one loop iteration can block for
`batch_size × AI_TIMEOUT_SECONDS` (default 10 × 30 s) before enrichment runs again.

| Option | Consequence |
|--------|-------------|
| Keep as built | No change. Review must accept the duplicated claim logic and the blocking cost; ADR states it. |
| Fold into enrichment job model | AI becomes a job kind in `enrichment_jobs` (or a shared claim helper used by both). Removes `claim_ai_analyses` / `_handle_attempt_error`; `ai_scan_analyses` keeps only result columns; migration `20260912_21` changes shape (allowed only while unreleased); `AI_MAX_ATTEMPTS`/`AI_RETRY_DELAY_SECONDS` may merge with `ENRICHMENT_*`. Couples to D5. |
| Keep separate flow, bound its cost | Only worker-side limits (e.g. AI batch of 1 per iteration). Smaller diff; does not remove duplication. |

### D4 — Local scan import

Touches: `backend/src/api/management/import_scan.py`, `backend/pyproject.toml` scripts,
`tests/test_import_scan.py`, `tests/test_migrations.py:221-226`, `backend/README.md`,
`docs/DEV-SETUP.md`, `.claude/docs/backend/management.md`.

| Option | Consequence |
|--------|-------------|
| Supported command | Document in `docs/DEV-SETUP.md` and code map; decide the `--org-id` phantom agent (a real `agents` row with an unusable key that appears in agent reads) — keep, or require `--agent-id` only; ADR-005 check: bypasses Ed25519 ingest auth by design (operator has DB access). |
| Dev-only tool | Keep code; document only in `docs/DEV-SETUP.md` as dev tooling; consider moving out of `[project.scripts]` (then `test_migrations.py` script set reverts). |
| Remove | Delete `import_scan.py`, `test_import_scan.py`, the `pyproject.toml` line, the `test_migrations.py` entry and the README section; open a Linear issue. |

### D5 — Enrichment retry design vs DMI-120

DMI-120 (Backlog) asks to truncate `last_error` and stop trusting client `X-Request-Id`.
Part 3 adds coded `last_error` values for NVD temporary errors, but the generic branch
(`enrichment.py:145`) still stores `str(exc)` unbounded; `X-Request-Id` is untouched.

Touches: `services/enrichment.py`, `services/nvd.py`, `services/worker.py`, `core/config.py`,
migration `20260912_22`, `tests/test_enrichment_retries.py`, `tests/test_nvd_resilience.py`.

| Option | Consequence |
|--------|-------------|
| Accept; rescope DMI-120 | No Part 3 code change; DMI-120 keeps both items (truncation not done here). |
| Accept with changes | e.g. truncate `last_error` in `enrichment.py:145` (then DMI-120 rescoped to `X-Request-Id` only); pass settings explicitly instead of `get_settings()` inside `claim_pending_enrichment_jobs`; do not sleep while holding the lock; treat NVD 403 rate-limit replies. Each is a Phase 1 finding to accept or reject. |
| Defer | Remove `20260912_22`, the `NvdTemporaryError` path, `next_attempt_at`, the three `ENRICHMENT_*` and `NVD_MIN_REQUEST_INTERVAL_SECONDS` settings, and the two test files; AI enqueue then depends on the old enrichment behaviour; new issue. |

### D6 — Industrial services vs DMI-142 / DMI-157

DMI-157 (In Progress, PR #145, branch `origin/feat/dmi-157-harden-active-ot-scans`) persists
industrial observations with a **different design**: tables `industrial_services` and
`modbus_units`, `findings.modbus_unit_id`, `orgs.ot_digest_key` (revision `20260912_22`), moves
Modbus payloads to `schemas/industrial.py`, and requires "no raw values, no min/max/nonzero, no
validation payload" on wire, DB and read APIs. Part 1 stores and serves the full
`ModbusTcpServicePayload` as JSON, and `IndustrialServices.tsx` renders `value_min`/`value_max`.
Both change `persistence.py`, `schemas/read.py`, `services/read.py`, `openapi.yaml`,
`openapi.d.ts`, `ScanDetail.test.tsx`, `mswHandlers.ts`.

Risk context (`risk-summary`, `findings/{id}`, `FindingRead` risk fields) does not overlap with
DMI-157 and is a dependency of Part 2 (`context.py` calls `get_scan_risk_summary`).

| Option | Consequence |
|--------|-------------|
| PR #144 wins | PR #145 must drop its persistence half and adopt JSON columns; DMI-157's "no process values" rule is broken unless Part 1 strips values; DMI-142 closed by #144. |
| DMI-157 wins | Remove from #144: migration `20260911_20`, both `industrial_services_json` model fields, `persistence.py:294`, `hosts.py:64/94`, `industrial_services` on read schemas and `_to_industrial_services`, `IndustrialServices.tsx`, `ScanIndustrialServices.tsx`, `industrialFixtures.ts`, their tests and contract entries. Keep the risk-context half. DMI-142 closed by #145. |
| Merge both | Keep #144 read surfaces but back them with #145 tables and its value-free schema; requires sequencing (#145 first) and a rebase of #144 onto it. |

### D7 — One PR or split

| Option | Consequence |
|--------|-------------|
| One PR | Phases 4–7 on `feature/ia-implementation`. One migration chain to re-order. Review load stays at 73 files. |
| Split into four | Order forced by dependencies: Part 1 risk-context → Part 3 → Part 2 (needs risk summary and terminal enrichment) → Part 4 (independent). Each PR gets its own revision chain, contract diff, and `openapi.d.ts` regeneration. New branch names per Linear issue. |
| AI apart from the rest | PR A: Parts 1 (per D6), 3, 4 + migrations `20260911_20`, `20260912_22`. PR B: Part 2 + `20260912_21` re-chained after PR A. The AI ADR gates PR B only. |

---

## 3. Remediation plan per phase

### Phase 0 — Baseline

Record results in `TRUTH.md` (new "Baseline" section) for **two** points: the current head
`7997383` and the rebased branch.

```bash
# point A: as-is
git switch feature/ia-implementation && git rev-parse HEAD      # expect 7997383
./database.sh --test                                             # record passed / skipped
(cd backend && uv run ruff check src tests)
(cd frontend && npm run lint && npm run typecheck && npm test && npm run build)

# point B: rebased (coordinate with the teammate: this rewrites a shared branch)
git fetch origin
git rebase origin/main
(cd backend && uv run alembic heads)                             # must print exactly one head
./database.sh --test
(cd backend && uv run ruff check src tests)
(cd frontend && npm run gen:types && git diff --exit-code src/types/openapi.d.ts)
(cd frontend && npm run lint && npm run typecheck && npm test && npm run build)
```

Never run `ruff format`, `black .`, or root `./lint.sh`. A backend result with non-zero skips is
recorded as "not green".

Expected rebase conflicts (from `git diff --stat 08c1284 main`): `backend/src/api/models/persistence.py`,
`schemas/read.py`, `services/read.py`, `services/persistence.py`, `services/enrichment.py`,
`services/home.py`, `tests/conftest.py`, `tests/test_migrations.py`, `tests/test_read_findings.py`,
`tests/test_read_hosts.py`, `tests/test_ingest_scan.py`, `frontend/src/pages/ScanDetail.tsx`,
`ScanDetail.test.tsx`, `src/test/mswHandlers.ts`, `src/types/openapi.d.ts` (regenerate, do not
hand-merge), `contracts/openapi/openapi.yaml`.

**Alembic blocker on rebase:** `main` already has revision id `20260912_21`
(`20260912_21_merge_inventory_and_os.py`, merges `20260907_20` + `20260908_19`). The branch's
`20260912_21_ai_scan_analyses.py` reuses that id, and `20260911_20` re-merges `20260908_19`.
Conflict resolution in Phase 0 is limited to: give the three branch revisions unused ids and
chain them linearly after `main`'s head (`20260911_20` → down `20260912_21`). Also check
PR #145's ids (`20260912_20`, `20260912_22`, `20260912_23`) — `20260912_22` collides with the
branch's enrichment revision. Record any semantic conflict as a Phase 1 finding; do not fix it
in Phase 0.

**Spec number:** `main` has `specs/046-machine-inventory-depth/`, so this spec was renumbered to
`047` (next free on `main`). Re-check after rebase.

### Phase 1 — Code review

Run one review per part, scoped by paths, and write findings into `TRUTH.md` ("Findings" table:
id, severity, part, `path:line`, description, proposed action).

| Part | Review scope |
|------|--------------|
| 1 | `alembic/versions/*industrial_services*`, `models/persistence.py` (industrial fields), `services/persistence.py`, `services/hosts.py`, `services/read.py`, `services/home.py`, `schemas/read.py`, `routers/findings.py`, `routers/scans.py` (risk-summary), `frontend/src/pages/hosts/IndustrialServices*`, `pages/scans/ScanIndustrialServices.tsx`, `pages/scans/FindingPanel*`, `pages/HostDetail*`, `test/industrialFixtures.ts`, related tests, `tests/conftest.py` |
| 2 | `services/ai/**`, `schemas/ai.py`, `alembic/versions/*ai_scan_analyses*`, `models/persistence.py` (`AIScanAnalysisRecord`), `core/config.py` AI_*, `.env.example`, `routers/scans.py` (analysis), `services/worker.py`, `frontend/src/api/scans.ts`, `api/queryKeys.ts`, `pages/scans/ScanAIAnalysis*`, `pages/ScanDetail*`, `test/mswHandlers.ts`, `tests/test_ai_*.py`, `docs/roadmap/AI.md` |
| 3 | `services/enrichment.py`, `services/nvd.py`, `services/worker.py`, `alembic/versions/*enrichment_retries*`, `core/config.py` ENRICHMENT_*/NVD_*, `tests/test_enrichment_retries.py`, `tests/test_nvd_resilience.py`, `tests/test_worker_sweep.py` |
| 4 | `management/import_scan.py`, `pyproject.toml`, `tests/test_import_scan.py`, `backend/README.md` |
| All | `contracts/openapi/openapi.yaml`, `frontend/src/types/openapi.d.ts`, `tests/test_contract_fidelity.py`, `tests/test_health.py` |

Useful tools: `/code-review high` on the rebased branch, `/security-review` for Part 2 and Part 4,
`gh-adr-change-tracker` against ADR-005 / ADR-009 / ADR-018.

### Phase 2 — Decisions

Fill the `TRUTH.md` decision log (option, reason, maintainer, date) using §2. Update Linear:
DMI-142, DMI-157 (D6), DMI-120 (D5). Deferred/removed parts → new issues via `create-issue`.

### Phase 3 — ADRs

AI ADR path: **`docs/adr/ADR-020-ai-scan-analysis.md`**. `ADR-019` is free on `main` and on this
branch, but open PR #145 adds `docs/adr/ADR-019-v2-active-scanning-and-agent-hardening.md` and
DMI-157 cites it as Accepted. Before writing, re-run:

```bash
git fetch origin
for b in origin/main $(git branch -r --format='%(refname:short)'); do git ls-tree --name-only $b docs/adr/; done | sort -u | tail -3
```

and take the next number not used on any open branch.

Required ADR sections (match `ADR-018` layout: Status, Context, Decision, Consequences, Rejected
alternatives, References), with Decision covering:

1. Provider and model policy (D1): named provider, default model, who may change `AI_MODEL`, retention/training terms.
2. Data boundary (D2): exact field list sent (§2 D2 tables), fields never sent, clip limits, back-fill rule.
3. Opt-in / opt-out rule (D2): deployment flag and org-level rule.
4. Execution and retry (D3): where jobs run, attempt budget, stale handling.
5. Failure behaviour: AI off / not configured / failed never hides scan results; no partial analysis shown.
6. Grounding: context-only prompt, strict JSON schema, finding-id validation (`validation.py`), `context_hash`, versions.
7. Output language (Portuguese prompt vs English UI).
8. Secret handling for `AI_API_KEY` (ADR-005 alignment).

Other ADRs only if a decision requires one (e.g. D6 "merge both" changing ADR-009 persistence
shape). Then run `roadmap-sync` so `docs/roadmap/AI.md` states the same provider and boundary as
the ADR and does not contradict `docs/roadmap/SECURITY.md`; remove roadmap text for features
out of scope (chat, reports, Home summary) or mark them as not decided.

### Phase 4 — Remediation

Only for parts with a recorded decision. Every change maps to a finding id or decision id.
Per-task work goes through `/create-tasks` → `TASKS.md`. Backend code is formatted by hand.

### Phase 5 — Gates

Same commands as Phase 0 point B. Pass = backend 0 failed / **0 skipped**, `ruff check` clean,
one Alembic head, `npm run gen:types` produces no diff, frontend lint/typecheck/test/build pass,
`test_contract_fidelity.py` passes.

### Phase 6 — Docs sync

Run `docs-sync`, which covers and delegates:

| Target | What must be true |
|--------|-------------------|
| `.claude/docs/backend/services.md` | AI services package, enrichment retry/claim, NVD spacing |
| `.claude/docs/backend/models.md`, `migrations.md` | `AIScanAnalysisRecord`, `industrial_services_json` (per D6), `next_attempt_at`, new revision ids |
| `.claude/docs/backend/routers.md`, `schemas.md`, `api.md` | new routes, `schemas/ai.py`, AI/ENRICHMENT/NVD settings, worker wiring |
| `.claude/docs/backend/management.md` | `backend-import-scan` (per D4) |
| `.claude/docs/contracts.md`, frontend concept docs | new operations; `ScanAIAnalysis`, industrial components |
| `.claude/docs/log.md` | entry for this sync |
| `docs/DEV-SETUP.md` | every new `AI_*`, `ENRICHMENT_*`, `NVD_MIN_REQUEST_INTERVAL_SECONDS` setting; import command (per D4) |
| `docs/roadmap/AI.md` (+ `README.md`) | via `roadmap-sync`, aligned to the ADR |
| `contracts/openapi/openapi.yaml` | via `openapi-contract-sync` |
| `docs/architecture/ARCHITECTURE.md`, ADRs | via `architecture-adr-sync` |
| `docs/README.md` | new "Decisions" row for the AI ADR. (Rows for ADR-013…018 are also missing today — report, do not fix unless docs-sync owns it.) |
| `backend/README.md` | consistent with DEV-SETUP; no stale text |

### Phase 7 — Merge readiness

PR description (no session URL): decisions D1–D7 with one line each, ADR link(s), findings
closed/ticketed, gate results, "Fixes DMI-158". Close or rescope DMI-142, DMI-157, DMI-120 per
D5/D6. If D7 splits the PR, each PR carries its own "Fixes" line and links DMI-158.

---

## 4. Review checklist per part

### All parts

- [ ] CLAUDE.md: no temporary code or stopgap; every changed line traces to the part's purpose; no unrelated edits.
- [ ] Backend files were not run through `ruff format` (diff shows no mass reflow of untouched lines).
- [ ] Style: no new comments/docstrings (repo convention) — PR adds docstrings in `services/ai/*.py`, `schemas/read.py`.
- [ ] Alembic: exactly one head after rebase; no duplicate revision id vs `main` and vs PR #145; each `downgrade()` reverses `upgrade()`; upgrade from empty and from `main`'s head both run (`test_migrations.py`).
- [ ] Contract fidelity: every new route in `openapi.yaml` with matching `operationId`, security, responses; `npm run gen:types` gives no diff; `test_contract_fidelity.py` `SCHEMA_NAMES` covers new schemas (today it lists the AI schemas but not `ScanRiskSummaryResponse` / `SeverityBreakdown` — confirm).
- [ ] Tests run against the real `dmitri_test` DB with zero skips.
- [ ] Every constructor/call site of changed functions accounted for (CLAUDE.md integration rule):
      `run_worker_once` (worker loop, `test_worker_sweep.py`), `claim_pending_enrichment_jobs` / `process_pending_enrichment_jobs` (worker, tests), `NvdClient()` (worker, `enrichment.py` default path), `ingest_scan` (`routers/scans.py`, `import_scan.py`), `_to_finding_read` → `findings_with_risk` (`read.py`, `home.py`), `get_scan_risk_summary` (router, `ai/context.py`).

### Part 1

- [ ] Migration `20260911_20` re-chained; not a second merge of `20260908_19`.
- [ ] Industrial JSON exposes process values (`values`, `value_min`, `value_max`, `validations`) — conflicts with DMI-157; resolved by D6.
- [ ] `hosts.py:94` never clears industrial services when a later scan finds none — intended?
- [ ] Merge with `main`'s DMI-139 shared finding query (`9f9e57a`) keeps one read path.

### Part 2

- [ ] AI failure never hides scan results: `ScanAIAnalysis` is a sibling card; errors/`failed`/`unavailable` do not affect findings, hosts, or the page state; `/analysis` 5xx does not break `ScanDetail`.
- [ ] AI off: `/analysis` returns `unavailable`; worker builds no provider (`build_ai_provider` → `None`); no HTTP call.
- [ ] `get_scan_ai_analysis` returns `pending` for a completed scan even when the job will never run (e.g. scan without `org_id`) and for `processing`/`accepted` scans — check UI never polls forever.
- [ ] `ScanAIAnalysis.model_validate(record.analysis_json)` in `ai/read.py` raises on stored payloads from an older schema → 500.
- [ ] `AI_API_KEY`: `SecretStr`; only unwrapped in `factory.py` and the `Authorization` header; not logged (`jobs.py` logs `scan_id` only; `AIProviderError` carries codes, not bodies); redaction covered by `test_settings.py`.
- [ ] Prompt-injection: context strings are untrusted; output limited by schema + id validation. Free text (`evidence_used`, summaries) is not validated against context.
- [ ] Error mapping: 400/422 → retryable `invalid_provider_response` (a request bug retries).
- [ ] Back-fill and cross-org sending on first enable (D2).
- [ ] RLS/grants on `ai_scan_analyses` match other runtime tables (no DELETE grant; cascade from `scans`).
- [ ] Model/migration drift: model FK has no `ondelete="CASCADE"`; migration does.

### Part 3

- [ ] `last_error = str(exc)` still unbounded (`enrichment.py:145`) — DMI-120.
- [ ] `get_settings()` read inside `claim_pending_enrichment_jobs` and the exception path (hidden dependency; tests must override settings).
- [ ] `time.sleep` inside the lock (`nvd.py:60`) stalls the whole worker loop (enrichment + AI) for up to 6 s per uncached call.
- [ ] Exhausted-stale update runs without `SKIP LOCKED` (two workers).
- [ ] NVD 403 rate-limit replies fall to `raise_for_status` → permanent `failed`.
- [ ] Retried job re-runs KEV/EPSS parts idempotently.

### Part 4

- [ ] Phantom `Local JSON importer` agent: appears in `GET /api/v1/agents`? Can it be revoked/deleted? Is it counted as an offline device?
- [ ] `--agent-id` path does not require an org match to anything — acceptable for an operator tool?
- [ ] Idempotency relies on `ingest_scan` scan_id rules (`ScanClosedError`, `ScanOwnershipError`).
- [ ] Documented in the place D4 selects; README examples use Windows paths only.

### Preliminary observations (to confirm in Phase 1)

| # | Sev. | Part | Location | Observation |
|---|------|------|----------|-------------|
| P1 | Blocker | 1–3 | `alembic/versions/20260912_21_ai_scan_analyses.py` vs `main:…/20260912_21_merge_inventory_and_os.py` | Duplicate revision id `20260912_21` after rebase; branch is not on current `main`. |
| P2 | Blocker | 3 | `20260912_22_enrichment_retries.py` vs PR #145 `20260912_22_industrial_observations.py` | Second id collision with the open DMI-157 PR. |
| P3 | High | 1 | `schemas/read.py` (`industrial_services`), `IndustrialServices.tsx:41` | Serves and renders Modbus process values; DMI-157 forbids raw values/min/max on read APIs. |
| P4 | High | 2 | `services/ai/jobs.py:enqueue_ready_ai_analyses` | Enabling AI sends every org's completed scans (including history) to Groq; no org-level control. |
| P5 | High | 2 | `services/ai/context.py:86` | Raw `evidence` (up to 4000 chars per finding), `subnet` and `host_ip` leave the product. |
| P6 | Medium | 2/3 | `services/worker.py:70-82`, `services/nvd.py:60` | Synchronous provider calls and lock-held sleeps share one loop; AI can delay enrichment by minutes. |
| P7 | Medium | 2 | `services/ai/prompts.py:11` | Analysis prose is Portuguese; the web UI copy is English. |
| P8 | Medium | 2 | `services/ai/read.py:56` | `pending` returned for scans no job will pick up → endless 3 s polling in `ScanAIAnalysis.tsx`. |
| P9 | Medium | 3 | `services/enrichment.py:145` | Untruncated `last_error` remains (DMI-120). |
| P10 | Medium | 4 | `management/import_scan.py:81-90` | Creates a real agent row with a discarded private key. |
| P11 | Low | 2 | `services/ai/groq.py:103` | HTTP 400/422 treated as retryable. |
| P12 | Low | 2 | `services/ai/factory.py` | `AI_PROVIDER` setting is never read. |
| P13 | Low | 2 | `backend/.env.example` | Comment "Provider credentials are added only with the provider." is stale. |
| P14 | Low | all | `services/ai/*.py`, `schemas/read.py` | Docstrings in new code (repo style: none). |
| P15 | Low | docs | `specs/047-*` | Resolved: spec renumbered from `046` to `047` (`046-machine-inventory-depth` exists on `main`). |
| P16 | Low | docs | `docs/adr/` | `ADR-019` claimed by PR #145; AI ADR must be `ADR-020` or later. |
| P17 | Info | docs | `docs/roadmap/AI.md` | Rewritten to match code (Groq, chat, reports, Home) with no ADR; contradicts `main` roadmap line 37. |
| P18 | Info | tests | `backend/tests/test_ai_context.py` | No test pins the exact field set sent to the provider. |

---

## 5. New files and naming (mandatory)

Phase = when touched. Condition = decision outcome that makes the change happen ("always" when
unconditional).

| Phase | Layer | Path | Condition / notes |
|-------|-------|------|-------------------|
| 0–2, 7 | Spec | `specs/047-pr-144-review-remediation/TRUTH.md` | always — baseline, findings, decision log |
| 1 | Spec | `specs/047-pr-144-review-remediation/ARCHITECTURE.md` | this file; update if findings change the plan |
| 4 | Spec | `specs/047-pr-144-review-remediation/TASKS.md` | always — via `/create-tasks` |
| 4 | Spec | `specs/047-pr-144-review-remediation/DESIGN.md` | only if a decision changes a web screen (D2 opt-in UI, D6 removal) |
| 0 | Spec | `specs/0NN-pr-144-review-remediation/` (rename) | if maintainer confirms renumbering (P15) |
| 3 | ADR | `docs/adr/ADR-020-ai-scan-analysis.md` | always; number re-verified (P16) |
| 3 | ADR | `docs/adr/ADR-009-database-stack.md` / new ADR | only if D6 "merge both" changes persistence design |
| 3, 6 | Docs | `docs/roadmap/AI.md`, `docs/roadmap/README.md` | always — align to ADR via `roadmap-sync` |
| 3 | Docs | `docs/roadmap/SECURITY.md` | if roadmap-sync finds a contradiction |
| 6 | Docs | `docs/README.md` | always — ADR index row |
| 6 | Docs | `docs/DEV-SETUP.md` | always — new settings; import command per D4 |
| 6 | Docs | `docs/implementation/INTELLIGENCE-IA-ASSESSMENT-ROADMAP.md` | if its three added lines drift from the decisions |
| 6 | Docs | `backend/README.md` | always — consistent with DEV-SETUP and decisions |
| 6 | Code map | `.claude/docs/backend/services.md`, `models.md`, `migrations.md`, `routers.md`, `schemas.md`, `api.md`, `management.md`, `.claude/docs/contracts.md`, `.claude/docs/log.md` | always (management.md per D4) |
| 6 | Code map | `.claude/docs/frontend/host-detail.md` and the scan-detail concept doc under `.claude/docs/frontend/` | always — `ScanAIAnalysis`, industrial components per D6 |
| 0, 4 | Migration | `backend/alembic/versions/20260911_20_industrial_services_inventory.py` | always re-chained/renamed (P1); removed if D6 = DMI-157 wins |
| 0, 4 | Migration | `backend/alembic/versions/20260912_21_ai_scan_analyses.py` | always re-id'd (P1); reshaped if D3 = fold; removed if Part 2 removed |
| 0, 4 | Migration | `backend/alembic/versions/20260912_22_enrichment_retries.py` | always re-id'd (P2); removed if D5 = defer |
| 4 | Migration | `backend/alembic/versions/<new>_org_ai_opt_in.py` | only if D2 = per-org opt-in |
| 4 | Config | `backend/src/api/core/config.py`, `backend/.env.example` | D1 (provider/model defaults), D3 (merged retry settings), D5 defer; P13 |
| 4 | Models | `backend/src/api/models/persistence.py` | D3, D5, D6 |
| 4 | Models | `backend/src/api/models/identity.py` | only if D2 = per-org opt-in |
| 4 | AI | `backend/src/api/services/ai/context.py`, `schemas.py` | D2 reduced/anonymised |
| 4 | AI | `backend/src/api/services/ai/validation.py` | D2 if ids are tokenised |
| 4 | AI | `backend/src/api/services/ai/factory.py`, `groq.py`, `prompts.py` | D1; P7, P11, P12 |
| 4 | AI | `backend/src/api/services/ai/anthropic.py` | only if D1 = Claude or provider-neutral with Claude |
| 4 | AI | `backend/src/api/services/ai/jobs.py`, `read.py`, `backend/src/api/schemas/ai.py` | D2 opt-in, D3; P8 |
| 4 | Worker | `backend/src/api/services/worker.py` | D3, D5; P6 |
| 4 | Enrichment | `backend/src/api/services/enrichment.py`, `backend/src/api/services/nvd.py` | D5; P9 |
| 4 | Ingest/read | `backend/src/api/services/persistence.py`, `services/hosts.py`, `services/read.py`, `services/home.py`, `schemas/read.py` | D6; rebase conflicts |
| 4 | Routers | `backend/src/api/routers/scans.py`, `routers/findings.py` | D6, D7 split; D2 opt-in route |
| 4 | Management | `backend/src/api/management/import_scan.py`, `backend/pyproject.toml` | D4; P10 |
| 4 | Contract | `contracts/openapi/openapi.yaml` | any route/schema change |
| 4 | Frontend | `frontend/src/types/openapi.d.ts` | regenerated via `npm run gen:types`, never hand-edited |
| 4 | Frontend | `frontend/src/pages/scans/ScanAIAnalysis.tsx`, `pages/ScanDetail.tsx`, `api/scans.ts`, `api/queryKeys.ts`, `test/mswHandlers.ts` | D2 id mapping / opt-in; P8; Part 2 removal |
| 4 | Frontend | `frontend/src/pages/hosts/IndustrialServices.tsx`, `pages/scans/ScanIndustrialServices.tsx`, `pages/HostDetail.tsx`, `test/industrialFixtures.ts` | D6 |
| 4 | Backend tests | `backend/tests/test_ai_context.py` | always — add D2 boundary test |
| 4 | Backend tests | `backend/tests/test_worker_sweep.py` | always — AI-disabled makes no provider call |
| 4 | Backend tests | `backend/tests/test_ai_jobs.py`, `test_ai_groq.py`, `test_ai_analysis_read.py`, `test_settings.py` | D1, D2, D3 |
| 4 | Backend tests | `backend/tests/test_enrichment_retries.py`, `test_nvd_resilience.py` | D5 |
| 4 | Backend tests | `backend/tests/test_import_scan.py`, `test_migrations.py` | D4; revision re-ids |
| 4 | Backend tests | `backend/tests/test_industrial_services_migration.py`, `test_host_materialisation.py`, `test_read_hosts.py`, `test_read_scans.py`, `test_ingest_scan.py`, `conftest.py` | D6; rebase |
| 4 | Backend tests | `backend/tests/test_contract_fidelity.py`, `test_health.py` | any contract change |
| 4 | Frontend tests | `frontend/src/pages/scans/ScanAIAnalysis.test.tsx`, `pages/ScanDetail.test.tsx` | always — AI-disabled / AI-failed scenarios |
| 4 | Frontend tests | `frontend/src/pages/hosts/IndustrialServices.test.tsx`, `pages/HostDetail.test.tsx`, `pages/scans/FindingPanel.test.tsx` | D6 |
| — | Hardware agent | none | PR does not touch `hardware-agent/`; `ScanRunner` / `ScanProgressScreen` unaffected |

---

## 6. Constraints

- Spec phases gate code: no Phase 4 change for a part without a D-row (TRUTH business rule).
- Never `ruff format` / `black .` / root `./lint.sh`; backend gate is `ruff check` only.
- Backend suite counts only via `./database.sh --test` with 0 skipped; DB name exactly `dmitri_test`; never point `supabase db reset|push|migration` at it.
- Do not rewrite Alembic revisions already applied to a hosted database. Confirm with the teammate whether `20260911_20`/`20260912_21`/`20260912_22` ran on any shared Supabase instance before re-id'ing them. `HUMAN_INFRA_REQUIRED` if they did.
- `openapi.d.ts` is generated from `openapi.yaml`; the contract is edited first.
- No live provider calls in tests; `GroqProvider` gets an injected `httpx.Client` / `MockTransport`.
- Hosted `AI_API_KEY` is set by a human in Railway; `HUMAN_INFRA_REQUIRED` for provider account, key issuance, and data-processing terms review.
- Out of scope: chat, reports, Home AI summary; Pi agent changes; unrelated formatting.

## 7. Testing expectations

### Backend (`backend/tests/`, real DB)

| Area | Test | Mirror |
|------|------|--------|
| D2 data boundary | New test in `test_ai_context.py`: seed a scan with hostname, MAC, vendor, OS, industrial services and a long evidence string; build context; assert `set(ScanAIContext.model_json_schema()["properties"])` and per-finding keys equal the exact allowed sets from the ADR; assert forbidden values (hostname, MAC, vendor, org name) do not appear in `context.model_dump_json()`; assert clip limits. A second assertion in `test_ai_groq.py` inspects the captured request body and checks the user message JSON equals the context and nothing else is added. | `test_ai_context.py::test_context_uses_ranked_bounded_enriched_findings`, `test_ai_groq.py::test_groq_provider_requests_strict_structured_output` |
| D2 opt-in (if chosen) | enqueue skips non-opted orgs; read returns `unavailable` for them | `test_ai_jobs.py::test_ai_job_runs_once_after_enrichment_is_terminal`, `test_ai_analysis_read.py::test_analysis_read_is_unavailable_when_ai_is_disabled` |
| AI disabled | `run_worker_once` with `AI_ENABLED=false` (and with blank key) creates no `ai_scan_analyses` row and never constructs/calls a provider; `/scans/{id}` returns full findings; `/analysis` returns `unavailable` | `test_worker_sweep.py::test_run_worker_once_processes_ai_after_enrichment`, `test_ai_analysis_read.py` |
| AI failed | provider timeout/5xx until attempts exhausted → row `failed`, `analysis_json` null, `last_error_code` set; `/scans/{id}` unchanged; `/analysis` returns `failed` with `analysis: null` | `test_ai_jobs.py::test_retryable_provider_failure_is_bounded` |
| Grounding | invented finding id / duplicate explanation → `failed/invalid_analysis`, nothing stored | `test_ai_analysis.py::test_analyzer_rejects_invented_finding_ids` |
| Migrations | single head; upgrade from empty and from `main` head; downgrade of each branch revision | `test_migrations.py`, `test_industrial_services_migration.py` |
| Enrichment (D5) | retry on 429/5xx/transport; exhaust → failed; stale reclaim; truncation if accepted | `test_enrichment_retries.py`, `test_nvd_resilience.py` |
| Import (D4) | keep/dev-only: existing 8 tests; remove: script absent from `pyproject.toml` | `test_import_scan.py`, `test_migrations.py::test_alembic_artifacts_and_backend_package_configuration` |
| Industrial (D6) | per outcome: persistence round trip without process values, org isolation | `test_host_materialisation.py`, `test_read_hosts.py` |
| Contract | every new/changed operation and schema | `test_contract_fidelity.py::test_scan_ai_analysis_operation_is_published` |

### Frontend (Vitest + Testing Library + MSW)

| Scenario | Test | Mirror |
|----------|------|--------|
| AI disabled | MSW `/scans/:id/analysis` → `unavailable`; `ScanDetail` shows all findings and hosts; no `scan-ai-*` test id rendered; no error text | `ScanAIAnalysis.test.tsx` "stays out of the page when AI is unavailable" |
| AI failed | MSW → `failed`; `scan-ai-failed` shown; findings/hosts still rendered; no summary text | "contains provider failure without hiding the scan results" |
| AI read error | MSW → 500; `scan-ai-error` with retry; page still renders findings | "offers an explicit retry when the read fails" |
| Pending stops polling | MSW pending then completed; polling stops after terminal status | new, in `ScanAIAnalysis.test.tsx` |
| Industrial (D6) | per outcome | `IndustrialServices.test.tsx`, `HostDetail.test.tsx` |

Gate: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, plus `npm run gen:types`
with no diff.
