# Roadmap — AI (in-app LLM explainer)

> **Scope of *this* doc:** the **user-facing LLM** that explains findings to the end user inside
> the frontend. The **backend vulnerability-intelligence** roadmap (KEV/EPSS/NVD, scoring, the
> LLM-as-analyst architecture, authorized assessment) already exists and is **not restated here**:
> see [`../implementation/INTELLIGENCE-IA-ASSESSMENT-ROADMAP.md`](../implementation/INTELLIGENCE-IA-ASSESSMENT-ROADMAP.md)
> (the copilot is its **Phase 3B**). This file is the product/frontend-facing slice of that plan.
>
> **Neighbours:** [`FRONTEND.md`](FRONTEND.md), [`BACKEND.md`](BACKEND.md), [`SECURITY.md`](SECURITY.md).

## What the in-app explainer is

A read-only assistant that helps a non-expert operator understand their scan:

- "Explain this finding in plain language and why it matters."
- "Summarize this scan: what needs attention first?"
- "What is this CVE / is it known to be exploited?"
- Plain-language remediation suggestions, prioritized by the existing `risk_score`.

## Hard guardrails (inherited from the IA roadmap)

- **Grounded only in persisted data.** Every answer cites the `scan_id` / `device_id` /
  `finding_id` it used. No invented CVEs or correlations.
- **Read-only this phase.** The explainer **must not** trigger scans, change scope, or run active
  modules. Active/authorized assessment is a *later, separate* track (IA roadmap Phase 3C).
- **Auditable:** prompts, tool calls, and cited evidence IDs are logged.
- Conservative language templates: "observed evidence", "hypothesis", "recommendation", "confidence level".

## Architecture (per IA roadmap Phase 3B)

- The **backend** stays the authority on state; the LLM consumes structured data via a **restricted
  tool surface** the backend controls (e.g. `get_scan_summary`, `get_finding_detail`,
  `get_cve_context`, `search_findings`).
- New backend endpoints/tables (`POST /api/v1/ai/sessions`, `.../messages`,
  `POST /scans/{id}/ai-summary`, `llm_sessions/llm_messages/llm_artifacts`) — tracked in
  [`BACKEND.md`](BACKEND.md) as API surface; designed in the IA roadmap.
- **Model choice:** default to the latest capable Claude model for the explainer; keep the model id
  configurable (env), and keep the tool layer model-agnostic so it can be swapped.

## Frontend surface

A contextual panel on scan-detail and finding-detail (not a standalone page) — see
[`FRONTEND.md`](FRONTEND.md). Streams responses; renders cited evidence as links back into the
finding/device views so the user can verify every claim.

## Milestones

1. Define the minimal read-only tool surface in the backend.
2. LLM orchestration service + session/message persistence.
3. `ai-summary` per scan + per-finding explanation endpoints.
4. Frontend explainer panel with evidence citations.
5. (Out of scope here) authorized-assessment copilot — IA roadmap Phase 3C.

## Ripple

Tool/endpoint changes ripple to [`BACKEND.md`](BACKEND.md); the panel to [`FRONTEND.md`](FRONTEND.md);
data-access scope + prompt/audit logging to [`SECURITY.md`](SECURITY.md). Keep this doc and the
[IA roadmap](../implementation/INTELLIGENCE-IA-ASSESSMENT-ROADMAP.md) consistent — if they diverge,
the IA roadmap is the deeper source and this doc should link, not fork.
