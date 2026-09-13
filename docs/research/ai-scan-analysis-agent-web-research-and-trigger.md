# Research: AI scan analysis agent — architecture, prompt injection, web research, trigger and consent

> **Scope.** The AI scan analysis in PR #144 (spec `specs/047-pr-144-review-remediation/`,
> Linear DMI-158). Decided inputs: D1 OpenAI `gpt-5.6-luna`, Responses API, strict structured
> output, `store=false`, no tools; D2 only public vulnerability facts plus request-local
> placeholders leave the backend; D3 a separate, failure-isolated AI worker with stateless
> child tasks and a separate synthesizer. Proposed or open: D8 prompt-injection architecture,
> D9 writing skill and linter, D10 trigger, back-fill and consent. Future: a web research stage
> built on the Responses `web_search` tool.
>
> Questions: (1) agent architecture, (2) prompt-injection controls, (3) trigger model,
> (4) consent and cost controls, (5) citations and grounding for web research, (6) UX for AI
> output for non-experts, (7) structured, plain writing output.
>
> Primary sources only: OWASP GenAI Top 10 (2025 and 2026 editions), OWASP Top 10 for Agentic
> Applications 2026, NIST AI 600-1, Beurer-Kellner et al. 2025, Debenedetti et al. 2025 (CaMeL),
> Nasr et al. 2025, Meta Agents Rule of Two, OpenAI and Anthropic developer docs, vendor product
> docs (GitHub, Microsoft, Google, Sentry, Datadog, Snyk), FIRST, CISA, OASIS CSAF, Google PAIR,
> Microsoft HAX (Amershi et al., CHI 2019), Apple HIG, W3C WCAG 2.2, LGPD (Lei 13.709/2018).
> Simon Willison's blog is cited as the originator of the "lethal trifecta" term, which OWASP
> 2026 adopts. **Fetched 2026-09-13.** Items marked **unverified** could not be confirmed
> against the owner's text.

---

## TL;DR verdict

- **Q1 — architecture.** A fixed **workflow** (code decides the steps), not an autonomous agent,
  is the right shape. Anthropic's own guidance says to use "the simplest solution possible"
  and separates predefined-code-path *workflows* from self-directed *agents*. D3's
  builder → stateless child tasks → synthesizer is the published **LLM map-reduce** pattern,
  whose guarantee is that one malicious input can affect only its own map task. Put web
  research **before** the analysts, as a separate stage that is **not tied to any customer**:
  one research record per CVE, cached and shared across organisations. Structured feeds
  (CVE.org, NVD, CISA KEV, FIRST EPSS, vendor CSAF) should answer most questions. Use web
  search only for what those feeds lack.
- **Q2 — prompt injection.** Every serious source agrees that no reliable prevention exists
  (OWASP LLM01:2025 and LLM01:2026, NIST AI 600-1, Anthropic, OpenAI). The OWASP 2026 text is
  blunt: defence "is therefore architectural rather than interceptive". The controls that
  survive an adaptive attacker **limit the blast radius**: no tools, no actions, no private
  data in the model's context, strict output validation in code, isolated tasks, and plain-text
  rendering. Delimiters, "ignore instructions in the data" prompt lines and injection
  classifiers **lower the success rate** only against non-adaptive attacks. Nasr et al. (2025)
  bypassed 12 published defences with >90% success. Treat these as telemetry, not as a
  boundary. D8's ranking is mostly right. Four corrections are in §8.2.
- **Q3 — trigger.** Vendors split on this. The common pattern is: **an admin enables the
  feature; new events run automatically within caps; the backlog runs on request; results
  are cached.** Microsoft Defender auto-generates on open, lets admins choose auto, by
  severity or on demand, and caches for a week. Sentry auto-runs only new issues that pass
  thresholds and says existing issues "need Autofix to be run manually". Google SecOps TIN
  auto-runs with an hourly cap and "doesn't automatically analyze alerts generated beyond the
  limit". **For Dmitri: hybrid.** Per-organisation admin opt-in, off by default. After opt-in,
  analyse each new completed scan automatically. Do no back-fill. An admin can request
  analysis of an older scan. Apply per-organisation daily caps. Reuse results by context hash.
