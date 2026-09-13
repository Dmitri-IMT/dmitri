# TRUTH — Review and remediate PR #144 (scan intelligence, AI analysis, resilient enrichment)

Linear: DMI-158

## Narrative

A teammate opened PR #144 without an issue, a spec, or an approved decision. The PR bundles
four separate changes into one branch:

1. **Industrial services and risk context** — shows industrial protocol observations and risk
   context for hosts and findings. This work re-applies an earlier PR that was merged by
   mistake and then reverted.
2. **AI scan analysis** — after a scan, the backend sends a summary of the scan to an external
   LLM provider (Groq, running an open-weight model) and shows a plain-language analysis in
   the web app.
3. **Resilient vulnerability enrichment** — enrichment from the public vulnerability database
   retries after rate limits and temporary failures, and recovers abandoned jobs.
4. **Local scan import** — an operator can load a scan result file into the backend without a
   Raspberry Pi.

CI is green. But the PR broke the project process:

- Nobody decided to use Groq. The AI roadmap said "default to the latest capable Claude model".
  The PR rewrote the roadmap to match the code, instead of recording a decision.
- No ADR exists for the AI agent, even though it sends customer network data to a third party.
- The knowledge base and the code map were not synced.
- The scope overlaps open issues on industrial service persistence and enrichment error
  handling.

This spec organizes the review. It turns every open question into a recorded decision, and it
makes the branch meet project rules before it can merge. It is for the maintainers who own the
merge, and for the teammate, who must understand why each change is kept, changed, or removed.

## Business rules

- **Decisions come before code changes.** No remediation code is written for a part of the PR
  until the maintainers record a decision for that part (keep, change, or remove).
- **Every decision has a record.** A decision that changes the architecture, the data boundary,
  or a sanctioned provider becomes an ADR. Smaller choices are written into this spec's decision
  log.
- **Customer network data does not leave the product without an explicit, recorded decision.**
  The AI data boundary (what is sent, to whom, and whether the operator can turn it off) must be
  decided and written in the AI ADR before the AI part can merge.
- **The AI analysis never hides scan results.** If the AI is off, not configured, or fails, the
  operator still sees the full scan results.
- **Keep the author's features.** PR #144 changes only what it needs to work and pass the gates.
  Redesigns are Epic-scoped issues, not rewrites inside this PR.
- **Rejected work is not rewritten here.** A part that is removed or deferred becomes a new
  Linear issue. It is not rebuilt inside this review.
- **No temporary code.** Fixes follow the CLAUDE.md rule: complete shape or an explicit
  question to the maintainers.
- **Overlaps are resolved, not duplicated.** Where the PR covers an open issue, the decision
  log says which one wins, and the other issue is closed or rescoped.
- **Green means green.** The backend suite counts only with the test database up and zero
  skipped tests.
- **Docs follow code.** The knowledge base, code map, setup guide, roadmap, and API contract
  describe what the merged branch actually does.

## Plan (phases, in order)

| Phase | Name | Output | Gate to next phase |
|-------|------|--------|--------------------|
| 0 | Baseline | Branch integrated with current main by merge or rebase; gates run once; results recorded as the "before" state | Baseline recorded |
| 1 | Code review | Findings list for the whole PR, ranked by severity, grouped by the four parts | Findings recorded |
| 2 | Decision review | One decision per question D1–D11 (below), approved by a maintainer, with the teammate consulted; each marked PR or Epic scope | PR-scoped rows decided |
| 3 | ADRs | ADR-020 records the AI as merged (Groq, context as built, `Explain this scan`) and the Epic target decisions; `docs/roadmap/AI.md` rewritten to state these decisions | ADR accepted |
| 4 | Remediation | PR-scoped changes only; the epic and its issues are created for Epic-scoped rows | Every finding fixed in the PR or linked to an epic issue |
| 5 | Gates | All per-layer gates green, zero skipped backend tests | All green |
| 6 | Docs sync | Knowledge base, code map, setup guide, roadmap, and contract match the branch | No drift reported |
| 7 | Merge readiness | PR description updated with decisions, ADR links, and "Fixes DMI-158"; overlapping issues closed or rescoped | Maintainer approval |

Phase 1 runs before Phase 2 because review findings are inputs to the decisions (for example, a
data-exposure finding changes the data-boundary decision).

## Decisions to make (Phase 2)

