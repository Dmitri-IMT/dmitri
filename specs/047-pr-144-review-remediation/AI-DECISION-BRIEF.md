# AI DECISION BRIEF — PR #144 AI scan analysis (D1–D3 reopened)

Linear: DMI-158 · Parent: [`TRUTH.md`](TRUTH.md) decision log D1–D3 · Read with
[`ARCHITECTURE.md`](ARCHITECTURE.md) Part 2 and [`DESIGN.md`](DESIGN.md) §3.1.

This brief prepares one human decision session. It decides nothing. It gives facts, the
choices the teammate made alone, and the questions in the order they must be answered.

**Citation rule.** Code paths are on branch `feature/ia-implementation` (head `7997383`).
Backend paths are relative to `backend/src/api/` unless they start with `backend/`. "Approved"
means `main:docs/roadmap/AI.md`, `docs/implementation/INTELLIGENCE-IA-ASSESSMENT-ROADMAP.md`
§Fase 3B, `docs/roadmap/SECURITY.md`, and `docs/adr/ADR-005-security-model.md`.

**History fact.** The long roadmap rewrite (Home summary, chat, reports) came first in PR #138
(commit `f0f8439`, "No provider is selected by this document"). That PR was merged by mistake
and reverted. PR #144 re-applied it (`1b072dd`) and then added Groq (`1946c94`, `980033b`). On
`main`, the approved roadmap is still the short Claude version.

---

## 1. What the teammate built

### 1.1 Data flow

```
scan completed ─► enrichment jobs reach terminal state
backend-worker tick (services/worker.py:51-84)
  ├─ sweep_stale_commands
  ├─ process_pending_enrichment_jobs            (NVD, blocking)
  └─ if AI_ENABLED and AI_API_KEY set (worker.py:70-72, ai/factory.py:8-13)
       process_ready_ai_analyses (ai/jobs.py:27-64)
         ├─ enqueue: every completed scan, any org, no enrichment job active,
         │           no analysis row → insert pending row (jobs.py:67-115)
         ├─ claim pending/stale rows (jobs.py:118-180)
         └─ per row: build context (ai/context.py:23-109)
                     → Groq POST /chat/completions (ai/groq.py:35-97, sync httpx)
                     → schema check + finding-id check (ai/validation.py:12-32)
                     → store analysis_json + SHA-256 context_hash (jobs.py:240-247)
browser: ScanDetail → GET /api/v1/scans/{id}/analysis (routers/scans.py:110-129)
         → ai/read.py:31-75 → ScanAIAnalysis card (frontend/src/pages/scans/ScanAIAnalysis.tsx)
```

### 1.2 What data leaves the product (per scan, to Groq)

Sent in one request (`groq.py:36-58`): static system prompt, user prompt with
`context.model_dump_json()` (`groq.py:40-45`), the output JSON schema, model id, and
`reasoning_effort`.

| Level | Fields (`ai/schemas.py`) | Sensitive |
|-------|--------------------------|-----------|
| Scan (`ScanAIContext`, 46-65) | `context_version`, `scan_id`, `timestamp`, **`subnet`**, `scan_mode`, `duration_seconds`, `host_count`, `total_findings`, `scored_findings`, `confirmed_findings`, `kev_findings`, `average_risk_score`, `max_risk_score`, `severity` counts, `top_findings[]` | subnet = customer network range; host count = network size |
| Finding (`AIFindingContext`, 18-43), up to `AI_MAX_FINDINGS` (default 10, max 15) | `finding_id`, `host_id`, **`host_ip`**, `port`, `protocol`, `service`, `cve_id`, `cvss_score`, `severity`, `confidence`, `risk_score`, `exploitability`, `epss_score`, `epss_percentile`, `is_kev`, `known_ransomware`, `title` (500), `description` (4000), `recommendation` (2000), **`evidence` (4000)**, `references` (10 × 2000) | host IP + open service map + exploitability = an attack map; raw scanner `evidence` can hold banners, versions, hostnames, share or account names |

Not sent: org id/name, users, agent id, hostnames field, MAC, vendor, OS, industrial data.
Clip limits: `context.py:11-16`, `81-90`.

### 1.3 When jobs run

