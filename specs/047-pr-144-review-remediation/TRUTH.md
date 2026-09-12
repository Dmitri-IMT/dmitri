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
| 0 | Baseline | Branch rebased on main; gates run once; results recorded as the "before" state | Baseline recorded |
| 1 | Code review | Findings list for the whole PR, ranked by severity, grouped by the four parts | Findings recorded |
| 2 | Decision review | One decision per question D1–D7 (below), approved by a maintainer, with the teammate consulted | All seven decided |
| 3 | ADRs | AI analysis agent ADR, plus any other ADR a decision requires; roadmap reverted or aligned to the ADR | ADRs accepted |
| 4 | Remediation | Code changes that apply the decisions and fix the accepted review findings; new issues for deferred work | Every accepted finding fixed or ticketed |
| 5 | Gates | All per-layer gates green, zero skipped backend tests | All green |
| 6 | Docs sync | Knowledge base, code map, setup guide, roadmap, and contract match the branch | No drift reported |
| 7 | Merge readiness | PR description updated with decisions, ADR links, and "Fixes DMI-158"; overlapping issues closed or rescoped | Maintainer approval |

Phase 1 runs before Phase 2 because review findings are inputs to the decisions (for example, a
data-exposure finding changes the data-boundary decision).

## Decisions to make (Phase 2)

| ID | Question | Options to weigh |
|----|----------|------------------|
| D1 | Which LLM provider and model does the AI analysis use? | Keep Groq with an open-weight model; switch to the Claude model the roadmap named; provider-neutral with one default |
| D2 | What scan data may be sent to the provider, and can an organisation opt out? | Full context as built; reduced or anonymised context; off by default per organisation with explicit opt-in |
| D3 | How are AI analysis jobs run and retried? | Keep the separate AI job flow as built; fold into the existing background worker |
| D4 | Is the local scan import a product feature or a developer tool? | Keep as a supported command; keep as a dev-only tool; remove |
| D5 | Is the enrichment retry design accepted, and how does it relate to the open enrichment-error issue? | Accept and close/rescope that issue; accept with changes; defer |
| D6 | Does the industrial services part duplicate or conflict with the open industrial persistence work? | This PR wins and the issues are rescoped; the in-progress issue wins and this part is removed; merge both |
| D7 | Does PR #144 merge as one PR or split into one PR per part? | One PR; split into four; split AI from the rest |

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

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Baseline recorded | The branch is rebased on main | Phase 0 runs | The spec records each gate result, including the backend passed/skipped counts |
| Review complete | Phase 0 is done | The code review runs on the whole PR | A findings list exists, each finding with severity, part (1–4), and a location |
| All decisions made | Findings are recorded | Phase 2 ends | D1–D7 each have a chosen option, a reason, the approving maintainer, and a date |
| No code before decision | A part has no recorded decision | Someone proposes a remediation change for it | The change is not started |
| AI ADR exists | D1 and D2 are decided | Phase 3 ends | An accepted ADR names the provider, model policy, data sent, opt-in/opt-out rule, failure behaviour, and how answers are grounded in scan data |
| Roadmap matches ADR | The AI ADR is accepted | The AI roadmap is read | It states the same provider and data boundary as the ADR, and it does not contradict the security roadmap |
| AI disabled | AI analysis is turned off | An operator opens a completed scan | All scan results show, and the AI area shows no error and makes no provider call |
| AI provider fails | AI is on and the provider returns an error or times out | An operator opens that scan | All scan results show; the AI area shows a clear failed state; no partial or invented analysis is shown |
| Data boundary enforced | D2 limits what is sent | An analysis request is built | The request contains only the data D2 allows (verified by a test) |
| Import decision applied | D4 is decided | The branch is read | The import command exists, is documented, and is tested as D4 says — or it is gone |
| Overlap resolved | D5 and D6 are decided | Linear is read | Each overlapping issue is closed, rescoped, or linked with the decision |
| Findings closed | Phase 4 ends | The findings list is read | Every accepted finding is fixed on the branch or linked to a new issue |
| Backend gate | Phase 5 runs with the test database up | The backend suite runs | It passes with zero skipped tests, and lint reports no errors |
| Frontend gate | Phase 5 runs | Lint, typecheck, tests, and build run | All pass |
| Contract fidelity | Phase 5 runs | The API contract is compared to the routes and the generated frontend types | No drift |
| Docs synced | Phase 6 runs | Docs sync runs | The setup guide lists every new setting and the import command (if kept); the code map lists the new modules; no drift is reported |
| No temporary code | Phase 4 ends | The diff is reviewed | No stopgap or partial implementation remains without a maintainer-approved issue |
| Merge ready | Phases 0–6 are done | The PR is read | Its description lists the decisions, links the ADRs, and says "Fixes DMI-158" |

## Out of scope

- New AI features beyond what PR #144 already contains (chat assistant, downloadable reports,
  Home summary described in the rewritten roadmap).
- Rebuilding any part the decisions remove or defer — those become new issues.
- Changes to the Raspberry Pi agent.
- Formatting unrelated backend files.
- Reworking the earlier accidental merge and revert history.

## Decision log

Filled in during Phase 2. One row per decision.

| ID | Decision | Reason | Approved by | Date |
|----|----------|--------|-------------|------|
| D1 | **Reopened.** The whole AI scan analysis (provider, model, data boundary, job design, frontend embedding) is reviewed again as one decision. No AI code is kept, changed or fixed until then. | The maintainer does not accept the AI choices made without approval, including how AI is embedded in the frontend. | Guilherme Ronca | 2026-09-12 |
| D2 | Part of D1. | Reviewed together with D1. | Guilherme Ronca | 2026-09-12 |
| D3 | Part of D1. | Reviewed together with D1. | Guilherme Ronca | 2026-09-12 |
| D4 | **Remove** the local scan import command, its tests and its docs. | The end user never uses the Raspberry Pi or the TUI; the web app is the only surface they know. A file-import path has no user. | Guilherme Ronca | 2026-09-12 |
| D5 | **Keep** the enrichment retry work. Verify it end to end across every call path and fix what is wrong. | Resilient enrichment is wanted. | Guilherme Ronca | 2026-09-12 |
| D6 | **Main wins** (DMI-157, PR #145, merged 2026-09-12). The branch's own industrial backend is dropped; the industrial web screens are updated to show main's industrial observations. | The fix on main is the approved design. | Guilherme Ronca | 2026-09-12 |
| D7 | Open. | Depends on D1. | | |

## Related specs

- Implementation: `ARCHITECTURE.md`, `DESIGN.md`