| ID | Question | Options to weigh |
|----|----------|------------------|
| D1 | Which LLM provider and model does the AI analysis use? | Keep Groq with an open-weight model; switch to the Claude model the roadmap named; OpenAI GPT-5.6 Luna; provider-neutral with one default |
| D2 | What scan data may be sent to the provider, and can an organisation opt out? | Full context as built; reduced or anonymised context; off by default per organisation with explicit opt-in |
| D3 | How are AI analysis jobs run and retried? | Keep the separate AI job flow as built; fold into the existing background worker |
| D4 | Is the local scan import a product feature or a developer tool? | Keep as a supported command; keep as a dev-only tool; remove |
| D5 | Is the enrichment retry design accepted, and how does it relate to the open enrichment-error issue? | Accept and close/rescope that issue; accept with changes; defer |
| D6 | Does the industrial services part duplicate or conflict with the open industrial persistence work? | This PR wins and the issues are rescoped; the in-progress issue wins and this part is removed; merge both |
| D7 | Does PR #144 merge as one PR or split into one PR per part? | One PR; split into four; split AI from the rest |
| D8 | What is the prompt-injection architecture for AI tasks, now and when web research is added? | System-prompt warning only; context minimisation + strict output validation; full trust-zone design with a quarantined research stage |
| D9 | How does the AI write customer-facing prose? | Free prompt wording; application-owned writing skill + deterministic linter |
| D10 | What triggers an AI analysis, and who consents to sending data? | Automatic after enrichment; on demand per scan; hybrid (latest scan automatic, history on demand); with or without per-organisation opt-in and back-fill |
| D11 | How are the non-PR improvements tracked? | Keep in this spec; one follow-up PR; a Linear epic with one issue per improvement |

## User stories

1. As a maintainer, I want every design choice in PR #144 turned into a recorded decision, so
   that the codebase does not carry choices nobody approved.
2. As a maintainer, I want an ADR for the AI analysis agent, so that the provider and the data
   boundary are explicit and reviewable.
3. As an operator, I want scan results to stay fully visible when the AI analysis is off or
   fails, so that the AI never blocks my work.
4. As a security-conscious organisation, I want to know what network data leaves the product
   for AI analysis, so that I can accept or refuse it.
5. As the teammate who wrote the PR, I want each kept, changed, or removed part explained, so
   that I understand the process for the next PR.
6. As a future agent or developer, I want the docs and the code map to match the merged code, so
   that I do not build on stale information.

## Acceptance criteria (verifiable)

### PR #144 (merge gate)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Baseline recorded | The branch contains current main | Phase 0 runs | The spec records the tested commit and each gate result, including the backend passed/skipped counts |
| Review complete | Phase 0 is done | The code review runs on the whole PR | A findings list exists, each finding with severity, part (1–4), location and PR or Epic scope |
| Scope decided | Findings are recorded | Phase 2 ends | Every PR-scoped row has a chosen option, a reason, the approving maintainer and a date |
| Page never waits for AI | AI is configured | An operator opens a completed scan | Vulnerabilities and machines render from the scan request alone; no AI job starts; the AI area shows only `Explain this scan` |
| Explain on request | No analysis exists for the scan | Any member presses `Explain this scan` | One job is created; the button disappears for that scan; the card shows a pending state with bounded polling; no other scan gets a job |
| No second request | The scan has a pending, processing or completed analysis | Anyone calls `POST /scans/{id}/analysis` | HTTP 409; no new job; the UI shows no button |
| AI outside enrichment | A provider call hangs until its timeout | The worker runs | Enrichment jobs and the command sweep keep completing on their own loop |
| Production schema current | PR #144 is deployed | The API and worker start | The hosted database is at the Alembic head before the services restart; no `UndefinedColumn` errors in Railway logs |
| No automatic jobs | AI is configured | A scan completes, or the worker starts with old completed scans | No analysis job is created without a button press |
| AI disabled | `AI_ENABLED` is false or the key is blank | An operator opens a completed scan | All results show; no AI card, no error, no provider call |
| AI provider fails | The provider errors or times out | The job ends | All results show; the card shows a failed state and offers `Explain this scan` again; no partial analysis is shown |
| English output | A provider response is accepted | The card renders | The prose is English |
| Cleanup applied | Phase 4 ends | The diff is read | `AI_PROVIDER` is gone; `.env.example` has no stale comment; no new explanatory docstrings remain in the AI files |
| Roadmap states our decisions | ADR-020 is accepted | `docs/roadmap/AI.md` is read | It describes the merged feature and the Epic target decisions (D1–D3, D5, D8–D11) and does not contradict `SECURITY.md` |
| Industrial UI compiles | D6 applies | Frontend typecheck runs | No errors; no process values rendered |
| Migration graph from main | A database is at main's head `20260912_23` | `alembic upgrade head` runs | It succeeds with no manual version edits; revision ids are unique; main's revision files are unchanged (DMI-160; covered by `test_alembic_single_head.py` and the full suite) |
| Import removed | D4 | The branch is read | No import command, tests or docs remain |
| Overlap resolved | D5 and D6 are decided | Linear is read | DMI-157 linked; DMI-120 keeps `last_error` truncation and is related to DMI-164 |
| Epic opened | D11 | Linear is read | The epic exists with one validated issue per Epic-scoped row, each linking this spec |
| Backend gate | Phase 5 runs with the test database up | The backend suite runs | It passes with zero skipped tests, and lint reports no errors |
| Frontend gate | Phase 5 runs | Lint, typecheck, tests, and build run | All pass |
| Contract fidelity | Phase 5 runs | The API contract is compared to the routes and the generated frontend types | No drift |
| Docs synced | Phase 6 runs | Docs sync runs | The setup guide lists every AI and enrichment setting; the code map lists the new modules and route; no drift is reported |
| No temporary code | Phase 4 ends | The diff is reviewed | No stopgap remains except what an epic issue owns |
| Merge ready | Phases 0–6 are done | The PR is read | Its description lists the decisions and their scope, links ADR-020 and the epic, and says "Fixes DMI-158" and "Fixes DMI-160" |