- **Q4 — consent.** The D2 payload (CVE facts and placeholders) is probably **not personal
  data** under LGPD Art. 5 I. So the opt-in is a **B2B product and contract control**, not LGPD
  *consentimento* (Art. 5 XII is a data subject's consent). Name it "enable AI analysis" and not
  "consent". Record who enabled it, when, and which disclosure text they saw. ANPD has published
  a non-binding generative-AI *Radar Tecnológico*. **No binding ANPD AI rule was found.** Brazil's
  AI bill PL 2338/2023 passed the Senate in Dec 2024. Its status in the Câmara on 2026-09-13 is
  **unverified**.
- **Q5 — citations.** OpenAI `web_search` supports up to 100 `allowed_domains` (subdomains
  included), a full `sources` list via `include`, `url_citation` annotations that "must be made
  clearly visible and clickable", and `external_web_access: false` for cache-only runs. **Trap:**
  subdomain inclusion means allow-listing a user-content host (for example `github.com`) admits
  attacker-written pages. **Validation:** check URLs against the tool's returned sources and
  the allow-list in code. Check facts against structured feeds, not against a second model.
- **Q6 — UX.** Label AI text where it appears (Apple HIG, NIST MP-5.1-003). Name the data sources
  (PAIR). Show specific progress text, not "Processing…" (Apple HIG). Poll a bounded job; do not
  stream strict JSON. Always keep a path forward after failure (PAIR). Never let an overview say
  the network is safe. Prefer a categorical signal or a limitations list to numeric confidence
  (PAIR). Mark the overview "outdated" when enrichment later changes the input (HAX G18).
- **Q7 — writing.** Use a strict schema with enums and `maxItems`. Strict mode supports string
  `pattern` and `format`, but `minLength`/`maxLength` are **not in the documented supported
  list**. So enforce character limits in Pydantic and the D9 linter, and state them in the
  field `description`. Use `text.verbosity: "low"`. Treat refusal and `incomplete` as failures.

---

## Findings

### 1. Architecture of an embedded analysis agent

#### 1.1 Workflow, not agent

- Anthropic separates **workflows**, "systems where LLMs and tools are orchestrated through
  predefined code paths", from **agents**, which "dynamically direct their own processes and
  tool usage". Its core advice is "finding the simplest solution possible, and only increasing
  complexity when needed"
  ([Building effective agents, 2024-12-19](https://www.anthropic.com/engineering/building-effective-agents)).
- A scan analysis has a known input (a finding list) and a known output (a fixed schema). No
  step requires the model to choose the next step. That is a workflow. Anthropic's named
  patterns that fit are **parallelization / sectioning** (independent subtasks) and **prompt
  chaining** (child results → synthesis).
- **Orchestrator-worker** (a model plans the subtasks) is for "unpredictable" tasks. Anthropic's
  multi-agent research system uses it, at about **15× the tokens of chat**. It says the approach
  suits high-value, parallel, open-ended research and fits poorly where tasks share context
  ([How we built our multi-agent research system, 2025-06-13](https://www.anthropic.com/engineering/built-multi-agent-research-system)).
  A model-driven orchestrator gives Dmitri nothing that deterministic backend partitioning
  does not already give. It also adds a model that can be steered.

#### 1.2 Security patterns that match the shape

[Beurer-Kellner et al., "Design Patterns for Securing LLM Agents against Prompt Injections"
(arXiv:2506.08837, June 2025)](https://arxiv.org/abs/2506.08837) define six patterns
([HTML full text](https://arxiv.org/html/2506.08837)). Their guiding principle: "once an LLM
agent has ingested untrusted input, it must be constrained so that it is impossible for that
input to trigger any consequential actions".

| Pattern | Guarantee (per paper) | Limit (per paper) | Dmitri fit |
|---|---|---|---|
| Action-selector | Model only picks from fixed actions; tool feedback never returns to it | Loses LLM flexibility | Not needed: no actions |
| Plan-then-execute | Control-flow integrity: untrusted data cannot change the action sequence | Does not stop tampering with action *parameters* | Research stage: backend code is the planner |
| **LLM map-reduce** | One malicious document affects only its own map task | Map outputs need strict constraints | **D3 child tasks → synthesizer** |
| **Dual LLM** | Privileged model never sees untrusted data; quarantined model has no tools | Quarantined model is still injectable; output must be constrained | **Research reader = quarantined model** |
| Code-then-execute | Explicit, analysable control flow (generalises CaMeL) | Untrusted data can still change parameters | Overkill |
| **Context-minimization** | Removes content (e.g. user prompt) before later steps | May drop useful context | **D2 allow-list** |

The paper's ten case studies do not include a web-search or summarisation agent. The Dmitri
mapping above is my own application, not the paper's.

[CaMeL (Debenedetti et al., arXiv:2503.18813, 2025)](https://arxiv.org/abs/2503.18813) takes
dual-LLM further. A privileged model writes a program from the trusted query. Untrusted data
"can never impact the program flow". Capabilities block exfiltration at tool calls. It solved
77% of AgentDojo tasks with provable security against 84% undefended. **For Dmitri:** CaMeL
targets agents with tools that act on private data. PR #144 has no tools. The plain rule "backend
code is the planner, the reader has no tools" gives the control-flow property without an
interpreter.

#### 1.3 Context isolation and intermediate records

- Anthropic reports that letting subagents write results to external storage, rather than
  passing everything through the lead agent, avoids "the 'game of telephone'". A separate
  citation step checks source attribution
  ([multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system)).
  This supports D3's "synthesizer sees only validated structured child results".
- OpenAI's agent-safety guide: "By defining structured outputs between nodes (e.g., enums, fixed
  schemas, required field names), you eliminate freeform channels that attackers can exploit".
  It also says to "extract only specific structured fields … from external inputs"
  ([Safety in building agents](https://developers.openai.com/api/docs/guides/agent-builder-safety)).
- OpenAI's deep-research guide recommends **staging**: "run public-web research first, then run
  a second call that has access to the private MCP but no web access"
  ([Deep research](https://developers.openai.com/api/docs/guides/deep-research)). That is the
  same separation as research stage → analysts.
- **Critical note.** Structured records remove *freeform* channels, not *semantic*
  manipulation. OWASP 2026: schema validation "catches format violations, not semantic
  manipulation: a schema-valid response can still carry a malicious … body"
  ([OWASP GenAI LLM Top 10 2026, LLM01 mitigation #2](https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/)).
  A record field such as `exploit_status: "none_known"` can still be a lie planted by a page.
  Enums shrink what a lie can say. They do not make it true. §5.4 covers the check.

#### 1.4 Where the research stage sits

Recommended order, derived from the sources above. The "customer-independent" point is my
inference, not a vendor statement.

```
                 ┌──────────── customer-independent ────────────┐
CVE ids in scan ─► dossier cache hit? ─no─► structured feeds ─► gaps? ─yes─► research reader
                 │  (key: cve_id +       │   (CVE.org/NVD/KEV/     │         (web_search, allow-list,
                 │   dossier_version,    │    EPSS/CSAF, no model) │          no other tools, strict record)
                 │   TTL)                │                         │               │
                 └───────────────────────┴─────────────────────────┴── validate ◄──┘
                                                   │ typed dossier fields only
customer scan ─► D2 builder (placeholders) ─► child analysts (no tools) ─► validate+lint ─► synthesizer ─► UI
```

Why the research stage should not be tied to any customer:

1. It needs only a CVE id. It never needs `machine_1` or `finding_1`. Keep placeholders out of
   it, so the only model that reads the web holds **no customer context**. That removes the
   "private data" leg of the lethal trifecta for that call (§2.3).
2. It is the expensive part: web search costs $10 per 1k calls plus search content tokens
   ([OpenAI pricing](https://developers.openai.com/api/docs/pricing)). Analysis tokens cost
   far less (§3.4). A per-CVE cache shared across organisations makes each CVE a one-time cost,
   not a per-scan cost.
3. Querying a CVE id at scan time reveals, at most, that *some* OpenAI customer cares about that
   CVE. A cache refreshed on a timer weakens even that timing signal.

---

### 2. Prompt-injection defences

#### 2.1 What the standards say

- **OWASP LLM01:2025 Prompt Injection.** It defines direct and indirect injection and lists
  seven mitigations: constrain behaviour, define and validate output formats "use deterministic
  code to validate", filter input and output, least privilege, human approval for high-risk
  actions, "segregate external content", adversarial testing. It says: "it is unclear if there
  are fool-proof methods of prevention"
  ([LLM01:2025](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)).
- **OWASP 2026 edition supersedes 2025.** The
  [OWASP GenAI LLM Top 10 2026](https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/)
  (resource page dated 2026-08-03; the PDF was read directly) ranks: LLM01 Prompt Injection,
  LLM02 Sensitive Information Disclosure, **LLM03 Excessive Agency** (was LLM06),
  LLM04 Supply Chain, LLM05 Data and Model Poisoning, LLM06 Unbounded Consumption,
  LLM07 Misinformation, LLM08 Hidden Context Exposure, LLM09 Vector and Embedding Weaknesses,
  **LLM10 Improper Output Handling** (was LLM05). The task named the 2025 IDs. The 2025 pages
  are cited below where asked, but ADR-020 should cite the 2026 IDs.
- **LLM01:2026 mitigations, with OWASP's own caveats** (PDF pp. 13–15):
  1. Constrain role in the system prompt: "a partial control only".
  2. Strict output schema validated in code, "using structural validation rather than a second
     LLM call": catches format, not semantics.
  3. Filter at every modality boundary: "evadable by rephrasing or encoding".
  4. Credentials and state changes in application code; deterministic policy engine;
     least privilege.
  5. Strip tag-block **U+E0000–E007F**, variation selectors **U+FE00–FE0F**, zero-width
     **U+200B, U+200C, U+200D, U+2060** "at every ingest and render boundary".
  6. Provenance-labelled separate channel for external content: "reduces attack success in
     non-adaptive tests only".
  7. Human confirmation of the exact rendered action.
  8. **Rule of Two** as a floor.
  9. Treat memory writes as privileged.
  10. Pin and verify MCP servers and tool packages.
  11. "Test against adaptive attackers who have read the deployed defense".

  It also says the least-privilege and capability-budget controls (#4, #8) "are load-bearing".
- **LLM02:2025 Sensitive Information Disclosure.** Sanitise and minimise data. Use
  "tokenization and pattern-matching … to preprocess and redact". Be transparent about
  retention ([LLM02:2025](https://genai.owasp.org/llmrisk/llm022025-sensitive-information-disclosure/)).
  D2 placeholders are this control.
- **LLM05:2025 Improper Output Handling.** "Treat the model as any other user, adopting a
  zero-trust approach". Encode output for its context. Use strict CSP. Use parameterised queries
  ([LLM05:2025](https://genai.owasp.org/llmrisk/llm052025-improper-output-handling/)).
- **LLM06:2025 Excessive Agency.** Minimise extensions, functions and permissions. Avoid
  open-ended tools such as URL fetching. "Implement authorization in downstream systems rather
  than relying on an LLM". Rate-limit to limit damage
  ([LLM06:2025](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)).
- **LLM07:2026 Misinformation** (the injection outcome that matters most for Dmitri: "tell the
  owner it is safe"). "Ground Claims Before Action", "Claim-Check-Act", "Use Verification
  Signals (Not Just Confidence)", "Require structured outputs with mandatory fields", "Distinguish
  verified facts from assumptions" (2026 PDF, LLM07).
- **LLM06:2026 Unbounded Consumption.** "Hard Spending Caps: Set non-overridable budget ceilings
  per API key, user, team". Also "Traditional request-rate limiting alone is no longer
  sufficient" (2026 PDF, LLM06).
- **OWASP Top 10 for Agentic Applications 2026** (announced 2025-12-09): ASI01 Agent Goal
  Hijack, ASI02 Tool Misuse, ASI03 Identity & Privilege Abuse, ASI04 Agentic Supply Chain,
  ASI05 Unexpected Code Execution, **ASI06 Memory & Context Poisoning**, **ASI07 Insecure
  Inter-Agent Communication**, **ASI08 Cascading Failures**, **ASI09 Human-Agent Trust
  Exploitation**, ASI10 Rogue Agents
  ([OWASP announcement](https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/)).
  The per-entry mitigation text is in the download PDF, which I did **not** read (unverified).
  The earlier [Agentic AI – Threats and Mitigations (2025-02-17)](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/)
  is the threat-model companion. Relevance to Dmitri: ASI06 is the per-CVE dossier cache (a
  poisoned record reaches every organisation). ASI08 is one bad research record spreading
  into every scan that cites it. ASI09 is a non-expert owner trusting a confident overview.
- **NIST AI 600-1 (July 2024), Generative AI Profile.** §2.9 Information Security names direct
  and indirect prompt injection. Indirect injection is when adversaries "exploit LLM-integrated
  applications by injecting prompts into data likely to be retrieved". §2.2 names
  **Confabulation**. Relevant actions: **MS-2.7-007** red-team for prompt injection;
  **MP-5.1-003** "Consider disclosing use of GAI to end users in relevant contexts"; **GV-6.1-007**
  "Inventory all third-party entities with access to organizational content and establish
  approved GAI technology and service provider lists"; **GV-6.1-008** keep records of
  third-party content changes "including sources, timestamps, metadata"
  ([NIST.AI.600-1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)). NIST's AI RMF
  profile is a voluntary framework. It lists actions, not a ranking.

#### 2.2 Vendor guidance

- **OpenAI.** Do not put untrusted variables in developer messages: "Developer messages take
  precedence … injecting untrusted input directly into developer messages gives attackers the
  highest degree of control". Use structured outputs between nodes. Keep tool approvals on
  ([Safety in building agents](https://developers.openai.com/api/docs/guides/agent-builder-safety)).
  Deep research: use only trusted MCP servers, stage web and private access, "log and review
  tool calls", apply "schema or regex validation to tool arguments"
  ([Deep research](https://developers.openai.com/api/docs/guides/deep-research)). The general
  best-practices page ([Safety best practices](https://developers.openai.com/api/docs/guides/safety-best-practices))
  is thin on injection: limit input length, limit output tokens, red-team. OpenAI's blog posts
  on agent injection (`openai.com/index/prompt-injections/`,
  `/designing-agents-to-resist-prompt-injection/`) returned HTTP 403 to my fetch. Their content
  (confirmations, "Safe Url" exfiltration checks) is known only from search snippets and is
  **unverified**.
- **Anthropic.** "Put untrusted content only in tool results", "Tell Claude what the content is
  and where it came from", state the untrusted-content policy in the system prompt,
  "JSON-encode untrusted content", least privilege, screen tool outputs with a small classifier,
  red-team ([Mitigate jailbreaks and prompt injections](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks)).
  Anthropic's browser research states "prompt injection is far from a solved problem". It
  reports a 1% attack success rate against an adaptive attacker for Claude Opus 4.5 and says this
  "still represents meaningful risk"
  ([Mitigating prompt injections in browser use, 2025-11-24](https://www.anthropic.com/research/prompt-injection-defenses)).
  - **Disagreement.** Anthropic's doc recommends classifier screening as a step. OWASP 2026 and
    Nasr et al. show that classifiers fail against adaptive attackers. Both can be true: a
    classifier is a detector with a false-negative rate, not a boundary. Its vendor doc also
    sells the model's own robustness. That is a real but model-specific property. It does not
    carry over to `gpt-5.6-luna`.
- **Meta, Agents Rule of Two (2025-10-31).** Within one session an agent may have at most two
  of: **[A]** untrusted inputs, **[B]** sensitive systems or private data, **[C]** state change
  or external communication. Meta calls it "a supplement — and not a substitute" for least
  privilege, and says it does not cover misinformation
  ([Meta AI blog](https://ai.meta.com/blog/practical-ai-agent-security/)).
- **Simon Willison, lethal trifecta (2025-06-16).** Private data + untrusted content + external
  communication. Of guardrail products claiming "95%" detection, he writes that in web security
  such a rate is a failure
  ([simonwillison.net](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/)). OWASP
  2026 LLM01 cites the trifecta directly.

#### 2.3 Where the trifecta legs are in Dmitri

| Stage | [A] untrusted input | [B] private data | [C] outbound / state change | Verdict |
|---|---|---|---|---|
| PR #144 child analyst | CVE ids, numbers, enums only (T1). Weak A: NVD/CNA-authored strings are excluded by D8 | Placeholders only; mapping stays in backend | None: no tools, output is display text | 0–1 legs |
| Synthesizer | Validated child records (model output = semi-trusted) | Placeholders, counts | None | 0–1 legs |
| Future research reader | **Yes**: web pages | **Must be none**: no placeholders, no scan context | **Yes**: `web_search` issues queries to the internet (a query can carry data) | A + C: acceptable **only if B is empty** |
| Future analyst using dossier | Typed dossier fields (derived from A) | Placeholders | None | Keep dossier fields typed; no page prose |

Leak through search queries is real, not theoretical.
[Rall et al., "Exploiting Web Search Tools of AI Agents for Data Exfiltration" (arXiv:2510.09093)](https://arxiv.org/abs/2510.09093)
report that well-known indirect-injection methods still succeed in getting agents with web
search to leak internal data. OpenAI's deep-research guide gives the same scenario: a page tells
the model to send CRM data "through search query parameters"
([Deep research](https://developers.openai.com/api/docs/guides/deep-research)). With an empty
[B], a hijacked reader has nothing worth leaking.

#### 2.4 Controls ranked by strength (against an adaptive attacker)

| Rank | Control | Type | Why it holds / fails | Sources |
|---|---|---|---|---|
| 1 | **No capability**: no tools, no model-triggered action, output is display text only | Blast radius | Nothing to hijack; survives any injection | LLM06:2025; LLM01:2026 #4; Beurer-Kellner principle |
| 2 | **Break a trifecta leg per call**: no private data in the web-reading call; no web in the private-context call | Blast radius | Structural; does not depend on model behaviour | Rule of Two; OpenAI deep-research staging; Willison |
| 3 | **Context minimisation** (D2 allow-list; no raw evidence, banners, advisory prose) | Attack surface | Less attacker text reaches the model at all | LLM02:2025; Beurer-Kellner |
| 4 | **Deterministic output validation in code**: strict schema, enums, placeholder set check, URL ∈ returned sources ∩ allow-list, length limits, linter | Output boundary | Blocks format smuggling and unknown refs; **not** semantic lies | LLM01:2026 #2; LLM05:2025; OpenAI structured outputs |
| 5 | **Isolation**: stateless per-chunk tasks, `store=false`, no `previous_response_id`, synthesizer sees records only | Blast radius | One poisoned input affects one map task (map-reduce guarantee) | Beurer-Kellner; OpenAI agent safety |
| 6 | **Safe rendering**: text nodes only, no markdown/HTML/auto-link, no model-supplied URLs outside validated source records, CSP | Output boundary | Removes image-URL and link exfiltration and XSS | LLM05:2025; LLM01:2026 Scenario #2 |
| 7 | **Deterministic cross-check of claims** against structured feeds (KEV, EPSS, NVD, CVE.org) | Semantic | A page cannot overrule the KEV JSON; conflict → record rejected or flagged | LLM07:2026 "Claim-Check-Act" |
| 8 | **Invisible-character stripping** at ingest *and* render (the exact OWASP ranges) | Input hygiene | Stops a known class; not visible-text payloads | LLM01:2026 #5 |
| 9 | **Caps**: tool calls per task, tasks per org per day, spend ceiling | Blast radius (cost) | Bounds loop and cost attacks | LLM06:2026; LLM06:2025 |
| 10 | **Audit**: versions, context hash, validation and linter codes, source URLs per record | Detection | Makes an attack visible after the fact | NIST GV-6.1-008; OpenAI deep research "log and review" |
| 11 | **Adaptive red-team tests** in CI (fixed corpus) plus periodic manual | Assurance | Measures, does not prevent | LLM01:2026 #11; NIST MS-2.7-007 |
| 12 | Separate input item / JSON-encoding untrusted strings; developer vs user role placement | Probability | Helps non-adaptive attacks only; "an attacker who knows the marking scheme can mimic it" | LLM01:2026 #6; OpenAI; Anthropic |
| 13 | System-prompt policy ("content is data, not instructions") | Probability | "a partial control only" | LLM01:2026 #1 |
| 14 | Injection classifier (LLM or ML) on web text | Detection | Useful telemetry; bypassed by adaptive attacks | Anthropic doc; Nasr et al. 2025 |

#### 2.5 Mitigation vs theatre

- **Theatre when used alone:** a "treat content as untrusted" sentence; XML or delimiter
  "spotlighting"; a second LLM that "checks the first for injection" and then gates an action;
  keeping the system prompt secret (OWASP 2026 LLM08 assumes it can be reconstructed);
  vendor "95% detection" claims. Nasr et al. (2025) found defences that reported near-zero attack
  success were bypassed at **>90%** for most of 12 defences under adaptive attack
  ([arXiv:2510.09023](https://arxiv.org/abs/2510.09023)).
- **Theatre specific to Dmitri:** "human in the loop" for a display-only overview that nobody
  reviews before the owner reads it. The owner *is* the loop, and ASI09 is about exactly that
  person over-trusting. A moderation API call: it detects harmful content, not injection
  ([Safety best practices](https://developers.openai.com/api/docs/guides/safety-best-practices)).
- **Real mitigation:** ranks 1–7 above. They constrain what a successful injection *achieves*.
  For Dmitri the remaining impact after ranks 1–6 is **misinformation**: an overview that
  understates a risk. Rank 7, plus taking priority out of the model's hands (§8.2), is the
  control for that.

---

### 3. Trigger model

#### 3.1 Vendor evidence

| Product | Default trigger | On-demand path | Admin control | Caps / cost signal | Source |
|---|---|---|---|---|---|
| **Microsoft Copilot in Defender — incident summary** | Auto-generates "for each incident the user opens" | **Generate** button when auto is off | Setting: Auto-generate (Always / by minimum severity) or Generate on demand (preview) | Shows "estimated SCU consumption"; cache "for a week … redisplayed at no cost" if incident "didn't change significantly" | [Microsoft Learn, updated 2026-09-10](https://learn.microsoft.com/en-us/defender-xdr/security-copilot-m365d-incident-summary) |
| **GitHub Copilot Autofix (code scanning)** | Auto on pull requests: alert data "is automatically sent to the LLM" | "Generate fix" on existing alerts | "Allowed by default and enabled for every repository that uses CodeQL"; enterprise/org/repo admins can disable | Needs write permission to fix | [Triaging alerts in PRs](https://docs.github.com/en/code-security/code-scanning/managing-code-scanning-alerts/triaging-code-scanning-alerts-in-pull-requests); [About Copilot Autofix](https://docs.github.com/en/code-security/concepts/code-scanning/copilot-autofix-for-code-scanning); [Resolving alerts](https://docs.github.com/en/code-security/code-scanning/managing-code-scanning-alerts/resolving-code-scanning-alerts) |
| **Google SecOps — Triage and Investigation Agent** | Auto on alerts, "enabled by default if you have the necessary administrator permissions and are opted into the agent" | Manual trigger | SIEM Settings toggle and criteria | Trial limits: 5 automatic + 5 manual per hour (Enterprise); "doesn't automatically analyze alerts generated beyond the limit" | [Triage Agent](https://docs.cloud.google.com/chronicle/docs/secops/triage-agent) |
| **Google SecOps — Gemini case summary widget** | Shown in default case view | Manual refresh | Admin can remove widget | "2 cases per minute … maximum of 100 cases per hour"; "doesn't automatically regenerate the summary when entity enrichment is updated" | [Summarize cases with Gemini](https://docs.cloud.google.com/chronicle/docs/soar/investigate/working-with-cases/using-the-gemini-case-summary-widget) |
| **Sentry Seer Autofix** | Auto only when issue has ≥10 events, occurred in last 14 days, sufficient fixability | "Always manually trigger … from the Issue Details page" | Org "Show Generative AI Features" toggle; per-project automation stop points | "Existing issues will need Autofix to be run manually" (**no back-fill**) | [Autofix](https://docs.sentry.io/product/ai-in-sentry/seer/autofix/); [AI in Sentry](https://docs.sentry.io/product/ai-in-sentry/) |
| **Datadog Bits Investigation** | Opt-in per monitor: starts when a monitor "transitions to the alert state" (not warn, renotify, test) | Manual from monitor, event panel, Slack | Per-monitor toggle; not settable via API/Terraform | Rate-limit numbers not on page (unverified) | [Investigate issues](https://docs.datadoghq.com/bits_ai/bits_ai_sre/investigate_issues/) |
| **Snyk Agent Fix** | Off until enabled in Group/Org settings | "Click **Generate AI fix**" in IDE | Group/Org admin | "Does not use customer code to train" | [Fix code vulnerabilities automatically](https://docs.snyk.io/scan-fix-and-prevent/scan-with-snyk/snyk-code/manage-code-vulnerabilities/fix-code-vulnerabilities-automatically) |
| **Wiz** | Product docs require login; public material is blog/marketing | — | — | — | **Unverified**; excluded as non-primary ([Wiz blog](https://www.wiz.io/blog/introducing-ai-powered-remediation-2-0) is marketing) |

**Patterns in the evidence:**

1. **Every product has an admin-level switch.** Defaults vary: GitHub, Sentry and Defender are
   on by default for entitled customers. Snyk and Datadog are off until configured. Vendors that
   default *on* already hold a contract that covers AI processing. Dmitri's customers have no
   such contract clause today.
2. **Automatic runs attach to *new* events, with caps.** Sentry and Google state the backlog is
   not processed automatically.
3. **Caching by "did the input change"** is explicit at Microsoft (one week, "didn't change
   significantly"). Google's widget shows the failure mode: it does *not* regenerate when
   enrichment updates, so a summary can go stale.
4. **Operator-facing cost estimates** (Defender SCU estimate) appear when automation is
   configurable.
5. All these products serve **security or engineering staff**. None targets a non-expert small
   business owner. Transferring "on-demand is fine" from SOC tools to Dmitri is weak evidence.
   SOC analysts are trained to click. Dmitri's user is not.

#### 3.2 HCI evidence on timing

- HAX **G3 "Time services based on context"** and **G17 "Provide global controls"**
  ([Amershi et al., CHI 2019](https://www.microsoft.com/en-us/research/uploads/prod/2019/01/Guidelines-for-Human-AI-Interaction-camera-ready.pdf);
  [HAX library](https://www.microsoft.com/en-us/haxtoolkit/library/)).
- Apple HIG: "Generative models typically take longer to produce a result, so design a loading
  experience or generate in the background while a person uses another part of the app"
  ([Apple HIG — Generative AI](https://developer.apple.com/design/human-interface-guidelines/generative-ai)).
  Background generation for a new scan fits that line. A button that makes the owner wait
  tens of seconds does not.

#### 3.3 Options for Dmitri

| Option | Pros | Cons |
|---|---|---|
| A. Auto after enrichment, all orgs (as built) | Ready on open | No consent; back-fill egress (P4); pays for unread scans |
| B. On demand per scan | Clear intent and requester for audit; zero cost when unused | Non-expert owners may never click; wait on first view; an extra decision the owner is not equipped to make |
| **C. Hybrid: admin opt-in → auto for each new completed scan; on-demand (admin) for older scans; no back-fill; caps; hash cache** | Matches vendor pattern (Sentry, Defender, Google); ready when the owner opens the newest scan; consent recorded once by an accountable admin; bounded cost | Two entry paths to test; auto jobs have `requested_by = system`, so intent lives in the opt-in record, not per job |
| D. Auto only for the *latest* scan per org (supersede queued older) | Cheapest auto variant | Scans complete rarely per org (Pi schedule), so "latest" and "each new" are nearly the same; extra supersede logic |

#### 3.4 Cost reality check (my calculation, not a vendor figure)

Prices: `gpt-5.6-luna` $0.20 / 1M input, $0.02 / 1M cached input, $1.20 / 1M output
([model page](https://developers.openai.com/api/docs/models/gpt-5.6-luna);
[pricing](https://developers.openai.com/api/docs/pricing)). Web search: $10 / 1k calls plus
search content tokens at model rates for reasoning models ([pricing](https://developers.openai.com/api/docs/pricing)).

Assumptions (**unmeasured**): child task ≈ 3k input tokens (instructions largely cached after the
first call) and ≈ 1.5k output including medium reasoning; 40 findings in chunks of 5 → 8 children
+ 1 synthesis.

- Per child ≈ 3,000 × $0.20/1M + 1,500 × $1.20/1M ≈ **$0.0024**. Per scan ≈ 9 tasks ≈ **$0.02–0.03**.
- Research per uncached CVE ≈ 2 search calls ($0.02) + ~10k content tokens ($0.002) ≈ **$0.02**.
  40 new CVEs ≈ **$0.90**, about **30× the analysis**. Caching per CVE across organisations is
  the cost lever, not the trigger.

Conclusion: analysis cost alone does not justify making non-expert users click. Consent, back-fill
and research cost do justify admin opt-in, no back-fill and a shared research cache.

---

### 4. Consent and cost controls

#### 4.1 Legal framing (Brazil)

- **Personal data** is "informação relacionada a pessoa natural identificada ou identificável"
  (LGPD Art. 5 I). **Anonymised data** "não serão considerados dados pessoais" unless the process
  can be reversed "com esforços razoáveis" (Art. 12)
  ([Lei 13.709/2018](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)).
- D2 sends CVE facts and placeholders. The mapping `machine_1 → host` stays in Dmitri's backend,
  so for Dmitri it is **pseudonymised**. For OpenAI, which lacks the mapping, it is very likely
  not linkable to any natural person. The closest statutory definition of pseudonymisation is in
  Art. 13 §4, which formally sits in the article on public-health research. Its use here is by
  analogy. ANPD's anonymisation and pseudonymisation guide went to public consultation in
  January–March 2024 ([ANPD news](https://www.gov.br/anpd/pt-br/assuntos/noticias/anpd-abre-consulta-a-sociedade-sobre-o-guia-de-anonimizacao-e-pseudonimizacao)).
  **Its final publication was not verified.**
- **Consequence:** if no personal data leaves, the international-transfer rules (Art. 33;
  [Resolução CD/ANPD nº 19/2024](https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd/resolucao-cd-anpd-no-19-de-23-de-agosto-de-2024))
  do not apply to the D2 payload. They *would* apply to the pre-D2 context (IPs, raw evidence
  with hostnames or account names). That is a legal reason to keep the D2 boundary test (P18)
  strict.
- **"Consent" is the wrong word.** LGPD *consentimento* (Art. 5 XII) is a data subject's
  agreement. For customer scan data, Dmitri acts as **operador** processing "segundo as
  instruções fornecidas pelo controlador" (Art. 39). The customer organisation is the
  controller. The org opt-in is therefore the controller's **instruction** to its operator.
  Record it as such: who, when, and which disclosure text version. This is my legal reading,
  not ANPD guidance. Confirm with counsel before ADR-020 uses legal terms.
- **ANPD and AI.** ANPD published *Radar Tecnológico nº 3 — Inteligência Artificial Generativa*
  ([PDF](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/documentos-tecnicos-orientativos/radar_tecnologico_ia_generativa_anpd.pdf)),
  a technical study of risks under LGPD. gov.br blocked my direct fetch. Its content and non-binding
  status are known from ANPD's listing and search snippets only (**unverified in full**).
  **No binding ANPD regulation specific to AI was found.** PL 2338/2023 (AI framework) passed the
  Senate in December 2024 ([Senado](https://www25.senado.leg.br/web/atividade/materias/-/materia/157233)).
  Its Câmara status on 2026-09-13 is **unverified**.
- **GDPR / EU AI Act** are not directly applicable to a Brazil-only product. For awareness:
  EU AI Act Art. 50 transparency duties apply from 2 August 2026, but the text-disclosure duty
  covers text "published with the purpose of informing the public on matters of public interest"
  ([European Commission FAQ](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act)).
  A private B2B scan overview is outside that duty.

#### 4.2 Product disclosure (non-legal) sources

- Apple HIG: "Communicate where your app uses AI … gives people the opportunity to knowingly
  choose". For server processing: "process as much information locally as possible, and minimize
  what's shared … making sure people know their information may be sent to a server, showing them
  what's shared". "Articulate whether your model uses personal information for training"
  ([Apple HIG](https://developer.apple.com/design/human-interface-guidelines/generative-ai)).
- OpenAI API data: "not used to train or improve OpenAI models" unless opted in. `/v1/responses`
  stores data at least 30 days when `store=true`. Abuse-monitoring logs kept "up to 30 days"
  unless under modified or zero retention
  ([Your data](https://developers.openai.com/api/docs/guides/your-data)). **Disclosure copy must
  not say "OpenAI keeps nothing"**: `store=false` does not switch off abuse-monitoring
  retention unless the project has ZDR or modified retention.
- Background mode, if ever used, stores response data "for roughly 10 minutes" even with
  `store=false` ([Background mode](https://developers.openai.com/api/docs/guides/background)).
  D3's own worker makes synchronous calls, so this does not apply today.

#### 4.3 Cost controls

- OpenAI limits are per organisation and project (RPM, TPM, RPD, TPD), with separate budget
  controls at org and project level. Use exponential backoff with jitter and honour `Retry-After`
  ([Rate limits](https://developers.openai.com/api/docs/guides/rate-limits)). Luna's tier limits
  run from 500 RPM (Tier 1) to 30,000 (Tier 5) ([model page](https://developers.openai.com/api/docs/models/gpt-5.6-luna)).
- OWASP LLM06:2026: hard, non-overridable spend ceilings plus per-entity quotas.
- Google TIN's split quota (automatic and manual counted separately, "unused automatic
  investigation capacity doesn't transfer") is a good model. Automatic runs cannot starve a
  person's explicit request.

---

### 5. Citations and grounding for web research

#### 5.1 Authoritative sources — use the structured feed before the web

| Fact | Owner and structured source | Notes |
|---|---|---|
| CVE record, CNA description, references, affected products | CVE Program: CVE JSON 5 record ([cvelistV5](https://github.com/CVEProject/cvelistV5)); CNA container + ADP containers | CISA ADP adds SSVC, KEV data, missing CVSS/CWE/CPE, and "will [not] overwrite the originating CNA's data" ([CISA Vulnrichment](https://github.com/cisagov/vulnrichment)) |
| CVSS, CPE applicability | NVD CVE API ([developers](https://nvd.nist.gov/developers/start-here)) | Already integrated (D5). NVD page blocked my fetch today; rate-limit numbers not re-verified |
| Known exploited | CISA KEV. Criteria: CVE ID assigned, "reliable evidence that the vulnerability has been actively exploited in the wild", "clear remediation action" ([KEV](https://www.cisa.gov/known-exploited-vulnerabilities)); catalog in CSV/JSON with JSON Schema ([catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)) | Already integrated |
| Exploitation probability | FIRST EPSS: probability of exploitation "within the next 30 days", updated daily; "EPSS is not a complete risk score … does not measure how much damage … or whether it affects your environment" ([EPSS FAQ](https://www.first.org/epss/faq)) | The writing skill must not present EPSS as risk |
| Fixed versions, workarounds | Vendor advisories. Machine-readable form: **CSAF 2.0** (OASIS Standard, 2022-11-18), discovered via `provider-metadata.json`, with OpenPGP-signed documents ([CSAF 2.0](https://docs.oasis-open.org/csaf/csaf/v2.0/os/csaf-v2.0-os.html)) | Where a vendor publishes CSAF, parse it; no model needed |

**Conclusion.** Most facts the analysis needs have a structured, owner-published source that
code can parse without a model. Web search is justified only for the remaining gaps: vendors
without CSAF, or advisory pages that state a fixed version the CVE record lacks.
**Recommendation: build the structured-feed dossier first. Measure the gap. Add `web_search`
only if the gap is material.** Anthropic's research system found agents "consistently preferred
SEO-optimized content over authoritative sources" until given source-quality heuristics
([multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system)).
That is a reason to prefer feeds over search.

#### 5.2 OpenAI `web_search` features (Responses API)

From [Web search guide](https://developers.openai.com/api/docs/guides/tools-web-search):

- **Domain filters:** `filters.allowed_domains` or `blocked_domains`, up to 100. Omit the scheme
  ("use `openai.com`"). **Subdomains are included automatically.** Only on `web_search` in
  Responses, not `web_search_preview`.
- **Sources:** `include: ["web_search_call.action.sources"]` returns "the complete list of URLs the
  model consulted". Inline citations "show only the most relevant references". Sources can
  include feeds labelled `oai-sports`, `oai-weather`, `oai-finance`.
- **Citations:** `url_citation` annotations with URL, title and location. "Inline citations must
  be made clearly visible and clickable in your user interface".
- **Live access:** `external_web_access: false` = cache/offline mode. Default `true`.
- **Tool choice:** `tool_choice: "required"` forces a search.
- **Limits:** search context capped at 128k. `search_context_size` low/medium/high "does not …
  guarantee a specific number of sources".
- **Data:** live web search "is not HIPAA eligible"; offline mode can be covered under ZDR/BAA
  ([Your data](https://developers.openai.com/api/docs/guides/your-data)). For Dmitri this matters
  only if a customer asks about retention regimes.
- **Unverified and must be tested:** (a) whether `allowed_domains` restricts pages *opened*, or
  only results *returned*; (b) whether `url_citation` annotations are produced when
  `text.format` is a strict `json_schema` (the citations attach to message text, and strict JSON
  output may carry none); (c) whether `web_search` works with `store=false` in the same way
  (AI-DECISION-BRIEF §0 already flags combined-feature testing).

#### 5.3 Allow-list design

- **Tier 1 (facts):** `cve.org`, `nvd.nist.gov`, `cisa.gov`, `first.org`.
- **Tier 2 (vendor advisories):** exact vendor security subdomains only, e.g.
  `msrc.microsoft.com`, `support.hpe.com`. Never a vendor's apex domain when it also hosts
  forums or community content: subdomain inclusion would admit them.
- **Exclude user-generated content hosts** even when useful: `github.com` (issues, gists,
  READMEs are attacker-writable; OWASP 2026 LLM01 Scenario #9 is a poisoned GitHub issue),
  `medium.com`, forums, paste sites.
- Authoritative ≠ instruction-safe. NVD and CVE descriptions are CNA-authored text. OWASP 2026
  calls third-party content that a user chose to retrieve but did not author "semi-trusted".
  Treat every page as untrusted input, even on the allow-list.

#### 5.4 Validation of research records

1. Record schema: typed fields only. `cve_id` (pattern `^CVE-\d{4}-\d{4,}$`), `fixed_version`
   (bounded pattern), `vendor_workaround_available` (enum), `exploit_status` (enum),
   `published_at` (`format: date`), `source_url`, `retrieved_at`.
2. `source_url` ∈ `web_search_call.action.sources` **and** its host matches the allow-list
   (exact host or listed subdomain). Otherwise reject the record.
3. **Cross-check against feeds in code:** a record saying "not exploited" for a KEV-listed CVE is
   rejected. KEV wins. EPSS and CVSS always come from feeds, never from the reader.
4. **Quoted text.** The D8 draft passes "short quoted fact" in the record. That is attacker-controlled
   prose (T2) flowing onward. Keep a quote, if at all, **only for audit and display**, labelled as a
   source excerpt and rendered as text. **Never pass it to analysts or the synthesizer.** To verify
   a quote, the backend can fetch the allow-listed URL with plain HTTP (no model) and check that the
   string is present. That is deterministic, but it adds an outbound fetch. Accept it or drop quotes.
5. Store per record: model, prompt/schema versions, source URLs, retrieval date, validation
   outcome (NIST GV-6.1-008 "sources, timestamps, metadata").
6. **Poisoning of a shared cache (ASI06):** version and TTL every record. Allow manual
   invalidation. A record never overrides a feed value.

#### 5.5 Rendering sources

- OpenAI requires visible, clickable inline citations when its annotations are shown
  ([Web search guide](https://developers.openai.com/api/docs/guides/tools-web-search)). Dmitri's
  prose fields carry no links (WRITING-SKILL §2). So render a **"Sources"** list per explanation
  from validated record URLs: domain + title + date, as real links with `rel="noopener noreferrer"`.
- PAIR: "Articulate data sources … Telling the user what data are being used … can help your
  product avoid contextual surprises"
  ([PAIR — Explainability + Trust](https://pair.withgoogle.com/chapter/explainability-trust/)).

---

### 6. UX for AI output for non-experts

| Need | Guidance | Source |
|---|---|---|
| Label AI content | "Clearly identify when and where you use AI"; "Never trick someone into thinking … content authored by a human" | [Apple HIG](https://developer.apple.com/design/human-interface-guidelines/generative-ai) |
| | "Consider disclosing use of GAI to end users in relevant contexts" (MP-5.1-003) | [NIST AI 600-1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) |
| | HAX G1 "Make clear what the system can do", G2 "Make clear how well the system can do what it can do" | [Amershi et al. 2019](https://www.microsoft.com/en-us/research/uploads/prod/2019/01/Guidelines-for-Human-AI-Interaction-camera-ready.pdf) |
| Name data sources | "Articulate data sources" as a factor in calibrated trust | [PAIR](https://pair.withgoogle.com/chapter/explainability-trust/) |
| Errors possible | "Clearly communicate that AI-generated content may contain errors"; "Avoid using AI-generated content in situations where a possible hallucination could misinform and harm" | [Apple HIG](https://developer.apple.com/design/human-interface-guidelines/generative-ai) |
| Loading | "Instead of 'Processing…', say 'Summarizing key themes…'"; "If something goes wrong, describe what happened in plain language and offer a clear next step" | [Apple HIG](https://developer.apple.com/design/human-interface-guidelines/generative-ai) |
| Accessible status | Status messages must be programmatically determinable "without receiving focus" (`role="status"`) | [WCAG 2.2 SC 4.1.3](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html) |
| Failure | "Provide paths forward from failure"; "Return control to the user" | [PAIR — Errors + Graceful Failure](https://pair.withgoogle.com/chapter/errors-failing/) |
| | Offer a non-AI fallback where possible | [Apple HIG](https://developer.apple.com/design/human-interface-guidelines/generative-ai) |
| Confidence | "Statistical information like confidence scores can be challenging for users to understand"; "A misleadingly high confidence … may cause users to blindly accept a result"; categorical buckets are an option | [PAIR](https://pair.withgoogle.com/chapter/explainability-trust/) |
| Trust calibration | "The user shouldn't trust the system completely … should know when to trust … and when to apply their own judgement" | [PAIR](https://pair.withgoogle.com/chapter/explainability-trust/) |
| Staleness | HAX G18 "Notify users about changes"; Google's summary widget does not regenerate on enrichment update (anti-pattern) | [Amershi et al.](https://www.microsoft.com/en-us/research/uploads/prod/2019/01/Guidelines-for-Human-AI-Interaction-camera-ready.pdf); [Google SecOps](https://docs.cloud.google.com/chronicle/docs/soar/investigate/working-with-cases/using-the-gemini-case-summary-widget) |
| Feedback | HAX G15 "Encourage granular feedback"; PAIR "Communicate value & time to impact"; Google SecOps thumbs up/down with reason; Defender feedback icon | [Amershi et al.](https://www.microsoft.com/en-us/research/uploads/prod/2019/01/Guidelines-for-Human-AI-Interaction-camera-ready.pdf); [PAIR — Feedback + Control](https://pair.withgoogle.com/chapter/feedback-controls/); [Google SecOps](https://docs.cloud.google.com/chronicle/docs/soar/investigate/working-with-cases/using-the-gemini-case-summary-widget); [Defender](https://learn.microsoft.com/en-us/defender-xdr/security-copilot-m365d-incident-summary) |
| Global control | HAX G17 "Provide global controls" | [Amershi et al.](https://www.microsoft.com/en-us/research/uploads/prod/2019/01/Guidelines-for-Human-AI-Interaction-camera-ready.pdf) |

**Polling vs SSE/streaming.** The output is a strict JSON object produced by a backend worker in
several calls. A token stream of partial JSON has no user value, and D8 forbids showing partial
output. SSE would add a long-lived connection path for a job that finishes in seconds to about a
minute. **Bounded polling** of a job status (TanStack Query `refetchInterval` as a function, as
already used in `useScanCommand.ts`) is adequate. Poll only while the status is `queued`/`running`,
stop at a terminal state or a time bound (P8). The repo's
[`tanstack-query-followed-resource-lifetime.md`](tanstack-query-followed-resource-lifetime.md)
covers the query-lifetime side. No primary source mandates polling over SSE. This is an
engineering judgement.

**Not certifying safety.** No source above gives exact copy. It follows from Apple's
hallucination guidance and PAIR's trust calibration. A scan with zero findings must produce
"This scan found no known vulnerabilities. It cannot confirm the network is safe." Never "Your
network is secure". This is already WRITING-SKILL rule 7–10 territory. Keep it linter-enforced.

**Feedback affordance.** PAIR ties feedback to model or product improvement. Dmitri has no
pipeline that reads feedback. Under the repo's no-temporary-code rule, **do not ship thumbs
buttons until someone owns the review loop**. Record this as deferred.

---

### 7. Structured writing output

- **Schema.** Strict mode supports string `pattern` and `format` (date-time, date, email, uuid…),
  number bounds, and array `minItems`/`maxItems`. It limits schemas to 5,000 properties, 10
  nesting levels and 1,000 enum values. "If you turn on Structured Outputs by supplying strict: true
  and call the API with an unsupported JSON Schema, you will receive an error"
  ([Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)).
  **`minLength`/`maxLength` are not in the supported-string list.** The page mentions them only in
  the list of keywords fine-tuned models "additionally" do not support. That is ambiguous.
  **Unverified:** test whether Luna accepts `maxLength` in strict mode. Either way, enforce the
  WRITING-SKILL character limits in Pydantic and the linter, and state them in each field
  `description`.
- **Key order** follows the schema ([Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)).
  Put `refs` before prose fields so the model commits to its evidence first. That is my design
  inference, not an OpenAI claim.
- **Refusal and truncation.** Refusals are "programmatically detectable". Incomplete responses
  (e.g. `max_output_tokens`) "won't necessarily follow your supplied schema": check
  `response.status` and `incomplete_details.reason`
  ([Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)).
- **Length control.** `text.verbosity` low/medium/high "affects output length, not reasoning"
  ([GPT-5 new params and tools](https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_new_params_and_tools)).
  Support on `gpt-5.6-luna` is **unverified** (the cookbook targets GPT-5). Test it.
- **Style rules and banned-phrase linting.** No standards body publishes an "AI voice" banned
  list. Such lists are product-owned. The defensible primary basis is plain-language guidance
  ([Digital.gov plain language guides](https://digital.gov/guides/plain-language/), Plain Writing
  Act of 2010). The project's ASD-STE100 rule is already in `CLAUDE.md`. The enforcement shape
  in WRITING-SKILL (deterministic linter, one repair attempt, then `style_violation`) matches
  OWASP 2026's preference for "structural validation rather than a second LLM call". **Do not use
  an LLM as the style judge in the gate.** It adds cost and another injectable step.

---

## 8. Recommendations for Dmitri

### 8.1 D10 — trigger, back-fill, consent

**Recommend option C (hybrid).**

| Rule | Detail |
|---|---|
| Deployment kill switch | `AI_ENABLED` + key stays; off → no jobs, card absent |
| Org enablement | New org setting, **off by default**, **admin only** (viewer is read-only per ADR-008). Store `ai_enabled_at`, `ai_enabled_by_user_id`, `ai_disclosure_version` |
| Automatic | After opt-in, enqueue one analysis for each **scan completed after `ai_enabled_at`** once enrichment reaches a terminal state (D5). `requested_by = system` |
| Back-fill | **None.** Scans completed before opt-in get no automatic job (Sentry precedent) |
| On demand | For older scans, or after a failure: `Explain this scan` button, **admin only**. `requested_by = user_id`. Viewers see the card only when an analysis exists |
| Reuse | Key = hash(D2 context) + prompt, skill, schema, model versions. Same key → reuse, no call (Defender "no cost" cache precedent) |
| Outdated | When D5 enrichment later changes the context hash, show "outdated" and auto-regenerate once if within cap. This avoids Google's stale-widget failure mode |
| Caps | Per-org daily cap with **separate automatic and manual budgets** (Google TIN pattern), plus an OpenAI project budget ceiling (OWASP LLM06:2026). Cap hit → terminal `limit_reached` state, never endless pending (P8) |
| Opt-out | Stops new jobs and hides the card immediately. **Maintainer choice:** delete stored analyses (clean expectation) or keep until scan deletion. Recommend delete |
| Audit event | `ai_analysis_enabled` / `disabled` (actor, disclosure version); per job: requester, versions, context hash, token usage, latency, validation codes |

**Draft disclosure (Settings, admin):** "Turn on AI overviews. Dmitri sends public vulnerability
details (such as CVE numbers and severity scores) to OpenAI to write a plain-language overview of
each new scan. Dmitri does not send your IP addresses, machine names, company name or raw scan
data. OpenAI does not use this data to train its models. OpenAI may keep it for up to 30 days for
abuse monitoring. Overviews can contain mistakes. Your scan results do not change."
Check the 30-day claim against the project's actual retention terms before release
([Your data](https://developers.openai.com/api/docs/guides/your-data)).

**Why not pure on-demand (option B)?** Its strongest argument is "clear intent per call". The
admin opt-in already records accountable intent. The cost per scan is cents (§3.4). The target
user is a non-expert, and HAX G3 and Apple HIG favour background generation. B stays a valid
fallback if cost per scan measures far above the estimate.

### 8.2 D8 — prompt-injection ADR controls (checks on the proposed list)

The TRUTH D8 list is consistent with the evidence. Adopt it with these changes:

1. **Re-rank "Data, not instructions" (control 3) as a probability control**, below validation
   and isolation. OWASP 2026 #6 says it helps "in non-adaptive tests only". Do not present it as a
   boundary.
2. **Replace "Unicode NFKC" with explicit stripping.** NFKC does not remove tag-block (U+E0000–E007F),
   variation selectors (U+FE00–FE0F) or zero-width (U+200B–U+200D, U+2060) characters. Strip them
   at ingest **and** before render (OWASP 2026 #5). Keep NFKC if wanted, as an addition.
3. **Take priority ordering out of the model.** The residual injection impact is misinformation
   (§2.5). Compute the action order and a minimum priority band in code from KEV/EPSS/CVSS/risk.
   Reject model output that ranks a KEV-listed finding below that band, or that omits it. This is
   the LLM07:2026 "Claim-Check-Act" control. It is also the only control on the list that targets
   the semantic lie.
4. **Research quotes never reach analysts** (§5.4 item 4). Records carry typed fields only.
5. **Add to the ADR:** Rule of Two table per stage (§2.3); per-task tool-call cap; allow-list
   excludes user-content hosts; research cache is versioned and TTL'd, and never overrides feed
   values (ASI06/ASI08); CI corpus of adversarial cases; claims of classifier protection are out of
   scope.
6. **Cite 2026 IDs:** LLM01, LLM02, LLM03 (Excessive Agency), LLM06 (Unbounded Consumption),
   LLM07 (Misinformation), LLM10 (Improper Output Handling); ASI06, ASI08, ASI09.

### 8.3 Future web research stage (new issue)

1. **Stage 0 — structured dossier, no model:** CVE.org record (CNA + CISA ADP), NVD, KEV, EPSS,
   vendor CSAF where discoverable. Keyed by CVE, shared across orgs, TTL.
2. **Measure the gap** (share of findings with no fixed version or remediation text). Add web
   search only if material.
3. **Stage 1 — research reader** (dual-LLM quarantined model): input = CVE id + typed feed facts
   only, no placeholders, no scan or org context. `web_search` with `allowed_domains` (Tier 1 +
   exact vendor security hosts), `tool_choice: "required"`,
   `include: ["web_search_call.action.sources"]`, `store=false`, no other tools, a small tool-call
   cap, strict record schema. Consider `external_web_access: false` first and measure freshness
   loss.
4. **Validation in code:** URL ∈ sources ∩ allow-list; enums and patterns; feed values win on
   conflict; reject otherwise.
5. **Analysts** receive typed dossier fields. **UI** shows a Sources list from validated URLs.
6. **Tests before accept:** web_search + strict JSON + `store=false` combined; domain filter
   behaviour on linked pages; injected page fixtures (instruction text, fake JSON, invisible
   Unicode).
7. D10 is unaffected: research is customer-independent, so it needs no per-org trigger. It runs
   when an enabled org's scan contains an uncached CVE.

### 8.4 D6-adjacent UI (DESIGN amendments)

- Provenance caption. Keep DESIGN's line and add sources: "Written by an AI model from this scan's
  results and public vulnerability data (NVD, CISA KEV, FIRST EPSS). It can contain mistakes. Check
  the vulnerabilities before acting."
- Pending text names the step and coverage ("Reading vulnerabilities: 4 of 12") inside
  `role="status"`.
- States: `not_enabled` (card absent), `not_requested` (admin button), `queued/running` (bounded
  polling), `completed`, `outdated`, `limit_reached`, `failed` (facts remain; admin "Try again").
- No numeric confidence. Use the `limitations[]` list.
- No feedback buttons until a review owner exists (record as deferred).

---

## Sources

All fetched or checked 2026-09-13.

**Standards and frameworks**
- OWASP GenAI LLM Top 10 2026 (resource page dated 2026-08-03; PDF read): https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/
- OWASP LLM01:2025 Prompt Injection: https://genai.owasp.org/llmrisk/llm01-prompt-injection/
- OWASP LLM02:2025 Sensitive Information Disclosure: https://genai.owasp.org/llmrisk/llm022025-sensitive-information-disclosure/
- OWASP LLM05:2025 Improper Output Handling: https://genai.owasp.org/llmrisk/llm052025-improper-output-handling/
- OWASP LLM06:2025 Excessive Agency: https://genai.owasp.org/llmrisk/llm062025-excessive-agency/
- OWASP Top 10 for Agentic Applications 2026 (announcement with list): https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/
- OWASP Agentic AI – Threats and Mitigations (2025-02-17): https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/
- NIST AI 600-1, Generative AI Profile (July 2024): https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- W3C WCAG 2.2 Understanding SC 4.1.3: https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
- OASIS CSAF 2.0: https://docs.oasis-open.org/csaf/csaf/v2.0/os/csaf-v2.0-os.html

**Papers and research**
- Beurer-Kellner et al., Design Patterns for Securing LLM Agents against Prompt Injections (arXiv:2506.08837): https://arxiv.org/abs/2506.08837 · full text https://arxiv.org/html/2506.08837
- Debenedetti et al., Defeating Prompt Injections by Design (CaMeL, arXiv:2503.18813): https://arxiv.org/abs/2503.18813
- Nasr, Carlini et al., The Attacker Moves Second (arXiv:2510.09023): https://arxiv.org/abs/2510.09023
- Rall et al., Exploiting Web Search Tools of AI Agents for Data Exfiltration (arXiv:2510.09093): https://arxiv.org/abs/2510.09093
- Amershi et al., Guidelines for Human-AI Interaction (CHI 2019): https://www.microsoft.com/en-us/research/uploads/prod/2019/01/Guidelines-for-Human-AI-Interaction-camera-ready.pdf · HAX library https://www.microsoft.com/en-us/haxtoolkit/library/
- Meta AI, Agents Rule of Two (2025-10-31): https://ai.meta.com/blog/practical-ai-agent-security/
- Simon Willison, The lethal trifecta (2025-06-16): https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/

**OpenAI**
- GPT-5.6 Luna model: https://developers.openai.com/api/docs/models/gpt-5.6-luna
- Pricing: https://developers.openai.com/api/docs/pricing
- Web search: https://developers.openai.com/api/docs/guides/tools-web-search
- Structured Outputs: https://developers.openai.com/api/docs/guides/structured-outputs
- Safety in building agents: https://developers.openai.com/api/docs/guides/agent-builder-safety
- Safety best practices: https://developers.openai.com/api/docs/guides/safety-best-practices
- Deep research (prompt injection and exfiltration section): https://developers.openai.com/api/docs/guides/deep-research
- Your data (retention, ZDR): https://developers.openai.com/api/docs/guides/your-data
- Background mode: https://developers.openai.com/api/docs/guides/background
- Rate limits: https://developers.openai.com/api/docs/guides/rate-limits
- GPT-5 new params and tools (verbosity): https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_new_params_and_tools
- Unverified (HTTP 403): https://openai.com/index/prompt-injections/ · https://openai.com/index/designing-agents-to-resist-prompt-injection/

**Anthropic**
- Building effective agents (2024-12-19): https://www.anthropic.com/engineering/building-effective-agents
- How we built our multi-agent research system (2025-06-13): https://www.anthropic.com/engineering/built-multi-agent-research-system
- Mitigate jailbreaks and prompt injections: https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks
- Mitigating the risk of prompt injections in browser use (2025-11-24): https://www.anthropic.com/research/prompt-injection-defenses

**Vendor products (trigger evidence)**
- Microsoft Copilot in Defender — incident summaries: https://learn.microsoft.com/en-us/defender-xdr/security-copilot-m365d-incident-summary
- GitHub Copilot Autofix: https://docs.github.com/en/code-security/concepts/code-scanning/copilot-autofix-for-code-scanning · https://docs.github.com/en/code-security/code-scanning/managing-code-scanning-alerts/triaging-code-scanning-alerts-in-pull-requests · https://docs.github.com/en/code-security/code-scanning/managing-code-scanning-alerts/resolving-code-scanning-alerts
- Google SecOps Triage Agent: https://docs.cloud.google.com/chronicle/docs/secops/triage-agent
- Google SecOps Gemini case summary: https://docs.cloud.google.com/chronicle/docs/soar/investigate/working-with-cases/using-the-gemini-case-summary-widget
- Sentry Seer Autofix: https://docs.sentry.io/product/ai-in-sentry/seer/autofix/ · AI in Sentry: https://docs.sentry.io/product/ai-in-sentry/ · Seer: https://docs.sentry.io/product/ai-in-sentry/seer/
- Datadog Bits Investigation: https://docs.datadoghq.com/bits_ai/bits_ai_sre/investigate_issues/
- Snyk Agent Fix: https://docs.snyk.io/scan-fix-and-prevent/scan-with-snyk/snyk-code/manage-code-vulnerabilities/fix-code-vulnerabilities-automatically
- Wiz (marketing only, not used for claims): https://www.wiz.io/blog/introducing-ai-powered-remediation-2-0

**Vulnerability data owners**
- CISA KEV: https://www.cisa.gov/known-exploited-vulnerabilities · catalog https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- FIRST EPSS FAQ: https://www.first.org/epss/faq
- NVD developers (fetch blocked today): https://nvd.nist.gov/developers/start-here
- CVE Program cvelistV5: https://github.com/CVEProject/cvelistV5
- CISA Vulnrichment: https://github.com/cisagov/vulnrichment

**UX**
- Google PAIR Guidebook — Explainability + Trust: https://pair.withgoogle.com/chapter/explainability-trust/ · Errors + Graceful Failure: https://pair.withgoogle.com/chapter/errors-failing/ · Feedback + Control: https://pair.withgoogle.com/chapter/feedback-controls/ · Mental Models: https://pair.withgoogle.com/chapter/mental-models/
- Apple HIG — Generative AI: https://developer.apple.com/design/human-interface-guidelines/generative-ai
- Digital.gov plain language guides: https://digital.gov/guides/plain-language/

**Brazil / legal**
- LGPD, Lei 13.709/2018 (Arts. 5, 6, 12, 13 §4, 33, 39): https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm
- Resolução CD/ANPD nº 19/2024 (international transfer): https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd/resolucao-cd-anpd-no-19-de-23-de-agosto-de-2024
- ANPD Radar Tecnológico — IA Generativa (direct fetch blocked): https://www.gov.br/anpd/pt-br/centrais-de-conteudo/documentos-tecnicos-orientativos/radar_tecnologico_ia_generativa_anpd.pdf
- ANPD consultation, anonymisation and pseudonymisation guide (2024): https://www.gov.br/anpd/pt-br/assuntos/noticias/anpd-abre-consulta-a-sociedade-sobre-o-guia-de-anonimizacao-e-pseudonimizacao
- PL 2338/2023 (Senado): https://www25.senado.leg.br/web/atividade/materias/-/materia/157233
- European Commission FAQ, AI Act Art. 50: https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act
