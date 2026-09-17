# ADR-020: AI scan analysis

> **Status:** Accepted (2026-09-13).
> **Extends:** [ADR-005](ADR-005-security-model.md) for `AI_API_KEY` handling.
> **Does not supersede:** ADR-005's JWT and device-signature rules.

## Context

PR #144 added an optional Groq-backed analysis of a completed scan. The product
sends bounded scan context to a third-party LLM and shows a plain-language
overview in the web app. No ADR existed for that boundary. The AI roadmap still
named Claude as the default. This ADR records what merged in PR #144 and points
at the epic for later changes.

The initial implementation sent subnet, host IP and raw evidence to the
provider. DMI-162 replaces that temporary boundary with public facts and
request-local placeholders.

## Decision

### 1. Merged provider

The merged adapter is Groq with model `openai/gpt-oss-120b`. The worker stores
the provider id `"groq"` as a code constant, not as an `AI_PROVIDER` setting.
The operator switch is `AI_ENABLED` plus a non-blank `AI_API_KEY` on both the
`api` and `worker` Railway services.

### 2. Trigger

AI is on for every organisation once those variables are set. There is no
per-organisation opt-in and no record of who enabled it. Analysis starts only
when a signed-in member (admin or viewer) presses **Explain this scan**. That
creates one `pending` job for that scan. A second request for a pending,
processing or completed job returns HTTP 409. A failed job is not an analysis.
The button is offered again. Scan completion never creates a job. There is no
back-fill.

### 3. Isolation from enrichment

The worker process runs two loops. Enrichment and the command sweep stay in
`run_worker_once`. AI claims and provider calls run in `run_ai_worker_loop` on
a daemon thread with its own session and `AI_POLL_INTERVAL_SECONDS`. A hanging
provider call must not stall NVD, KEV, EPSS or risk scoring. Scan Detail never
waits on AI to render vulnerabilities or machines.

### 4. Failure never hides scan results

If AI is off, unconfigured, unavailable, pending, failed or late, the operator
still sees the full scan. The card is absent when status is `unavailable`.
English prose is required in the system prompt.

### 5. Secrets

`AI_API_KEY` follows ADR-005: never log it, never persist provider error bodies,
never put `DATABASE_URL_DIRECT` on Railway.

### 6. Provider data boundary

The provider receives aggregate scan counts and allow-listed public
vulnerability facts only: request-local `finding_N` and `machine_N`
placeholders, CVE, CVSS, severity, confidence, deterministic risk values, EPSS
and KEV state. It never receives a subnet, IP, hostname, MAC, vendor, operating
system identity, organisation data, database UUID, port/service map, raw
evidence, scanner banner, recommendation or reference text.

The provider response refers to findings only through `finding_N` placeholders.
The backend rejects unknown references, maps valid references to persisted IDs,
and replaces placeholders with local display values before it stores or returns
the analysis.

### 7. Prompt-injection containment

The model has no tools or write capability, and it receives only the bounded
placeholder context described above. The backend normalizes generated text before
storage and again before returning older stored analyses, stripping Unicode format,
variation-selector and tag characters. This is a hygiene control, not a security
boundary.

Action priority and ordering are computed from the supplied KEV, EPSS, CVSS and
deterministic risk facts. Every KEV finding supplied to the model must be referenced
by an action; otherwise the analysis is rejected. The model cannot downgrade or
reorder those actions.

### 8. Customer-facing writing contract

The provider receives a versioned, application-owned English writing skill with
short plain-language prose rules. After the structural and grounding checks, the
backend deterministically rejects text that exceeds field limits, uses raw
identifiers or markup, certifies safety, or violates the agreed vocabulary and
style patterns. Each analysis stores the writing-skill version that it passed.

On the first style failure, the worker sends only violation codes and the original
bounded context for one repair attempt; it never echoes rejected prose. A second
style failure ends the job with `style_violation`, without changing deterministic
scan data.


## Consequences

- Operators must set `AI_ENABLED=true` and `AI_API_KEY` on **both** `api` and
  `worker`, then restart both.
- The provider cannot use customer-identifying scan fields to identify a network
  or machine. The backend retains the local placeholder mapping only while it
  validates and materialises that response.
- Groq is a temporary merged choice. DMI-163 replaces the adapter with OpenAI
  GPT-5.6 Luna on the Responses API.

## Rejected alternatives

- Automatic analysis after enrichment. It created unbounded `pending` polling
  and sent data without a press.
- Folding AI into the enrichment tick. A slow Groq call blocked scoring.
- Switching to Claude or Luna inside this PR. That would rewrite a working
  adapter before merge.
- Per-organisation opt-in and requester audit in this PR. Extra product surface
  with no customers.

## Planned changes

Tracked under epic [DMI-161](https://linear.app/peirce/issue/DMI-161) Improve AI
scan analysis:

| Issue | Change |
|-------|--------|
| [DMI-162](https://linear.app/peirce/issue/DMI-162) | D2. Public facts and request-local placeholders only — completed |
| [DMI-163](https://linear.app/peirce/issue/DMI-163) | D1. OpenAI GPT-5.6 Luna, Responses API |
| [DMI-164](https://linear.app/peirce/issue/DMI-164) | D5. Independent KEV/EPSS/NVD retries |
| [DMI-165](https://linear.app/peirce/issue/DMI-165) | D5. Refresh an open scan page after late enrichment |
| [DMI-166](https://linear.app/peirce/issue/DMI-166) | D3. Bounded child tasks and synthesizer |
| [DMI-167](https://linear.app/peirce/issue/DMI-167) | D8. Prompt-injection containment |
| [DMI-168](https://linear.app/peirce/issue/DMI-168) | D9. Writing skill and linter - completed |
| [DMI-169](https://linear.app/peirce/issue/DMI-169) | Research assistant with web search |
| [DMI-170](https://linear.app/peirce/issue/DMI-170) | DESIGN follow-ups for the AI card |

Chat, downloadable reports and a Home summary are not decided.

## References

- `specs/047-pr-144-review-remediation/TRUTH.md` decision log D1–D11
- `specs/047-pr-144-review-remediation/ARCHITECTURE.md` §2.1
- [ADR-005](ADR-005-security-model.md)
- `docs/roadmap/AI.md`