### Epic target (moved to epic issues; not a PR #144 gate)

| Scenario | Then |
|----------|------|
| Data boundary enforced (D2) | The provider request contains only allow-listed public facts and placeholders (verified by a test) |
| Provider switched (D1) | Requests go to OpenAI Luna via Responses with strict output and `store=false`; Groq adapter removed |
| Prompt injection contained (D8) | Untrusted text cannot select tools or change policy; invisible characters stripped at ingest and render; outputs with unknown placeholders, safety claims or schema errors are rejected; KEV-listed vulnerabilities cannot be ranked below their computed band |
| Large scan bounded (D3) | Findings split into token-bounded stateless tasks; synthesizer sees only validated results; coverage reported |
| Writing skill enforced (D9) | Linter rejects banned patterns, retired vocabulary, safety claims and long sentences; one repair attempt |
| All enrichment sources retry (D5) | NVD, KEV and EPSS retry independently; failed sources stay `unknown`; partial risk explicit; open page refreshes on late success |
| Solution research (D8 research stage) | For each vulnerability the assistant returns ranked solution records from allow-listed sources, easiest first, with validated source links and no customer data in any query |

## Out of scope

- New AI features beyond what PR #144 already contains (chat assistant, downloadable reports,
  Home summary described in the rewritten roadmap).
- Rebuilding any part the decisions remove or defer — those become new issues.
- Every Epic-scoped decision (D1 provider switch, D2, D3 pipeline and worker, D5 per-source
  retries, D8, D9, web research). They are built in epic issues, not in PR #144.
- Changes to the Raspberry Pi agent.
- Formatting unrelated backend files.
- Reworking the earlier accidental merge and revert history.

## Decision log

Filled in during Phase 2. One row per decision.

### Scope split (decided 2026-09-13, Guilherme Ronca)

PR #144 keeps its author's features. It merges with the smallest set of changes that make it
work and meet the project gates. The review decisions that improve the AI become issues under a
new Linear epic, so each improvement is reviewed on its own and the author can take part in it.
The project has no customers yet, so the as-built AI data boundary is accepted until the epic
issue for D2 lands.