- Automatic. No user action. The worker enqueues a job for **every completed scan of every
  org** that has an `org_id` and no analysis row (`jobs.py:87-97`).
- **Back-fill.** Turning AI on sends all historical scans, oldest first (`jobs.py:95`), in
  batches of `ENRICHMENT_BATCH_SIZE` per tick (`worker.py:78`).
- The only switch is deployment-wide: `AI_ENABLED` + non-blank `AI_API_KEY`
  (`core/config.py:25-28`, `factory.py:8-13`). No org-level control. The read route does not
  check any org consent (`routers/scans.py:115-126`).

### 1.4 Provider, model, prompt, output

- Provider: Groq, OpenAI-compatible API, raw `httpx`, no SDK (`groq.py:13-97`). Base URL
  `https://api.groq.com/openai/v1` (`config.py:29-32`).
- Model: `openai/gpt-oss-120b` (`config.py:27`), `reasoning_effort=low` (`config.py:40-42`),
  `include_reasoning=False` (`groq.py:57`), `max_completion_tokens` 4096 (`config.py:37-39`).
- `AI_PROVIDER` is `Literal["groq"]` (`config.py:26`) and is never read; `build_ai_provider`
  always returns `GroqProvider` (`factory.py:16-27`).
- Prompt (`ai/prompts.py:3-20`): "auxiliary defensive security analyst", use only the
  context, never invent facts, state uncertainty, "Write all explanatory prose in **Brazilian
  Portuguese**" (line 11). Context strings are "untrusted evidence" (line 15).
  `AI_PROMPT_VERSION="1"`.
- Output schema `ScanAIAnalysis` (`schemas.py:88-96`), strict JSON schema
  (`groq.py:47-54`): `executive_summary`, `overall_assessment`, `plain_language_summary`,
  `priority_actions[]` (`priority` immediate/high/medium/low, `title`, `description`,
  `related_finding_ids`), `important_findings[]` (`finding_id`, `why_it_matters`,
  `plain_language_explanation`, `recommendation`, `evidence_used[]`, `uncertainty`),
  `uncertainties[]`.

### 1.5 Validation and grounding

- Pydantic `extra="forbid"` on every model; response parsed with `model_validate`
  (`groq.py:69-81`).
- `validate_scan_analysis` rejects finding ids not in the context and duplicate explanations
  (`validation.py:16-32`).
- **Not validated:** every free-text field (summaries, `evidence_used`, recommendations). No
  sentence-level citation. The three summaries cite nothing.
- Stored per row: `provider`, `model`, `context_version`, `prompt_version`, `context_hash`,
  `attempts`, `last_error_code`, timestamps (migration `backend/alembic/versions/20260912_21_ai_scan_analyses.py:33-74`).
- **Not stored:** the prompt, the context JSON actually sent, token usage, latency, who asked
  (nobody asks — it is automatic). No audit event.

### 1.6 Failure handling

- Error map `groq.py:100-111`: 401/403 → not retryable; **400/422 → retryable** (P11); 408,
  429, 498, 5xx → retryable; network/timeout → retryable (`groq.py:61-64`).
- Attempts `AI_MAX_ATTEMPTS=2`, delay 30 s (`config.py:43-46`); stale `processing` rows are
  re-claimed or failed as `processing_timeout` (`jobs.py:130-158`), stale after
  `max(2 × timeout, 60 s)` (`worker.py:82`).
- Validation error or scan not ready → `failed/invalid_analysis`, no retry
  (`jobs.py:218-227`). Unknown exception → logged with `scan_id` only, `failed/internal_error`
  (`jobs.py:228-238`).
- Calls are **synchronous inside the enrichment loop**: worst case one tick blocks for
  `batch_size × 30 s` (10 × 30 s) before enrichment runs again (P6).
- Read side: AI off or scan failed → `unavailable`; no row → **`pending`** (`read.py:47-56`),
  even for a scan no job will ever pick up (P8). A stored payload from an older schema raises
  on `model_validate` (`read.py:58-62`) → HTTP 500.

### 1.7 Frontend behaviour

- Card mounted **first**, above the vulnerability groups (`frontend/src/pages/ScanDetail.tsx:74`).
  It renders `null` while loading and then pushes the epicenter down (DESIGN A4).
