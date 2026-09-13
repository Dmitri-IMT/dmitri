# Tasks — Review and remediate PR #144 (`047-pr-144-review-remediation`)

7 tasks (#6 and #7 are human). **Unblocked now: #1, #4**

Scope: PR #144 only — `ARCHITECTURE.md` §2.1 and `TRUTH.md` "Acceptance criteria → PR #144
(merge gate)". Epic-scoped work lives in Linear DMI-161 (DMI-162…DMI-170) and gets no task here.
Work on branch `feature/dmi-158-review-pr-144`; the PR head is `feature/ia-implementation`.

Layers and agents:

| Tasks | Blast radius | Test agent | Review agent | Gate |
|---|---|---|---|---|
| #1, #2 | `backend/` | `test-engineer` (tests under `backend/tests/`) | `code-reviewer` | `./database.sh --test`, then `cd backend && uv run ruff check src tests` — never `ruff format` |
| #3, #4 | `frontend/` | `frontend-test-engineer` | `frontend-code-reviewer` | `npm run lint && npm run format:check && npm run typecheck && npm run test && npm run build` |
| #5 | docs + all gates | — | `code-reviewer` + `frontend-code-reviewer` | all of the above, `npm run gen:types` no diff |
| #6 | hosted database + Railway variables | human operator | — | `alembic current` = `20260912_25 (head)`; AI variables set |
| #7 | full product flow | human validator | — | every scenario in Task 7 passes |

Rules for every task: extend existing test files, add no new test files; no temporary code; backend
formatted by hand.

---

## Task 1: `Explain this scan` request route and no automatic AI jobs
- **Description**: Implement D10 per `ARCHITECTURE.md` §2.1 "D10" and `TRUTH.md` D10.
  Add `POST /api/v1/scans/{scan_id}/analysis` (`operationId: requestScanAIAnalysis`,
  `require_user`, any member) backed by `request_scan_ai_analysis` in `services/ai/jobs.py`:
  404 foreign scan; AI unavailable or scan not completed → `unavailable`, no row; no row →
  insert `pending`, 202; `failed` → reset to `pending`, `attempts=0`, clear `last_error_code`,
  202; `pending`/`processing`/`completed` → 409, no change; concurrent inserts rely on the
  unique `scan_id` constraint and the loser gets 409. Remove `enqueue_ready_ai_analyses` and its
  call; move the "no active enrichment job" condition into the claim. The read route returns
  `not_requested` when no row exists. Edit the contract first, then regenerate frontend types.
- **Absorbed**: OpenAPI contract edit and `openapi.d.ts` regeneration (no logic of their own;
  covered by `test_contract_fidelity.py` and `test_health.py` in this task).
- **Dependencies**: —
- **Target Files**: [`backend/src/api/routers/scans.py`, `backend/src/api/services/ai/jobs.py`,
  `backend/src/api/services/ai/read.py`, `backend/src/api/schemas/ai.py`,
  `contracts/openapi/openapi.yaml`, `frontend/src/types/openapi.d.ts`,
  `backend/tests/test_ai_analysis_read.py`, `backend/tests/test_ai_jobs.py`,
  `backend/tests/test_contract_fidelity.py`, `backend/tests/test_health.py`]
- **Tests**: `test_ai_analysis_read.py` — POST on a completed scan → 202 and one `pending` row;
  second POST → 409 and no change; POST after `completed` → 409; POST on `failed` → 202 and
  `pending` with `attempts=0`; foreign scan → 404; AI off → `unavailable` and no row; GET with no
  row → `not_requested`. `test_ai_jobs.py` — completed scans with no request produce no row after
  processing; a requested job is not claimed while an enrichment job for that scan is active.
  `test_contract_fidelity.py` / `test_health.py` — the new operation is published and routed.
- **Success Criteria**: all tests above pass against `dmitri_test` with 0 skipped; `grep -rn
  enqueue_ready_ai_analyses backend/src` returns nothing; `cd frontend && npm run gen:types &&
  git diff --exit-code src/types/openapi.d.ts` passes after the commit; `uv run ruff check src
  tests` clean; every call site of `process_ready_ai_analyses` and `get_scan_ai_analysis`
  (`services/worker.py`, `routers/scans.py`, their tests) still compiles and passes.
- **Status**: COMPLETED
- **Review Rejections**: 2

## Task 2: AI loop outside the enrichment loop, plus AI cleanup
- **Description**: Implement D3 (PR scope) per `ARCHITECTURE.md` §2.1 "D3" and the cleanup
  table. Remove the AI block from `run_worker_once` (it returns the enrichment count only). Add
  `services/ai/worker.py` with `run_ai_worker_once()` (own session, claims and processes at most
  one job) and `run_ai_worker_loop()` (builds the provider once, own sleep of
  `AI_POLL_INTERVAL_SECONDS`, logs and continues on exceptions). `worker_main.main()` starts the
  AI loop in a daemon thread when `ai_is_available(settings)`, then runs `run_worker_loop()`.
  Add `AI_POLL_INTERVAL_SECONDS` (default 5). Remove `AI_PROVIDER` and store `"groq"` as a
  constant. Change the system prompt to ask for English prose and bump `AI_PROMPT_VERSION`.
  Remove the branch-added explanatory docstrings (P14) and the stale `.env.example` comment
  (P13).
- **Absorbed**: `.env.example` edits, docstring removal, `AI_PROVIDER` removal and the English
  prompt line (no branching of their own; covered by `test_settings.py`, `test_ai_groq.py` and
  the worker tests in this task).
- **Dependencies**: Task 1 (both edit `services/ai/jobs.py`)
- **Target Files**: [`backend/src/api/services/worker.py`, `backend/src/api/services/ai/worker.py`,
  `backend/src/api/worker_main.py`, `backend/src/api/core/config.py`, `backend/.env.example`,
  `backend/src/api/services/ai/factory.py`, `backend/src/api/services/ai/prompts.py`,
  `backend/src/api/services/ai/*.py` (docstrings only), `backend/src/api/schemas/read.py`
  (docstrings only), `backend/tests/test_worker_sweep.py`, `backend/tests/test_ai_jobs.py`,
  `backend/tests/test_settings.py`, `backend/tests/test_ai_groq.py`]
- **Tests**: `test_worker_sweep.py` — `run_worker_once` never builds a provider and processes
  enrichment while a pending AI row exists (replaces
  `test_run_worker_once_processes_ai_after_enrichment`). `test_ai_jobs.py` —
  `run_ai_worker_once` processes one requested row with a fake provider; with AI unavailable it
  makes no provider call. `test_settings.py` — `AI_POLL_INTERVAL_SECONDS` default and override;
  `AI_PROVIDER` is no longer a setting. `test_ai_groq.py` — the system prompt requests English and
  contains no Portuguese instruction.
- **Success Criteria**: tests above pass against `dmitri_test` with 0 skipped; `grep -rn
  "ai_provider\|AI_PROVIDER" backend/src backend/.env.example` returns nothing; `grep -n
  "Brazilian Portuguese" backend/src/api/services/ai/prompts.py` returns nothing; no triple-quoted
  docstrings added by the PR remain in `services/ai/`; `uv run ruff check src tests` clean.
- **Status**: COMPLETED
- **Review Rejections**: 1 (thermo-nuclear: required provider on `run_ai_worker_once`; fixed)

## Task 3: `Explain this scan` button on the AI card
- **Description**: Implement the PR #144 AI states per `DESIGN.md` §4 "Target: AI states" and
  `ARCHITECTURE.md` §2.1 "D10". Add `requestScanAnalysis` to `api/scans.ts`. In
  `ScanAIAnalysis.tsx`: `not_requested` renders `scan-ai-not-requested` with copy `Get a
  plain-language overview of this scan.` and a footer outline `size="sm"` button `Explain this
  scan` (`scan-ai-request`); `failed` renders `Couldn't prepare the overview. The scan results are
  complete without it.` with the same button; every other status renders no button. Pressing
  disables the button, sends the POST, writes the response into the query cache, and polls every
  3 s only while `pending`/`processing`, stopping after 5 minutes. A 409 refetches the status. A
  POST error shows the read-error state. `unavailable` still renders nothing. Card position and
  completed layout stay as built.
- **Absorbed**: `requestScanAnalysis` wrapper and the MSW POST handler (no logic beyond URL and
  type; exercised by the component tests).
- **Dependencies**: Task 1 (generated types and route)
- **Target Files**: [`frontend/src/api/scans.ts`, `frontend/src/pages/scans/ScanAIAnalysis.tsx`,
  `frontend/src/test/mswHandlers.ts`, `frontend/src/pages/scans/ScanAIAnalysis.test.tsx`,
  `frontend/src/pages/ScanDetail.test.tsx`]
- **Tests**: `ScanAIAnalysis.test.tsx` — `not_requested` shows the button; pressing sends one POST,
  hides the button, shows pending, then completed, and polling stops; `failed` shows the failed
  copy and the button; `pending`/`processing`/`completed` show no button; a 409 on press refetches
  the status and the button disappears; `unavailable` renders no `scan-ai-*` test id.
  `ScanDetail.test.tsx` — vulnerabilities and machines render while the analysis request never
  resolves.
- **Success Criteria**: tests above pass; frontend gate passes (`lint`, `format:check`,
  `typecheck`, `test`, `build`); no `dangerouslySetInnerHTML` added.
- **Status**: COMPLETED
- **Review Rejections**: 1 (thermo-nuclear: exhaustive status switch and DESIGN error card; fixed)

## Task 4: Industrial UI on main's `IndustrialServiceView` (F1)
- **Description**: Per `TRUTH.md` D6 / F1 and `ARCHITECTURE.md` §2.1 "D6", make the industrial
  components compile against `IndustrialServiceView`. Replace `ModbusTcpServicePayload` types in
  `IndustrialServices.tsx`, its two callers and the fixtures; remove rendering of `values`,
  `value_min`, `value_max`, `nonzero_count` and `validations`, which the contract no longer has.
  Other copy and layout changes from `DESIGN.md` §3.2 are Epic DMI-170 and out of this task.
- **Absorbed**: `industrialFixtures.ts` update (fixture data; consumed by the suites below).
- **Dependencies**: —
- **Target Files**: [`frontend/src/pages/hosts/IndustrialServices.tsx`,
  `frontend/src/pages/scans/ScanIndustrialServices.tsx`, `frontend/src/pages/HostDetail.tsx`,
  `frontend/src/test/industrialFixtures.ts`, `frontend/src/pages/hosts/IndustrialServices.test.tsx`,
  `frontend/src/pages/HostDetail.test.tsx`, `frontend/src/pages/ScanDetail.test.tsx`]
- **Tests**: `IndustrialServices.test.tsx` — a service with units and address ranges from an
  `IndustrialServiceView` fixture renders port, confidence, unit status and ranges; no min/max,
  non-zero count or validation text appears. `HostDetail.test.tsx` / `ScanDetail.test.tsx` —
  industrial cards render from the new fixtures.
- **Success Criteria**: `npm run typecheck` reports 0 errors (was 14); `grep -rn
  "ModbusTcpServicePayload\|value_min\|value_max\|nonzero_count\|validations" frontend/src` returns
  nothing outside generated types; frontend gate passes.
- **Status**: COMPLETED
- **Review Rejections**: 1 (thermo-nuclear: collapse leftover `readable` branch; fixed)

## Task 5: ADR-020, AI roadmap, docs sync and full gates
- **Description**: Per `ARCHITECTURE.md` §2.1 "ADR-020", §3 Phases 3, 5, 6 and 7. Write
  `docs/adr/ADR-020-ai-scan-analysis.md` (layout as `ADR-018`; re-check the next free ADR number on
  open branches) recording the merged AI and a "Planned changes" section linking DMI-161…DMI-170.
  Rewrite `docs/roadmap/AI.md` to state this spec's decisions (run `roadmap-sync`). Run
  `docs-sync` for the code map, `docs/DEV-SETUP.md` (every `AI_*` including
  `AI_POLL_INTERVAL_SECONDS`, `ENRICHMENT_*`, `NVD_MIN_REQUEST_INTERVAL_SECONDS`), the Railway runbook
  (`AI_ENABLED` and `AI_API_KEY` on both `api` and `worker`),
  `docs/README.md` and `backend/README.md`. Run every gate and record results (tested commit,
  backend passed/skipped counts, frontend results) in a new `TRUTH.md` "Gate results" section.
- **Dependencies**: Tasks 1, 2, 3, 4
- **Target Files**: [`docs/adr/ADR-020-ai-scan-analysis.md`, `docs/roadmap/AI.md`,
  `docs/roadmap/README.md`, `docs/README.md`, `docs/DEV-SETUP.md`, `docs/cloud/railway/SETUP.md`, `backend/README.md`,
  `.claude/docs/backend/services.md`, `.claude/docs/backend/routers.md`,
  `.claude/docs/backend/schemas.md`, `.claude/docs/backend/api.md`,
  `.claude/docs/backend/models.md`, `.claude/docs/backend/migrations.md`,
  `.claude/docs/backend/management.md`, `.claude/docs/contracts.md`, `.claude/docs/log.md`,
  `specs/047-pr-144-review-remediation/TRUTH.md`]
- **Tests**: No new test file. Documentation and gate-run task; the spec defines no testable
  artifact for docs. The reviewer gates on the full backend and frontend suites run here.
- **Success Criteria**: ADR-020 exists with Status, Context, Decision, Consequences, Rejected
  alternatives, References and a Planned changes list naming DMI-162…DMI-170; `docs/roadmap/AI.md`
  names Groq as merged provider, `Explain this scan` as trigger, and the epic targets, and lists
  chat, reports and Home summary as not decided; `./database.sh --test` passes with 0 failed and 0
  skipped; `uv run ruff check src tests` clean; `uv run alembic heads` prints one head
  `20260912_25`; `npm run gen:types` gives no diff; frontend gate passes; `docs-sync` reports no
  drift; `TRUTH.md` "Gate results" filled in.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6: Migrate the production database and set the AI variables (human, `HUMAN_INFRA_REQUIRED`)
- **Description**: Run after Tasks 1–5 are built and merged, before or as the PR #144 deploy
  restarts the services. The hosted Supabase database is at `20260907_20`, so the API
  currently fails with `UndefinedColumn` (`hosts.operating_system_json`,
  `scan_hosts.operating_system_json`, `commands.nspi_options`). Per `TRUTH.md` "Integration
  status → Production database" and `ARCHITECTURE.md` §2.1 "Production database":
  1. Follow `docs/cloud/supabase/SETUP.md`: pre-flight backup; export `DATABASE_URL_DIRECT` in a
     local shell only; from the merged code run `cd backend && uv run alembic upgrade head` (one
     run applies `20260903_18` through `20260912_25`); `unset DATABASE_URL_DIRECT`; confirm
     `uv run alembic current`.
  2. Get a Groq API key. Set `AI_ENABLED=true` and `AI_API_KEY=<Groq key>` on **both** Railway
     services, `api` (the analysis routes return `unavailable` without them) and `worker` (it
     calls Groq). Leave the other `AI_*` settings at their defaults unless the runbook says
     otherwise. Never set `DATABASE_URL_DIRECT` on either service.
  3. Restart `api` and `worker`.
  Reproduced on `dmitri_test` 2026-09-13: upgrading from `20260907_20` reaches the head; every
  missing revision adds nullable columns or new tables.
- **Dependencies**: Task 5 (merged)
- **Target Files**: [hosted Supabase database, Railway `api` and `worker` variables — no repository file]
- **Tests**: No test file. Ops step with no repository artifact; verification is the database
  revision, the Railway variables and the logs. Task 7 validates the result end to end.
- **Success Criteria**: `alembic current` on the hosted database prints `20260912_25 (head)`;
  `railway variable list --json` shows `AI_ENABLED` and `AI_API_KEY` on `api` and `worker` and no
  `DATABASE_URL_DIRECT` on either; after restart the `api` logs show no `UndefinedColumn` and the
  `worker` logs show the enrichment loop and the AI loop starting.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 7: Human validation of the full flow in production
- **Description**: A human validates the merged feature end to end in the deployed web app
  against `TRUTH.md` "Acceptance criteria → PR #144 (merge gate)" and `DESIGN.md` §4 "Target: AI
  states". Record each result (pass/fail, date, notes, screenshot link where useful) in a new
  `TRUTH.md` "Human validation" section. Any failure becomes a bug issue linked to DMI-158.
  Scenarios:
  1. **Scan to results.** Start a scan from a device; it completes; Scan Detail shows
     vulnerabilities and machines without waiting for any AI.
  2. **Enrichment.** Within a few minutes, risk scores appear on vulnerabilities (reload allowed);
     the worker logs show enrichment not blocked by AI.
  3. **Not requested.** The AI card shows `Get a plain-language overview of this scan.` and
     `Explain this scan`.
  4. **Explain.** Pressing the button (as a viewer, then on another scan as an admin) hides it and
     shows `Preparing a plain-language overview of this scan.`; the overview appears without a
     reload, in English.
  5. **Once per scan.** After the press, a second browser session on the same scan shows no
     button; a repeated `POST /api/v1/scans/{id}/analysis` returns 409.
  6. **Failure.** With an invalid `AI_API_KEY` on `worker` (restore it after), pressing the button
     ends in `Couldn't prepare the overview. The scan results are complete without it.` with the
     button offered again; scan results stay visible.
  7. **AI off.** With `AI_ENABLED=false` on `api` (restore it after), Scan Detail shows no AI card
     and no error.
  8. **Industrial services.** A machine with Modbus shows the industrial card on Machine and Scan
     Detail with no process values; a machine without it shows no card.
  9. **Other pages.** Home, Network, Machine Detail, Devices and Scans load with no errors in the
     browser console or `api` logs.
- **Dependencies**: Task 6
- **Target Files**: [`specs/047-pr-144-review-remediation/TRUTH.md` ("Human validation" section only)]
- **Tests**: No test file. Manual acceptance of the deployed system; the automated suites ran in
  Task 5.
- **Success Criteria**: all nine scenarios recorded as pass in `TRUTH.md` "Human validation", or
  each failure linked to a new bug issue; AI and variable settings restored after scenarios 6–7.
- **Status**: PENDING
- **Review Rejections**: 0

---

## Dependency graph

```
#1 ──► #2 ─┐
#1 ──► #3 ─┼──► #5 ──► merge ──► #6 (human: migrate + AI variables) ──► #7 (human validation)
#4 ────────┘
```

Parallel tracks: backend (#1 → #2), frontend (#4 now; #3 after #1). Human tasks #6 and #7 run after merge.

## Status

| # | Task | Status |
|---|------|--------|
| 1 | `Explain this scan` request route and no automatic AI jobs | COMPLETED |
| 2 | AI loop outside the enrichment loop, plus AI cleanup | COMPLETED |
| 3 | `Explain this scan` button on the AI card | COMPLETED |
| 4 | Industrial UI on main's `IndustrialServiceView` (F1) | COMPLETED |
| 5 | ADR-020, AI roadmap, docs sync and full gates | COMPLETED |
| 6 | Migrate the production database and set the AI variables (human) | PENDING |
| 7 | Human validation of the full flow in production | PENDING |