Each row below states its **scope**: **PR** (done or required in PR #144) or **Epic** (target
design for a follow-up issue; not built in PR #144).

| ID | Scope | Decision | Reason | Approved by | Date |
|----|-------|----------|--------|-------------|------|
| D1 | PR: keep Groq · Epic: OpenAI | **PR #144 keeps the Groq adapter and `openai/gpt-oss-120b` as built.** Epic target: OpenAI `gpt-5.6-luna`, `reasoning.effort=medium`, `POST /v1/responses`, strict structured output, `store=false` (OpenAI does not keep the response object; abuse-monitoring logs are still kept up to 30 days unless the organisation has Zero Data Retention; API data is not used for training by default — [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)). The epic issue replaces the adapter rather than adding a second one. Mauá's institution-hosted Qwen server is not the first choice. | Keeping the author's working adapter lets PR #144 merge now. Luna is the maintainer-selected target; [model docs](https://developers.openai.com/api/docs/models/gpt-5.6-luna) confirm medium reasoning, structured outputs and web search. | Guilherme Ronca | 2026-09-12, scope 2026-09-13 |
| D2 | Epic | **Target: no customer-identifying or raw customer data leaves the backend.** The provider receives aggregate counts and public vulnerability facts (CVE, CVSS, EPSS, KEV) tied only to request-local placeholders (`machine_1`, `finding_1`); never IPs, subnets, organisation data, internal UUIDs, hostnames, MAC, vendor/OS identity, raw evidence, banners or account/share names. The backend validates placeholders and substitutes real values locally. **PR #144 keeps the context as built** (it sends subnet, host IP and evidence). | No customers yet; the full placeholder design is a larger change best done as its own issue. | Guilherme Ronca | 2026-09-12, scope 2026-09-13 |
| D3 | PR: own loop, no auto jobs · Epic: pipeline | **PR #144:** AI never runs automatically; a job exists only after an `Explain this scan` request (D10). **AI runs outside the enrichment loop:** the worker process starts a separate AI loop (own thread, own database session, own sleep) so enrichment (scoring vulnerabilities with NVD/KEV/EPSS and calculating risk) and the command sweep never wait for a provider call. Scan pages never wait for AI. **Epic target:** bounded stateless child tasks feed a synthesizer that sees only validated structured results; explicit coverage. | Enrichment is a separate job: it fetches scores from the providers and calculates risk. A slow AI call must not delay it. A thread in the existing worker service needs no new Railway service. | Guilherme Ronca | 2026-09-12, scope 2026-09-13 |
| D4 | PR (done) | **Remove** the local scan import command, its tests and its docs. | The end user only knows the web app. A file-import path has no user. | Guilherme Ronca | 2026-09-12 |
| D5 | PR: keep · Epic: per-source | **PR #144 keeps the author's NVD retry design as built.** Epic target: NVD, KEV and EPSS each retry temporary failures independently; failed sources stay `unknown`, never `kev=no` or EPSS `0.0`; partial risk is explicit; risk is recomputed on late success and an open page refreshes (see "D5 partial-enrichment behaviour"). | His retries work for the common NVD case. The per-source model is a separate improvement. | Guilherme Ronca | 2026-09-12, scope 2026-09-13 |
| D6 | PR | **Merged PR #145/main wins.** The duplicate industrial backend stays removed, and the industrial web screens use main's `IndustrialServiceView`. | Required for the frontend to compile (F1). PR #145 owns the approved persistence design. | Guilherme Ronca | 2026-09-12 |
| D7 | PR | **One PR**, including DMI-160 (Alembic graph). | One reviewed remediation PR. DMI-160 is already satisfied by the re-parented revisions. | Guilherme Ronca | 2026-09-12 |
| D8 | Epic | **Target: prompt injection is contained by architecture**, per "D8 prompt-injection architecture" below. The OWASP 2026 invisible-character stripping list is kept. | A model cannot reliably tell instructions from data; limit what a manipulated model can reach and do. Checked against the research note §8.2. | Guilherme Ronca (character list); rest proposed | 2026-09-13 |
| D9 | Epic | **Proposed target:** customer-facing AI prose follows [`WRITING-SKILL.md`](WRITING-SKILL.md), enforced by a deterministic linter. | The audience is a non-technical owner who acts on the text. | _pending_ | — |
| D10 | PR | **AI is on by default for every organisation. There is no on/off setting and no record of who enabled it.** Any signed-in member (admin or viewer) may press `Explain this scan`. Pressing it creates one analysis job for that scan, and the button disappears for that scan for everyone. The API refuses a second request for a scan that already has a pending, processing or completed analysis (HTTP 409). No automatic analysis and no back-fill. A **failed** job is not an analysis: the button is offered again and the API accepts one new request. The deployment-level `AI_ENABLED` + key stays as the operator switch (off → no card). | A button is better than automatic loading: nothing runs until someone asks, the page never waits, and one scan is analysed once. | Guilherme Ronca | 2026-09-13 |
| D11 | Epic | **Open a Linear epic "Improve AI scan analysis"** under DMI-45 with one issue per Epic-scoped row (see "Epic backlog"). Issues go through `create-issue` validation. | Improvements land in reviewable steps on top of the merged feature. | Guilherme Ronca | 2026-09-13 |

### D5 partial-enrichment behaviour (Epic target)

The existing one-job-per-source shape stays. Completion is evaluated per finding and source,
not as one all-or-nothing transaction.

| Source outcome | Stored and calculated result | Frontend and AI behaviour |
|----------------|------------------------------|---------------------------|
| All required jobs pending or running | Preserve any data already available; mark enrichment pending | Show scan findings normally and a quiet "risk information is still updating" state; AI waits |
| One or two sources succeed and others are retrying | Recompute a provisional score from available inputs with completeness `partial`; missing inputs remain null/unknown | Show the provisional risk as partial and name the pending sources; refresh after a later success; AI waits |
| One or two sources exhaust retries | Preserve successful results; mark only the exhausted sources failed/unknown; never translate absence into `kev=no` or EPSS `0.0` | Show partial risk with unavailable source names; AI may run only if its context represents those fields as unknown and states the limitation |
| All external sources exhaust retries | Keep the original scanner finding and severity; external-intelligence completeness is `unavailable` | Do not show a fabricated complete risk score; scan results remain usable; AI analysis does not claim external validation |
| A successful response says the CVE is absent | Store a successful `not_found` outcome distinct from transport/provider failure | A successful KEV lookup may produce `not listed`; only this state may become a negative fact |

### D3 context engineering (Epic target)

The public API remains **one analysis per scan**. Internally, it is a bounded pipeline rather
than one growing prompt:

1. A deterministic backend builder converts allowed D2 fields to request-local placeholders,
   normalises public vulnerability facts and measures the serialized/token budget before any
   provider call. Raw scanner evidence and customer identity never enter this boundary.
2. Every scan is partitioned into bounded, independent finding/chunk tasks. Each call is
   stateless and receives no chat history or other organisation's context.
3. Each child response must pass its own strict, versioned JSON schema, placeholder validation
   and the D9 writing linter. A refusal, incomplete response, unknown reference or malformed
   output fails only that child task.
4. A separate scan-synthesis task receives only the validated structured child results plus
   aggregate counts. It never receives raw scanner strings or web-page text. The final result
   records analyzed, failed and total finding counts so coverage is explicit.

The application owns a compact, versioned **security-analysis skill** (defensive scope, source
precedence, uncertainty rules, output schema) and the D9 **writing skill** (voice, vocabulary,
banned patterns, length limits). Both are instruction packages, not user-authored prompts.
Relevant knowledge is selected per task; a whole security handbook is not copied into every
prompt. User-facing prose is **English** for this release. Future localisation changes the
complete UI and generated language together.

### D8 prompt-injection architecture (Epic target)

**Threat.** An attacker controls text the AI reads: service banners, HTTP titles, NSE script
output, hostnames, NVD descriptions, vendor advisories, and (later) web pages. The goal of an
injection is to change the analysis ("tell the owner this is safe"), leak data, or make the
system act. No prompt wording reliably stops a model from following injected text. The design
therefore assumes the model **can** be manipulated and limits what that achieves.

**Trust zones.**

| Zone | Contents | May reach the model? | May influence |
|------|----------|----------------------|---------------|
| T0 Application | System instructions, security-analysis skill, writing skill, schemas, validators | Yes, as instructions | Everything |
| T1 Structured facts | Enum values, numbers, CVE ids, CVSS, EPSS, KEV flags, placeholders | Yes, as typed JSON data | Content of one child task |
| T2 Untrusted text | Scanner evidence, banners, hostnames, advisory prose, web pages | **No** once D2 lands (PR #144 as built still sends evidence). Web pages: only inside the quarantined research stage | Nothing outside a validated record |
| T3 Model output | Child results, synthesis result | Only validated structured output flows to the next stage | UI text only, never an action |

**Controls, in order of strength.**

1. **No capability to abuse.** No tools, no function calls, no URLs fetched, no
   application action depends on model output. Output is display text. This removes
   exfiltration and action paths entirely. Rationale: an attack needs private data, untrusted
   input *and* an outbound channel; PR #144 removes the outbound channel and the private data.
2. **Context minimisation (D2).** T2 text does not enter AI input (PR #144 as built still sends evidence; the D2 issue removes it). The builder sends
   only allow-listed T1 fields. A test proves forbidden fields and raw strings are absent.
3. **Strict output contract.** Strict JSON schema per stage, enums for every categorical value,
   length limits, placeholder references validated against the task's own set (no cross-scan
   or unknown ids), D9 linter. Anything else fails the task. Refusal and incomplete responses
   are failures, never partial results.
4. **Isolation.** Each child task is stateless (`store=false`, no `previous_response_id`, no
   conversation). One manipulated child cannot see or change another. The synthesizer sees only
   validated T3 records.
5. **Safe rendering.** The frontend renders AI text as plain text (React text nodes, no
   `dangerouslySetInnerHTML`, no markdown renderer, no auto-linking). Links come only from
   validated placeholders mapped by the backend.
6. **Priority computed in code (Claim-Check-Act).** The backend computes action order and a
   minimum priority band from KEV, EPSS, CVSS and risk score. Output that omits a KEV-listed
   vulnerability or ranks it below its band is rejected. This is the only control against a
   manipulated model understating a risk (OWASP LLM07:2026 Misinformation).
7. **Data, not instructions (probability control, not a boundary).** T1 data travels as a JSON
   value in a separate input item, never concatenated into instruction text. Strings are
   length-bounded and stripped of tag-block (U+E0000–E007F), variation selector (U+FE00–FE0F),
   zero-width (U+200B–U+200D, U+2060) and control characters at ingest **and** before render.
   NFKC alone does not remove these. This lowers the success rate of simple attacks only.
8. **Audit and detection.** Store versions, context hash, validation failure codes and linter
   codes per task. A spike in `invalid_analysis` or `style_violation` for one scan is visible.

**Future web research: a solution-finding assistant (Epic, not in PR #144).** The goal is not a
CVE lookup. The agent acts as an assistant: for each vulnerability it looks for ways to fix it
and ranks them from the easiest to the hardest for a non-technical owner (for example a setting
change before a firmware update, an update before a hardware replacement). The model plans its
own searches. Security comes from what the research stage can see and what its output can do:

- **Planner and reader are one quarantined model call** with the web-search tool. Its input is
  public facts only: CVE id, affected product and version range from the CVE record, service
  type, severity, KEV/EPSS. No placeholders, no machine names, IPs, organisation or scan data.
  Whether the scanner-observed product version may be sent is an open question for the D2 issue
  (it helps find the exact fix but is observed customer data).
- **Queries are checked in code before the call is accepted as valid:** the tool's returned
  `web_search_call` actions are logged and rejected if they contain an IP, MAC, hostname,
  placeholder, organisation name or any string from the scan that is not a public fact.
- **Sources:** vendor security advisories and knowledge bases, official product documentation,
  CVE.org, NVD, CISA KEV and advisories first. Open sites (forums, Q&A, user-content hosts such as
  `github.com`) are not in the first version's allow-list, because the domain filter admits
  subdomains and these hosts carry attacker-written text. Tool calls per task are capped.
- **Output is a strict solution record**, one per option: `effort` enum (`setting_change`,
  `update`, `workaround`, `replace`, `ask_vendor`), `requires` enum (owner, IT person, vendor),
  short `steps` text (≤ 3 items, writing-skill linted), `fixes_fully` boolean, `source_urls`
  (each must be in the tool's returned sources **and** on the allow-list). Feed values (KEV,
  EPSS, fixed version from NVD/CSAF) win on conflict.
- **Web-derived text is untrusted even after validation.** Steps are rendered as plain text,
  labelled with their source link, and never become an application action. The assistant never
  touches the customer's network.
- **Analysts and the synthesizer receive solution records, never page text.** The easiest valid
  option per vulnerability feeds "What to do first".
- **Cache per CVE and product**, shared across organisations, with a TTL; research contains no
  customer data, so it needs no per-organisation trigger beyond the D10 button.
- No stage combines untrusted web text, private data and an outbound channel (Rule of Two).

**Tests required.** Adversarial scanner strings (instruction text, fake JSON, fake placeholders,
Unicode tricks) are proven absent from the provider request; responses that cite unknown or
cross-scan placeholders, certify safety, contain HTML/markdown/URLs, or break the schema are
rejected; refusal and incomplete responses produce the failed state; the frontend renders a
`<script>` string as text.

Not controls: prompt warnings, delimiters and injection classifiers. Adaptive attacks bypass
them (Nasr et al. 2025, research note §2.5). They may exist as telemetry, never as a claimed
defence. ADR-020 cites OWASP LLM Top 10 **2026** ids (LLM01, LLM02, LLM03, LLM06, LLM07, LLM10)
and Agentic ASI06/08/09.

Checked against `docs/research/ai-scan-analysis-agent-web-research-and-trigger.md` §8.2 on
2026-09-13; its changes are applied above. ADR-020 records the approved form.

## Epic backlog (D11)

Created 2026-09-13 as **DMI-161 [Epic] Improve AI scan analysis**. The PR #144 author is invited
to own or co-own issues. E3 (AI outside the enrichment loop) moved into PR #144.

| # | Linear | Issue | Decisions / findings | Blocked by |
|---|--------|-------|----------------------|------------|
| E1 | DMI-162 | Send only public facts and placeholders to the AI provider | D2; P5, P18 | DMI-158 |
| E2 | DMI-163 | Switch the AI provider to OpenAI GPT-5.6 Luna on the Responses API | D1; P11 | DMI-158 |
| E4 | DMI-166 | Split large scans into bounded AI tasks with a synthesizer and coverage | D3 | DMI-162 |
| E5 | DMI-167 | Contain prompt injection in AI analysis | D8 | DMI-162 |
| E6 | DMI-168 | Enforce a writing skill for AI prose (needs grooming: soft rules) | D9; A13 | DMI-163 |
| E7 | DMI-164 | Retry KEV and EPSS like NVD and keep failed sources unknown | D5; F3, F4 | DMI-158 |
| E8 | DMI-165 | Refresh an open scan page when enrichment finishes later | D5; F2 | DMI-164 |
| E9 | DMI-169 | Research assistant that finds the easiest fix (needs grooming: product version) | D8 research stage; F5 | DMI-162, DMI-163, DMI-167 |
| E10 | DMI-170 | AI overview card design follow-ups (needs grooming: card position) | DESIGN A4–A12, Q1 | DMI-158 |

P9 (`last_error` truncation) stays with DMI-120, which is related to DMI-164.

## Integration status

- `origin/main` commit `0333077` was merged at `4ab33eb`; it is an ancestor of the current
  branch. The merge base is that same `origin/main` commit, so a rebase would only rewrite
  history and is not required.
- Work happens on local branch `feature/dmi-158-review-pr-144`. PR #144's head is still
  `origin/feature/ia-implementation` at `7997383`; the local branch is 58 commits ahead and not
  pushed. PR #144 does not contain any fix below until that push happens.
- The migration graph has one head, `20260912_25`: main's `20260912_20`…`20260912_23` files are
  unchanged, AI is `20260912_24` (down `20260912_23`) and enrichment retries are `20260912_25`
  (down `20260912_24`).
- **Production database (2026-09-13).** Railway runs main `0333077`, but the hosted database is
  at `20260907_20`. The other branch of the graph (`20260903_18` nspi options, `20260908_19`
  operating system, merges `20260912_20`/`_21`/`_23`, industrial `20260912_22`) was never applied,
  so the API logs `UndefinedColumn` for `hosts.operating_system_json`,
  `scan_hosts.operating_system_json` and `commands.nspi_options`. Reproduced on `dmitri_test`:
  `alembic upgrade 20260907_20` then `alembic upgrade head` applies every missing revision and
  reaches `20260912_25`. Every added column is nullable, so existing rows are safe. Migrations are
  operator-run by design (`docs/cloud/railway/SETUP.md` forbids `DATABASE_URL_DIRECT` on Railway),
  so the fix is the runbook step, `HUMAN_INFRA_REQUIRED`: upgrade the hosted database to head
  before the PR #144 deploy restarts the services.
- **DMI-160 (in this PR).** The issue asks for a rebase; the merge above gives the same graph
  without rewriting history, so it is accepted. Existing `test_alembic_single_head.py` and the
  full backend suite cover it; no new test is added. Open question for the teammate: was the old
  PR head (`20260912_21` AI, `20260912_22` enrichment) ever applied to a shared database? Such a
  database needs a manual `alembic stamp` (`HUMAN_INFRA_REQUIRED`). DMI-160 has no validation
  stamp in Linear (`status:needs-grooming`).
- D4 is applied: the local import module, console script, tests and documentation are removed.
- D6 is only partly applied: the duplicate backend persistence is removed, but the industrial
  frontend still consumes the old ingest payload types and fails typecheck against main's read
  contract.
- Phase 0 remains incomplete until the backend and frontend gate results are recorded.
- Phase 1 findings are recorded below. Phase 4 remediation and later gates have not completed.

## Confirmed Phase 1 findings

Independently re-reviewed on the post-merge branch on 2026-09-12. "Resolved" means the
specific review finding is already closed by the current branch; it does not imply that its
whole part is complete.

| ID | Severity | Part | Location | Confirmed result | Required disposition |
|----|----------|------|----------|------------------|----------------------|
| P1 | Blocker | 1–3 | `alembic/versions/20260912_24_ai_scan_analyses.py`, `20260912_23_merge_industrial_and_inventory.py` | **Resolved.** The duplicate `20260912_21` revision was renamed and re-chained. Tracked as DMI-160. | Keep `test_alembic_single_head.py` green. |
| P2 | Blocker | 3 | `alembic/versions/20260912_25_enrichment_retries.py` | **Resolved.** The enrichment revision is unique and Alembic reports one head. | Keep the migration-chain test green. |
| P3 | High | 1 | `schemas/read.py:55-93`, `services/read.py:553-611` | **Resolved in backend.** Main's value-minimised industrial read model replaced the branch JSON model. F1 tracks the incomplete frontend adaptation. | Close with D6 after F1. |
| P4 | High | 2 | `services/ai/jobs.py:67-115` | **Confirmed.** Enabling AI still selects all organisations and back-fills historical completed scans without an organisation consent check. | **PR.** Fixed by D10: remove automatic enqueue and back-fill; jobs only from `Explain this scan`. |
| P5 | High | 2 | `services/ai/schemas.py:23-65`, `services/ai/context.py:64-108` | **Confirmed.** Real scan/finding/host ids, IP, subnet, raw evidence and references still enter provider context, contrary to D2. | **Epic E1.** |
| P6 | Medium | 2–3 | `services/worker.py:51-84`, `services/nvd.py:60-68` | **Confirmed.** AI calls share the enrichment worker loop; NVD sleeps and performs HTTP while holding its lock. | **PR** (AI loop separate from enrichment, D3). NVD sleep inside the lock: **Epic E7 (DMI-164)**. |
| P7 | Medium | 2 | `services/ai/prompts.py:3-12`, `ScanAIAnalysis.tsx:50-203` | **Confirmed.** Generated prose is pt-BR while the surrounding UI is English. | **PR.** Change the prompt language line to English. Writing skill is Epic E6. |
| P8 | Medium | 2 | `services/ai/read.py:47-56`, `ScanAIAnalysis.tsx:13-43` | **Confirmed.** A missing job is reported as `pending`, causing unbounded three-second polling. | **PR.** With D10, no row means `not_requested` (button), not `pending`; polling runs only while a job exists and is bounded. |
| P9 | Medium | 3 | `services/enrichment.py:138-148` | **Confirmed.** Generic exceptions persist unbounded `str(exc)` into `last_error`. | **DMI-120** (unchanged scope; related to DMI-164). |
| P10 | Medium | 4 | `backend/pyproject.toml`, `src/api/management/` | **Resolved.** The import entry point, implementation, tests and docs are gone. | Close with D4. |
| P11 | Low | 2 | `services/ai/groq.py:100-110` | **Confirmed.** HTTP 400/422 responses remain retryable. | **Epic E2 (DMI-163)** (new adapter's error map). |
| P12 | Low | 2 | `core/config.py:26`, `services/ai/factory.py:16-27` | **Confirmed with corrected wording.** `AI_PROVIDER` is stored as metadata but never selects an adapter; the factory always creates Groq. | **PR.** Remove the `AI_PROVIDER` setting; store the provider name as a constant. |
| P13 | Low | 2 | `backend/.env.example:3-8` | **Confirmed.** The provider-credential comment contradicts the committed Groq settings below it. | **PR.** Remove the stale comment. |
| P14 | Low | all | `services/ai/*.py`, `schemas/read.py:260` | **Confirmed.** New explanatory docstrings conflict with the repository convention recorded by this spec. | **PR.** Remove the branch-added docstrings in `services/ai/*.py` and `schemas/read.py`. |
| P15 | Low | docs | `specs/047-pr-144-review-remediation/` | **Resolved.** Spec number 047 is unique. | None. |
| P16 | Low | docs | `docs/adr/ADR-019-v2-active-scanning-and-agent-hardening.md` | **Resolved as numbering.** ADR-019 is occupied, making ADR-020 the next AI ADR; ADR-020 itself is still missing. | **PR.** Create and accept ADR-020 in Phase 3. |
| P17 | Info | docs | `docs/roadmap/AI.md:19-56` | **Confirmed.** The branch replaces the approved roadmap with Groq, Home, chat and report choices without an ADR. | **PR.** Rewrite `docs/roadmap/AI.md` to state the decisions in this spec (merged feature + epic targets); chat, reports and Home summary stay undecided. |
| P18 | Info | 2 | `tests/test_ai_context.py:9-81` | **Confirmed.** Tests do not pin exact allowed keys or prove forbidden values absent. | **Epic E1.** |
| F1 | Blocker | 1 | `IndustrialServices.tsx:3-113`, `HostDetail.tsx:60`, `ScanIndustrialServices.tsx:31`, `industrialFixtures.ts` | Main returns `IndustrialServiceView`, but the UI and fixtures still use `ModbusTcpServicePayload` and removed raw-value/validation fields. `npm run typecheck` fails with 14 errors; `unit.validations.length` can also crash at runtime. | **PR.** Adapt the component, both callers, fixtures and tests to `IndustrialServiceView`. Copy changes beyond compiling are Epic E10 unless trivial. |
| F2 | Medium | 3 | `services/enrichment.py:259,293,322`, `ScanDetail.tsx:35-39`, `FindingPanel.tsx:44-55` | Risk snapshots update asynchronously, but an already-open Scan Detail does not refetch or receive invalidation, so it can keep showing stale `Not calculated` risk until reload. | **Epic E8.** |
| F3 | Medium | 3 | `services/enrichment.py:116-148`, `services/kev.py:44-49`, `services/epss.py:44-49` | Retry classification covers `NvdTemporaryError` only; KEV/EPSS 429, 5xx, timeout and transport failures enter the permanent generic-failure path. | **Epic E7.** |
| F4 | Medium | 3 | `services/nvd.py:75-86` | NVD rate-limit-style HTTP 403 is not classified as temporary. | **Epic E7.** |
| F5 | Info | 2 | `services/ai/prompts.py:3-20`, `services/ai/groq.py:35-58` | The current provider contract is a context-only completion and has no search/tool path. | **Epic E9.** |

Review checks run during confirmation:

- `uv run ruff check src tests`: passed.
- `npm run lint`: passed.
- `npm run typecheck`: failed with the 14 D6 errors in F1.
- `uv run alembic heads`: one head, `20260912_25`.

These are review evidence, not the complete Phase 0 or Phase 5 gate: the real-database backend
suite, frontend tests/build and generated-contract no-diff check are still required.

## Gate results

Recorded 2026-09-13 on `feature/dmi-158-review-pr-144` at `6bd40cf` plus the uncommitted
Task 1–5 working tree.

| Gate | Result |
|------|--------|
| `uv run alembic heads` | `20260912_25 (head)` |
| `cd backend && uv run ruff check src tests` | passed |
| `DATABASE_URL_TEST=... uv run pytest` | 1290 passed, 0 failed, 0 skipped, 445 warnings |
| `cd frontend && npm run gen:types` | regenerated `openapi.d.ts` in line with the Task 1 contract |
| `npm run lint` | passed |
| `npm run format:check` | passed |
| `npm run typecheck` | passed (0 errors) |
| `npm test` | 70 files, 653 passed |
| `npm run build` | passed |

## Related specs

- Implementation: `ARCHITECTURE.md`, `DESIGN.md`
- AI decision evidence (historic, pre-decision): `AI-DECISION-BRIEF.md`
- D9 writing rules: `WRITING-SKILL.md`
- D8/D10 research: `docs/research/ai-scan-analysis-agent-web-research-and-trigger.md` (its D10 hybrid recommendation was not chosen)
- Linear: DMI-160 (Alembic graph), DMI-157 / PR #145 (industrial persistence), DMI-120 (enrichment errors)