- Query polls every 3 s while `pending`/`processing`, no upper bound
  (`ScanAIAnalysis.tsx:13`, `38-43`) → endless polling with P8.
- States: `unavailable` → nothing (46); read error → card with "Try again" in body (48-69);
  pending → prose card (73-87); failed → notice (89-103); completed → summary, "What to do
  first", "Why these vulnerabilities matter", disclosure with assessment and limitations
  (105-204).
- Finding ids are mapped to titles from the scan payload; unknown id → "Recorded
  vulnerability" (166-167). **No link** to the finding, machine, or evidence. No provenance
  line ("written by an AI model"). Provider/model come back in the API
  (`schemas/ai.py:27-28`) but are not shown.
- UI copy is English; the analysis text is pt-BR (A1).

---

## 2. Decisions the teammate made on his own

"Conflict" = contradicts an approved doc. "Silent" = approved docs say nothing.

| # | He chose (where) | Approved docs said | Status | Risk |
|---|------------------|--------------------|--------|------|
| 1 | Provider **Groq** (`groq.py`, `config.py:26-32`) | "default to the latest capable Claude model" (`main:docs/roadmap/AI.md` §Architecture) | Conflict | Unreviewed third party receives customer recon data; retention and training terms not recorded anywhere |
| 2 | Model **`openai/gpt-oss-120b`**, `reasoning_effort=low` (`config.py:27,40`) | Latest capable Claude; model id configurable | Conflict | Quality never evaluated; low reasoning on security explanations |
| 3 | Rewrote `docs/roadmap/AI.md` to match the code, no ADR | Roadmap changes ripple via roadmap-sync; data boundary belongs in SECURITY | Conflict | Docs record a choice nobody made |
| 4 | **Automatic** analysis for every completed scan (`jobs.py:67-115`) | "operator can open a scan and get a summary" (IA roadmap 3B); `POST /scans/{id}/ai-summary` = explicit | Conflict (roadmap implies on request) | Cost and data egress with no user intent |
| 5 | **Back-fill** all historical scans on enable (`jobs.py:87-97`) | Silent | Silent | Whole history of every org leaves at once |
| 6 | **Deployment-wide** switch only, no per-org opt-in (`factory.py:8-13`) | TRUTH: data must not leave "without an explicit, recorded decision"; SECURITY: "LLM data-access scope" open | Conflict with TRUTH | Every tenant is opted in by an env var |
| 7 | Send **`subnet`, `host_ip`, raw `evidence`** (`context.py:67,86,97`) | "scan-scoped" access; data sensitivity "Scans carry sensitive recon data" (SECURITY) | Silent on fields; against its spirit | Attack map plus raw banners at a third party (P5) |
| 8 | Backend **pushes a fixed context** in one call, no tool surface (`groq.py:36-58`) | "restricted tool surface the backend controls" (roadmap, IA 3B) | Conflict (acceptable for a one-shot summary if recorded) | Future chat needs a different design; this one will not grow into it |
| 9 | **No audit log** of prompt, context sent, tool calls, usage, or requester | "prompts, tool calls, and cited evidence IDs are logged" | Conflict | Cannot prove what left the product or why an answer said X |
| 10 | Grounding = finding-id set check only (`validation.py`) | "Every answer cites the scan_id / host_id / finding_id it used" | Partial | Summaries and free text can claim anything |
| 11 | **No citation links** in the UI (`ScanAIAnalysis.tsx:160-178`) | "renders cited evidence as links back into the finding/device views" | Conflict | User cannot verify a claim |
| 12 | **Sync** HTTP calls in the **shared worker loop** (`worker.py:70-84`) | Silent | Silent | AI latency delays enrichment and command sweep (P6) |
| 13 | **Separate job table** + own claim/stale/retry state machine (`jobs.py:118-283`, migration `_21`) | Roadmap named `llm_sessions/llm_messages/llm_artifacts` | Differs | Duplicates the Part 3 enrichment retry logic |
| 14 | Retry 400/422 (`groq.py:103-104`) | Silent | Silent | A request bug burns a second paid call (P11) |
| 15 | **pt-BR prose** in an English UI (`prompts.py:11`) | Silent; FOUNDATIONS: one language per screen | Conflict with design system | Mixed-language screen (A1) |
| 16 | No product vocabulary or "never certify safety" rule in the prompt (`prompts.py:3-12`) | FOUNDATIONS §Vocabulary; teammate's own roadmap says qualify "is my network safe" | Gap | Model may write "device", "finding", or imply safety (A13) |
| 17 | **Card placement** above vulnerabilities (`ScanDetail.tsx:74`) | SCREENS §SCAN DETAIL: epicenter is vulnerabilities; roadmap: "contextual panel" | Conflict | AI prose becomes the first thing read and shifts layout (A4) |
| 18 | **Unbounded 3 s polling** + `pending` with no job (`ScanAIAnalysis.tsx:38-43`, `read.py:55-56`) | Silent | Silent | Permanent spinner-like state, needless load (A2, P8) |
| 19 | No provenance caption; provider/model hidden | Silent | Silent | User cannot tell AI text from scanner facts |
| 20 | Any org member sees it; no role gate | Silent | Silent | Fine if read-only; matters once it costs money per click |
| 21 | Dead `AI_PROVIDER` switch (`config.py:26`, `factory.py:20`) | "keep the model id configurable" | Speculative config | Config that does nothing (P12) |
| 22 | Streaming not used; `max_completion_tokens` 4096 | Roadmap: "Streams responses" | Differs | Low for one-shot; relevant for chat |

