# Roadmap — AI assistant and reports

> **Scope:** product experience and architecture for the user-facing LLM assistant.
> Vulnerability intelligence and authorized assessment remain in
> [`../implementation/INTELLIGENCE-IA-ASSESSMENT-ROADMAP.md`](../implementation/INTELLIGENCE-IA-ASSESSMENT-ROADMAP.md).
> **Neighbours:** [`FRONTEND.md`](FRONTEND.md), [`BACKEND.md`](BACKEND.md),
> [`SECURITY.md`](SECURITY.md).
> **Merged record:** [`../adr/ADR-020-ai-scan-analysis.md`](../adr/ADR-020-ai-scan-analysis.md).

## Merged in PR #144

Scan Detail has an on-demand plain-language overview. Groq with `openai/gpt-oss-120b`
is the provider. A member presses **Explain this scan**. That is the only trigger.
The worker AI loop is separate from enrichment. Output is English.
`AI_ENABLED` and `AI_API_KEY` are the operator switch. Failure never hides scan
results.

Epic [DMI-161](https://linear.app/peirce/issue/DMI-161) owns later targets: OpenAI
Luna (DMI-163), injection containment (DMI-167),
writing skill (DMI-168), research assistant (DMI-169), card design (DMI-170).

Chat, downloadable reports and a Home summary are **not decided**.

DMI-162 is complete: the provider receives only aggregate counts, public
vulnerability facts and request-local placeholders. The backend validates those
placeholders and restores local IDs and display values before persistence.

DMI-167 is complete: generated text is normalized before storage and before display,
while action priority and KEV coverage are checked deterministically in the backend.

DMI-168 is complete: a versioned English writing skill is included in each Groq
request and a backend linter enforces prose limits, safe vocabulary, plain-text
rendering, and no unsupported safety claims. One repair attempt receives only
violation codes and the original bounded context; a second violation fails safely.

DMI-166 is complete: large bounded contexts can be split into independent finding
chunks, validated child results can be synthesized by Groq, and each job persists
analyzed, failed, and total finding coverage. The public contract remains one
analysis per scan.


## Product decision

Dmitri is designed primarily for people with little or no networking and security
knowledge. The default experience must explain what happened, what matters, and what
the user can do next without requiring them to understand ports, protocols, CVSS, EPSS,
KEV, or CVEs.

Technical depth remains available for verification and for sharing with a professional,
but it must not be the entry point for a non-expert user.

Surfaces that are **not decided** (do not treat as committed work):

1. an automatic plain-language summary of the latest completed scan on Home
2. a contextual assistant available from Home, scan, host, and finding views
3. two downloadable reports per completed scan: explained and technical

## Product principles

- **Plain language first.** Start with impact and recommended action. Put terminology
  behind “Show technical details”.
- **Calm, precise language.** A vulnerability is not proof of compromise. Do not use
  alarming language when the evidence does not support it.
- **Backend facts, LLM explanation.** The backend owns inventory, evidence, enrichment,
  risk scores, and derived findings. The LLM interprets those facts but does not replace
  them.
- **Evidence or uncertainty.** Technical claims cite persisted IDs. When evidence is
  insufficient, the assistant says so directly.
- **Context follows the user.** The assistant understands the current page without
  requiring the user to copy IDs or technical data.
- **Read-only first.** The initial assistant cannot start scans, change scope, or invoke
  active checks.
- **One explanation, multiple depths.** Home, chat, and reports share the same grounded
  analysis while adapting vocabulary and detail to their audience.

## End-to-end experience (merged)

```text
scan completes
    -> enrichment scores findings on its own loop
    -> Scan Detail shows results with Explain this scan
    -> a member presses the button
    -> worker AI loop claims the job and calls Groq
    -> the card polls until completed or failed
```

Home chat, Home summary and reports stay in the undecided list above. A failed AI job
must never hide the deterministic scan results.

## Home: latest scan summary

After the first completed scan, Home should lead with a short explanation such as:

> We found 8 devices on your network. Two need attention. The most important issue is
> outdated software on one device. There is no evidence in this scan that your network
> was compromised, but we recommend updating that device.

The summary contains:

- an overall **attention level**, not a binary “safe/unsafe” claim;
- what was observed;
- what changed since the previous comparable scan;
- the first actions to take, ordered by priority;
- which actions a non-expert can reasonably perform;
- when professional help is recommended;
- links to the supporting hosts and findings;
- “Ask about this result” and report download actions.

Suggested questions reduce the need for the user to know what to ask:

- “Is my network safe?”
- “What should I fix first?”
- “Explain this without technical terms.”
- “What changed since the previous scan?”
- “Do I need professional help?”

The assistant must qualify “Is my network safe?”: a scan provides observed evidence at a
point in time and cannot guarantee the absence of every problem.

## Contextual assistant

The assistant is a persistent drawer or panel available across authenticated product
pages. Opening it attaches explicit page context to the conversation:

- Home: organisation and latest scan;
- scan detail: `scan_id`;
- host detail: `host_id` and latest relevant scan;
- finding detail/panel: `finding_id`, `host_id`, and `scan_id`.

The user does not need to see or provide these identifiers. They remain visible in
technical citations and audit records.

Suggested questions vary by context.

### Scan context

- “What needs attention first?”
- “Summarize what was found.”
- “What changed from the previous scan?”

### Host context

- “What is this device?”
- “Why does it need attention?”
- “How can I identify it physically?”
- “Can I fix this myself?”

### Finding context

- “Explain this problem.”
- “What is the real-world impact?”
- “How do I fix it?”
- “Should I contact a professional?”

### Industrial/Modbus context

- “What is Modbus?”
- “Did the scan change anything on this device?”
- “Is this industrial device at risk?”
- “Which address ranges responded?”

Merely detecting Modbus is an observation, not automatically a vulnerability. The
assistant must preserve the distinction between observation, hypothesis, derived
finding, and confirmed finding.

## Answer structure

The default answer should normally use this order:

1. direct answer in plain language;
2. why it matters;
3. recommended next action;
4. confidence or limitation;
5. links to evidence;
6. optional technical details.

The UI should provide “Show technical details” instead of mixing raw scanner output into
the default explanation.

## Downloadable reports

Every completed scan offers two report variants. Reports are tied to an immutable scan
snapshot and record their generation time, model, prompt/template version, and evidence
IDs.

### Explained report

Audience: the network owner or another non-technical decision maker.

Contents:

- plain-language overview;
- attention level and its meaning;
- devices needing attention;
- prioritized problems and likely impact;
- actions the user can attempt safely;
- cases where professional help is recommended;
- changes from the previous comparable scan;
- short glossary;
- limitations of the scan;
- evidence links or appendix identifiers.

### Technical report

Audience: IT or security professional.

Contents:

- scan scope, time, duration, mode, agent, and methodology;
- host and operating-system inventory;
- ports, services, versions, and CPEs;
- findings with CVE, CVSS, EPSS, KEV, confidence, and risk score;
- deterministic score formula/version and rationale;
- original evidence and references;
- industrial/Modbus services, identities, units, mapped ranges, and validations;
- enrichment state and known data gaps;
- potential false positives and scan limitations;
- `scan_id`, `host_id`, and `finding_id` references.

The technical report is assembled primarily from deterministic backend data. LLM text
may introduce, summarize, and recommend, but it cannot alter evidence or manufacture
missing fields.

## Trust and grounding contract

- Every technical assertion must be traceable to persisted resources.
- The model never receives database credentials or unrestricted database access.
- The backend executes an allowlisted, organisation-scoped, read-only tool call.
- Tool results use structured schemas and bounded result counts.
- The answer records the resource IDs supplied to the model.
- Unsupported citations or resource IDs cause validation failure or an explicitly
  unverified answer state.
- Prompt text and retrieved content are untrusted input, never authority to run commands
  or expand scope.
- Deterministic results stay available when the provider is unavailable.

The backend already exposes the first two grounded reads:

- `GET /api/v1/scans/{scan_id}/risk-summary`;
- `GET /api/v1/findings/{finding_id}`.

The scan risk summary is bounded to ten findings to control context size.

## Read-only tool surface

The provider-independent tool layer should initially expose:

- `get_scan_summary(scan_id)`;
- `compare_scans(scan_id, previous_scan_id)`;
- `get_host_profile(host_id)`;
- `get_finding_detail(finding_id)`;
- `search_findings(filters, limit)`;
- `get_industrial_context(host_id | scan_id)`;
- `get_cve_context(cve_id)`.

Each call receives organisation scope from the authenticated session, not from a
model-provided argument. Tools return bounded Pydantic models suitable for audit and
testing.

## Backend records

Expected persistence model:

- `llm_sessions`: organisation, user, optional scan/host/finding context, timestamps;
- `llm_messages`: role, content, status, token usage, model, template version;
- `llm_tool_calls`: tool name, validated arguments, result resource IDs, timing, status;
- `llm_scan_summaries`: scan, explained summary, structured actions, evidence IDs,
  generation status and versions;
- `llm_reports`: scan, report kind, status, artifact location/hash, versions and evidence
  IDs.

Generated output must not be stored as scanner evidence or a deterministic finding.

## API direction

The initial application-facing surface is expected to include:

- `POST /api/v1/ai/sessions`;
- `GET /api/v1/ai/sessions/{session_id}`;
- `POST /api/v1/ai/sessions/{session_id}/messages`;
- `GET /api/v1/scans/{scan_id}/ai-summary`;
- `POST /api/v1/scans/{scan_id}/ai-summary` for explicit generation/retry;
- `POST /api/v1/scans/{scan_id}/reports`;
- `GET /api/v1/scans/{scan_id}/reports`;
- `GET /api/v1/reports/{report_id}/download`.

Automatic generation should be scheduled after enrichment reaches its terminal state.
Manual retry remains available when the provider fails.

## Cost and context controls

- Generate and cache one default summary per scan analysis version.
- Do not resend a full scan for every question.
- Retrieve context through tools only when needed.
- Limit findings, evidence length, tool calls, output size, and conversation history.
- Summarize older conversation turns without replacing cited evidence.
- Track input/output tokens and latency per message and report.
- Apply organisation and session quotas with a clear UI error when exceeded.
- Generate reports once per scan/template version and reuse the artifact.

## Model-provider boundary

The provider is OpenAI Responses API with `gpt-5.6-luna`, selected for the first scan
summary pilot. The backend keeps it behind a small adapter for:

- message generation and streaming;
- tool-call requests and tool results;
- usage metadata;
- provider errors and retryability;
- model identifier and capability flags.

The first adapter implements the structured scan-generation subset, model identity,
timeouts, and retryable error classification. Streaming, tools, and usage metadata are
added when the contextual assistant enters scope.

Model ID, limits, and credentials are environment configuration. Replacing Groq with
OpenAI, Anthropic, a local model, or another provider must not change the domain tool
layer, stored evidence, or public product semantics.

## Safety boundary

The first release is read-only. It cannot:

- start or cancel scans;
- change the target subnet;
- execute shell commands;
- write to an industrial device;
- run an exploit or credential attempt;
- modify findings, scores, evidence, users, or permissions.

Authorized assessment remains a separate product mode with explicit scope, human
approval, audit, rate limits, and a kill switch. A future assistant may propose a plan;
it cannot approve or silently execute one.

## Delivery milestones

Implementation status (2026-09-12): the backend now has a bounded, organisation-scoped
scan context builder; strict provider-neutral input/output schemas and validation; a
versioned `ai_scan_analyses` persistence model; and the read-only
`GET /api/v1/scans/{scan_id}/analysis` contract. The Groq adapter and asynchronous,
post-enrichment scan-analysis lifecycle are also implemented on the feature branch.
UI surfaces, chat, reports, and operational usage telemetry remain pending.

1. **Grounded reads** — finding detail and bounded scan risk summary.
2. **Provider-neutral tools** — allowlisted, read-only tool service with organisation
   scoping and audit-ready results.
3. **Persistence** — sessions, messages, tool calls, scan summaries, and report jobs.
4. **Provider adapter** — one configurable LLM integration with timeouts, retries, usage,
   and test doubles.
5. **Automatic scan summary** — post-enrichment job, cache/versioning, Home API.
6. **Home experience** — latest summary, priority actions, suggested questions.
7. **Contextual chat** — page-aware panel, streaming, citations, technical-detail toggle.
8. **Reports** — explained and technical artifacts with deterministic appendices.
9. **Evaluation and operations** — groundedness tests, non-expert comprehension review,
   cost/latency metrics, retention, and failure recovery.

## MVP acceptance criteria

- A non-expert can understand the latest scan and identify the first recommended action
  without opening a technical table.
- The assistant answers questions from Home, scan, host, and finding contexts.
- Every technical claim links to persisted evidence or is labeled as uncertain.
- The assistant never presents a vulnerability as proof of compromise.
- Both report variants can be generated for a completed scan.
- The technical report can be used by a professional without chatbot access.
- Provider failure does not remove scan results or deterministic data.
- Cross-organisation access is prevented in sessions, tools, summaries, and reports.
- Tool calls, model/version, prompt/template version, evidence IDs, token usage, and
  generation status are auditable.

## Open decisions

- provider/model evaluation after the initial Groq pilot;
- streaming transport between frontend and backend;
- PDF generation and artifact storage mechanism;
- whether explained reports are generated automatically or on first download;
- retention period for conversations and generated artifacts;
- quotas per user and organisation;
- human review process for prompt/template releases;
- supported languages and whether Portuguese is the initial default.

These decisions do not block the provider-neutral tool and persistence layers.