---

## 3. Decision tree

Answer in order. A later question assumes the earlier answers.

### Q1 — Does AI stay inside PR #144? (closes D7)

| Option | Pros | Cons |
|--------|------|------|
| A. Keep in PR #144 and fix | One PR; tests exist | Every answer below except "keep as built" rewrites most AI files; PR stays blocked on an ADR; migration `_21` id collides with `main` (P1) |
| B. **Remove from PR #144; redo under its own issue + spec** | PR #144 merges on D4–D6 alone; AI gets a real spec, ADR, and design review | Teammate work is discarded; AI ships later |
| C. Split: AI moves to a follow-up PR from the same code | Keeps code as a starting point | Starting point encodes the decisions under review; anchors the redesign |

**Recommend B.** The data boundary, trigger, audit, and UI all change under any non-default
answer; a clean spec is cheaper than editing a design nobody approved.
Note: the AI context reads `get_scan_risk_summary`, which exists only on this branch (PR #138
re-apply, `1b072dd`). If D6 drops that read, option A also loses its data source.

### Q2 — What is the first AI feature? (product shape)

| Option | Pros | Cons |
|--------|------|------|
| A. One-shot **scan summary** ("what needs attention first") | Smallest; matches IA roadmap 3B "resumo tecnico por scan" and milestone 3 | Not interactive |
| B. **Per-finding explanation** in the vulnerability panel | Small context (one finding); easy to cite; least data out | No scan-level priority |
| C. Contextual **chat panel** with backend tools | Full approved vision | Needs sessions, tool surface, streaming, audit tables; large |

**Recommend A, built as the first milestone of the approved roadmap.** It is the smallest unit
that gives value; B can reuse the same pipeline later. Record that a backend-assembled context
is the "restricted tool surface" for a one-shot call, and chat (C) needs its own ADR.

### Q3 — Provider and model (D1)

Facts for Claude (claude-api skill, model table cached 2026-06-24 — re-check live before the
ADR): `claude-opus-5` $5 / $25 per 1M input/output tokens; `claude-sonnet-5` $2 / $10;
`claude-haiku-4-5` $1 / $5. Structured output uses `output_config.format`. The API
"citations" feature cannot be combined with `output_config.format`, so citations must be ids
inside the schema. Responses can stop with `stop_reason: "refusal"` (categories include
`cyber`); security content must handle it. Official Python SDK `anthropic` 1.x uses `httpx2`
(a new backend dependency → ADR-003 stack note). Groq retention, training, and region terms
are **not verified here** — whoever proposes Groq must bring them.

| Option | Pros | Cons |
|--------|------|------|
| A. **Claude**, one adapter, `AI_MODEL` env var | Matches approved roadmap; no ADR reversal needed | New SDK dependency; cost per call higher than small open models |
| B. Groq + open-weight model (as built) | Code exists; low latency | Reverses an approved line; terms unknown; quality untested |
| C. Provider-neutral layer, two adapters | Swap later | Speculative flexibility (CLAUDE.md §2) unless a second provider is named now |
| D. Self-hosted / local model | No third-party egress | Hosting cost and ops; quality risk; out of team capacity |

**Recommend A**, with Sonnet-class as the default to evaluate first and the model id in env.
Reason: it is the approved choice; changing provider needs evidence, not a merged PR. Decide
cost vs quality on a small fixed eval set of real scans before picking the default id.

### Q4 — Data boundary (D2, part 1)

| Option | Pros | Cons |
|--------|------|------|
| A. Full context as built | No change | IP, subnet, raw evidence leave |
| B. **Minimised**: drop `subnet`, `host_ip`, raw `evidence`, `references`; keep ids, port, protocol, service, CVE, scores, KEV/EPSS flags, scanner title/description/recommendation (clipped) | Explanation does not need addresses; UI maps ids back to machines | Slightly less specific wording |
| C. Tokenised (IP → "machine 3") | Keeps structure | Mapping code in validation + UI; little gain over B |
| D. Minimised + opt-in to also send evidence | Flexible | A second boundary to test and explain |

**Recommend B.** Reason: a plain-language priority summary needs the vulnerability, not the
address. A test must pin the exact field set (P18).

### Q5 — Consent and scope (D2, part 2)

| Option | Pros | Cons |
|--------|------|------|
| A. Deployment switch only (as built) | Simple | Every tenant opted in by env; breaks TRUTH rule |
| B. **Deployment kill switch + per-org opt-in by an admin, off by default; no back-fill** | Explicit, recorded consent per customer; matches TRUTH | Needs an org flag, a settings route, contract, and a Settings row (DESIGN §5 shape) |
| C. Per-request consent (the click is the consent) | No settings screen | A member consents for the whole org's data; weak for B2B |

**Recommend B.** Reason: the customer, not an env var, decides if its recon data goes to a
third party. With Q6 "on demand", opt-in makes the button appear; it sends nothing by itself.

### Q6 — Trigger: automatic or on demand (D3, part 1)

| Option | Pros | Cons |
|--------|------|------|
| A. Automatic after enrichment (as built) | Ready when opened | Pays for scans nobody reads; no user intent in the audit record |
| B. **On demand**: "Explain this scan" creates a job | Cost and egress only when wanted; clear requester for audit; no endless `pending` | User waits (seconds to tens of seconds) |
| C. Automatic for the latest scan only, on demand for others | Home-friendly | Two paths to build and test |

**Recommend B.** Reason: intent, cost, and audit all come from one explicit action. Add a
per-org daily cap. Regenerate only when the context hash or prompt version changed.

### Q7 — Where it runs (D3, part 2)

| Option | Pros | Cons |
|--------|------|------|
| A. Synchronous in the API request | No job table | Request held open for the model call; timeouts at the edge |
| B. Same worker loop, as built | Exists | Blocks enrichment and the command sweep (P6) |
| C. **Job row + worker claims at most one AI job per tick, provider timeout bounded**, shared claim/retry helper with enrichment | Reuses the Part 3 (D5) retry design; no duplicate state machine | Enrichment still waits up to one timeout per tick |
| D. Separate AI worker process | Full isolation | New Railway service, deploy and ops cost |

**Recommend C.** Reason: bounded cost to enrichment with no new service; move to D only if
measured latency hurts. Retry only 408/429/5xx/network; 400/422 are final.

### Q8 — Grounding, citations, audit

| Option | Pros | Cons |
|--------|------|------|
| A. As built (id set check + hash) | Exists | No record of what left; summaries uncited |
| B. **Every output item carries ≥1 `finding_id`; ids validated; store the exact context JSON sent, prompt version, model id, token usage, latency, requester `user_id`, org, timestamps; write an activity/audit event** | Meets approved "auditable" and "cites IDs"; answers "what did we send" | Stores a copy of scan data (cascade-delete with the scan) |
| C. B + second-pass check of free text against the context | Stronger | Second model call; complex; defer |

**Recommend B.** Reason: it is the approved guardrail, and the stored context is the proof of
the data boundary. Prompt must carry product vocabulary and the "never certify safety" rule
(A13).

### Q9 — Output language

| Option | Pros | Cons |
|--------|------|------|
| A. pt-BR (as built) | Target users may read Portuguese | Mixed-language screen; UI is English |
| B. **English, same as the UI** | One language per screen (FOUNDATIONS) | Non-English readers wait for i18n |
| C. Follow a UI locale setting | Right long-term | No i18n exists; out of scope |

**Recommend B.** Reason: the output language follows the UI language; i18n is its own decision.

### Q10 — Frontend surface and states

| Option | Pros | Cons |
|--------|------|------|
| A. Card at top of SCAN DETAIL (as built) | Visible | Displaces the epicenter; layout shift (A4) |
| B. **Card after the vulnerability groups**, with a generate button | Facts first; AI is secondary | Less visible |
| C. Side panel / drawer (approved "contextual panel") | Matches roadmap; room for chat later | New layout primitive; bigger design work |
| D. Inline in the vulnerability panel (per finding) | Tight to the evidence | Only fits Q2-B |

**Recommend B for Q2-A.** Required states: org not opted in → card **absent** (absent-not-
disabled rule); not yet generated → one outline button `Explain this scan`; running → bounded
polling only while a job exists, with a loading indicator (DESIGN Q6); failed → notice +
`Reload overview` in the footer; completed → items with **links to the cited vulnerabilities**,
plus caption `Written by an AI model from this scan's results. Check the vulnerabilities before
acting.`; outdated (context hash changed) → note + regenerate. Who may click: decide member vs
admin (cost). A new DESIGN.md from `frontend-design-agent` owns exact copy and test ids.

---

## 4. Consequence of "remove AI from PR #144"

### Files to delete (branch paths)

- Backend service: `backend/src/api/services/ai/` — `__init__.py`, `analyzer.py`,
  `context.py`, `factory.py`, `groq.py`, `jobs.py`, `prompts.py`, `provider.py`, `read.py`,
  `schemas.py`, `validation.py`.
- `backend/src/api/schemas/ai.py`.
- Migration `backend/alembic/versions/20260912_21_ai_scan_analyses.py`.
- Tests: `backend/tests/test_ai_analysis.py`, `test_ai_analysis_read.py`,
  `test_ai_context.py`, `test_ai_groq.py`, `test_ai_jobs.py`.
- Frontend: `frontend/src/pages/scans/ScanAIAnalysis.tsx`, `ScanAIAnalysis.test.tsx`.

### Files to edit

| File | Change |
|------|--------|
| `backend/src/api/models/persistence.py` | Remove `_AI_ANALYSIS_STATUS_CHECK` (line 17) and `AIScanAnalysisRecord` (line 250) |
| `backend/alembic/versions/20260912_22_enrichment_retries.py` | `down_revision = "20260912_21"` must be re-chained (D5 keeps this file); the chain is being rebuilt on `main` anyway (P1, P2) |
| `backend/src/api/core/config.py` | Remove `ai_*` settings (lines 25-46) |
| `backend/.env.example` | Remove the `AI_*` block (keep the `ENRICHMENT_*`/NVD lines from Part 3) |
| `backend/src/api/routers/scans.py` | Remove the `/analysis` route (110-129) and imports (13, 23-24) |
| `backend/src/api/services/worker.py` | Remove AI imports (9-10) and the AI block (70-84); return enrichment count |
| `backend/tests/test_worker_sweep.py` | Remove `test_run_worker_once_processes_ai_after_enrichment` |
| `backend/tests/test_settings.py` | Remove `AI_*` env and asserts |
| `backend/tests/test_contract_fidelity.py` | Remove the 4 AI schema names and `test_scan_ai_analysis_operation_is_published` |
| `backend/tests/test_health.py` | Remove `("/api/v1/scans/{scan_id}/analysis", "GET")` |
| `contracts/openapi/openapi.yaml` | Remove `/api/v1/scans/{scan_id}/analysis`, `AIRecommendedAction`, `AIFindingExplanation`, `ScanAIAnalysis`, `ScanAIAnalysisResponse` |
| `frontend/src/types/openapi.d.ts` | Regenerate |
| `frontend/src/api/scans.ts`, `frontend/src/api/queryKeys.ts` | Remove `getScanAnalysis`, `ScanAIAnalysisResponse`, `scans.analysis` |
| `frontend/src/pages/ScanDetail.tsx` | Remove import (12) and mount (74) |
| `frontend/src/test/mswHandlers.ts` | Remove the `/scans/:scanId/analysis` handler |
| `docs/roadmap/AI.md` | Restore `main` version (or keep PR #138 vision text only if the maintainer accepts it separately) |
| `docs/roadmap/README.md`, `backend/README.md` (AI section ~162-175) | Remove AI rows/section |
| `docs/implementation/INTELLIGENCE-IA-ASSESSMENT-ROADMAP.md` | Keep the two "concluido" risk lines only if D6 keeps risk reads; drop "tool layer independente do provedor" unless ADR says so |
| `specs/047-*/ARCHITECTURE.md` Part 2, D1–D3; `DESIGN.md` §2.2, §3.1, A1–A13 | Mark "moved to new AI spec" |

### What breaks, and what does not

- Nothing outside AI imports `services/ai` except `routers/scans.py` and `worker.py`.
- Contract fidelity and route-surface tests fail until the contract, `openapi.d.ts`, and
  `test_health.py` are edited together.
- Alembic history breaks until `_22` is re-chained.
- The risk-summary and finding-detail reads (`/risk-summary`, `/findings/{id}`) are **not** AI
  files; they ride with D6 and stay or go on that decision.
- New Linear issue required (TRUTH: rejected work becomes an issue). The teammate's tests
  (`test_ai_context.py`, `test_ai_groq.py`, `ScanAIAnalysis.test.tsx`) are useful references
  for the new spec.

---

## 5. What the AI ADR must record

Path: next free ADR number at write time (ARCHITECTURE Phase 3 names `ADR-020`; check open
branches first). Layout as ADR-018: Status, Context, Decision, Consequences, Rejected
alternatives, References.

1. **Scope.** Which feature (Q2). What is explicitly not included (chat, reports, Home, active
   actions). Read-only.
2. **Provider and model policy (Q3).** Named provider; default model id; who may change
   `AI_MODEL` and how a change is approved; eval set used to pick it; provider retention,
   training, and region terms with a dated source; refusal handling.
3. **Data boundary (Q4).** Exact field list sent; fields never sent; clip limits; version
   (`context_version`); the test that pins it.
4. **Consent (Q5).** Deployment kill switch; per-org rule and default; who may toggle; what the
   disclosure line says; back-fill rule; what happens to stored analyses when an org opts out.
5. **Trigger and cost (Q6).** Automatic or on demand; who may request; per-org caps; when a
   stored analysis is reused or regenerated.
6. **Execution (Q7).** Where it runs; per-tick limit; timeout; retryable status codes; attempt
   budget; stale handling; relation to the enrichment job design (D5).
7. **Grounding (Q8).** Context-only prompt; strict schema; citation rule (every item cites ids,
   validated); how free text is labelled; prompt-injection stance.
8. **Audit and retention (Q8).** What is stored per call (context sent, prompt version, model,
   usage, requester, timestamps); audit event name; retention period; cascade on scan delete;
   access (RLS, `dmitri_runtime` grants).
9. **Failure behaviour.** AI off, not opted in, not configured, failed: scan results unaffected;
   no partial analysis shown; no endless pending.
10. **Output language and vocabulary (Q9, A13).** Language; product vocabulary; "never certify
    safety".
11. **Frontend surface (Q10).** Placement; states; citation links; provenance caption. Link the
    DESIGN.md that owns copy.
12. **Secrets (ADR-005).** API key as `SecretStr`, never logged, where it is unwrapped.
13. **Rejected alternatives.** At minimum: Groq/gpt-oss-120b as built, automatic back-fill,
    deployment-only switch, full raw-evidence context — each with the reason.
14. **Ripple.** `docs/roadmap/AI.md` and `SECURITY.md` ("LLM data-access scope" row moves from
    Open to decided), `BACKEND.md`, `FRONTEND.md`, `.env.example`, `docs/DEV-SETUP.md`.
