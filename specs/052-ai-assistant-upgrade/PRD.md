# PRD — AI assistant upgrade

> **Status:** draft. Decisions from the 2026-10-22 interview, updated with
> [`docs/research/ai-assistant-openai-luna-web-search-best-practices.md`](../../docs/research/ai-assistant-openai-luna-web-search-best-practices.md)
> (cited below as "research §N").
> **Branch:** `feat/improve-ai-workflows`.
> **Screen design:** [`DESIGN.md`](DESIGN.md).
> **Supersedes parts of:** [DMI-163](https://linear.app/peirce/issue/DMI-163) (model, effort, tools),
> [DMI-169](https://linear.app/peirce/issue/DMI-169) (allow-list, version, chat, links).
> **Earlier research:** [`docs/research/ai-scan-analysis-agent-web-research-and-trigger.md`](../../docs/research/ai-scan-analysis-agent-web-research-and-trigger.md).

## Problem

Dmitri is for people with little or no security knowledge. The AI must tell them what
matters and what to do. Today it does not:

1. **Chat answers are weak.** They are vague and stay close to the scan text.
2. **Fixes repeat the scan.** "What to do first" says what the scan found, not how to fix
   it. The model sees only scan facts, so it cannot give vendor steps, fixed versions or
   sources.
3. **The app feels technical.** Users see tables of ports, CVEs and scores before any
   plain explanation.

A better model alone does not fix 1 and 2. The model needs new facts (web research) and
better instructions.

## Goals

- Each vulnerability has a concrete fix: what to do, who does it, and a source.
- Chat answers specific questions with current information from the web.
- Every AI output follows one written voice, with explicit "do" and "do not" rules.
- A non-expert sees the AI summary and the first action before any technical table.

## Non-goals

- The AI does not act on the customer network. It stays read-only.
- No streaming in this PRD.
- No automated evaluation suite. Quality is checked by hand.
- No second provider and no provider switch setting.
- No reasoning summaries and no OpenAI background mode (research §1.6).
- No redesign of screens other than the entry-point change in R6.

## Users and use cases

- **Business owner:** "What is wrong, and what is the easiest thing I can do about it?"
- **Owner's IT person:** "Which version fixes this, and where is the vendor advisory?"
- **Any user in chat:** "How do I update this router?" and gets steps with a source link.

## Information plan per surface

The AI is called in two ways today: the scan analysis job and chat. Its text appears in
six places. Each place answers one question the user has:

| Place | The user's question | What the AI gives |
|-------|---------------------|-------------------|
| **Home** | "Am I OK? Do I need to act?" | No new AI text. Status and "needs your attention" come from code. Latest-scan review (decided 2026-10-23): the top to-do task (`Next: {task} · {who} · about {time}`), a `See all {n} tasks` link, a code count line (`{n} tasks · fixes {k} of {total} problems`), and a code "what changed since the last scan" line (`{a} problems fixed · {b} new · {machine} still needs attention`) from `first_seen_at` / `fixed_at`. |
| **Scan, to-do list** | "What is wrong, and in which order do I fix it?" | A to-do list of fix tasks, ordered by effort and impact, then one line on what the scan could not check. Created automatically when the scan finishes. |
| **Scan, "Explain this scan"** | "What did this scan do, and what do the results mean?" | A separate feature, started by the button. AI text covers what the results mean, what the scan could not see, and a one-line pointer to the to-do list. What the scan did (network, machines found, check type) is shown as visual cues on the page, not AI text. What the results mean may also become visual cues. |
| **Finding** | "What is this, can it hurt me, how do I fix it?" | What it is, what it could do on this kind of machine, whether it is used in real attacks, the easiest fix first in steps, how to check it is fixed, a source link. |
| **Machine** | "What is this device, and what is wrong with it?" | What the device probably is, its problems in one sentence, the one action that fixes the most. |
| **Chat** | Anything | The answer first, then steps, then the source. Says what is not known. Has guardrails (open). |
| **Report** | "What do I give my IT person?" | The scan to-do list with an owner per task, plus the technical appendix. |

### Output shape

- The basic unit is the **fix task**: one action that can fix many findings. Fields:
  `title`, `who`, `effort`, `steps` (up to 3), `how_to_verify`, `fixes` (finding
  references), `sources`. R3 fix records feed it.
- Replace `executive_summary`, `overall_assessment` and `plain_language_summary` with one
  short summary. Drop the three overlapping per-finding fields.
- Finding and machine explanations become their own structured tasks with their own
  instruction files, not free chat with a fixed question. The global assistant stays chat.
- The finding panel shows one "What to do": the AI fix when it exists, else the scanner's
  recommendation.

### Voice rules (for `voice.md`)

- Answer first. Direct advice, no filler, no over-explanation. Follow the unslop rules.
- Non-technical words. Explain a technical term the first time it is needed.
- Every output ends in an action: who does it, how much effort, how to check it worked.
- Group by fix, not by finding.
- Use visual structure: lists for steps and tasks, short labelled parts, not long
  paragraphs. How (decided 2026-10-23):
  - **Structured surfaces** (scan analysis, fix tasks, Explain panel, finding and machine
    explanations): the model writes no formatting. It returns JSON fields (`steps[]`,
    `lead`, `text`, …) and the frontend draws lists and bold text. The linter keeps
    rejecting Markdown there.
  - **Free chat answers:** limited Markdown only — `- ` lists, `1.` lists and `**bold**`.
    The frontend renders only these three with a safe renderer; everything else shows as
    plain text. The chat linter allows these three and rejects all other Markdown, HTML
    and raw URLs.
- Restate screen facts only when the user needs them explained. The user does not
  understand ports, CVEs or scores, so the AI explains what they mean, not their values
  again.
- Describe the real effect on this kind of machine, calmly, with how likely it is.
- Uncertainty in one sentence, only when it changes the decision.
- Length limits per place.

### Language of automatic output (decided 2026-10-23)

- New organisation setting: **AI language** (`en`, `pt-BR`, `ru`), changed by an admin in
  Settings. Default `en`, which keeps today's behaviour; the owner can switch the default
  later.
- The automatic to-do list (and the fix records it uses) runs once per scan, in the
  organisation language.
- Any other language is made on demand when a user opens the scan in that language,
  with the waiting state.

## Requirements

### R1 — Model and provider

- Replace the Groq adapter with the OpenAI Responses API.
- Model `gpt-6-luna`, `reasoning.effort=high`, on every AI call: chunk analysis,
  synthesis, chat and research. Model and effort are environment configuration.
- Every request sends `store: false`. The API default is `true` (research §1.3, §1.6).
- Instructions go in `instructions`. Scan context goes in the user message as JSON
  (research §3.1).
- Use `text.format` with a strict `json_schema` where the output is structured. Do not
  send `temperature`, `top_p`, `response_format` or `include_reasoning` (research §1.2, §1.3).
- `max_output_tokens` covers reasoning plus visible output. Start each call at 25,000, as
  OpenAI recommends, and lift the current settings cap of 8,192. Log
  `reasoning_tokens` per operation and lower each cap later from real data (research §1.5).
- Handle `status`:
  - `completed`: parse.
  - `incomplete` with `max_output_tokens`: fail this attempt. Never parse JSON from it.
  - `incomplete` with `content_filter`, or a refusal: terminal.
- Errors:
  - Retry rate-limit 429, 500, 503, timeouts and transport errors. Use `Retry-After` as
    the minimum wait, plus jitter.
  - Quota or spend-limit 429, 400, 401, 403 and 404 are terminal. `groq.py` retries some
    of these today (research §1.8).
  - Count or turn off SDK retries, so retries are not doubled.
- Measure latency per operation at `high`, with and without search, before setting
  `AI_TIMEOUT_SECONDS`. The current cap of 120 s may be too low for chat with search
  (research §1.9).
- Remove Groq-specific settings and the Groq base URL. Update `.env.example` and
  `docs/DEV-SETUP.md`.
- Usage rows record `provider="openai"`, model, input, cached, output and reasoning tokens,
  and latency.

### R2 — Instruction files

- One versioned Markdown file per task, stored in the backend: scan chunk analysis, scan
  synthesis, repair, chat and CVE research.
- One shared `voice.md` with the rules for how to write and how NOT to write, and short
  good and bad examples. Start from OpenAI's published GPT-6 plain-language and anti-slop
  prompts, then add Dmitri's rules (research §3.4).
- Each task file uses the order Identity → Instructions → Examples, with the same
  sections: role, goal, inputs, steps, output rules, "do not" list, examples
  (research §3.2, §3.6 has templates).
- Write each "do not" rule with the reason and the thing to do instead (research §3.3).
- Prompt order for caching: `voice.md`, task file, examples, fixed schema and tools, then
  request data. The stable part must be at least 1,024 tokens. Read `cached_tokens` to
  confirm cache hits (research §4.2).
- The file versions are saved with each result, as `AI_PROMPT_VERSION` and the writing
  skill version are today.
- Change two current rules that conflict with this PRD:
  - "Use only facts from the supplied context" becomes: scan facts come from the
    context; fixes and current facts come from research records or cited web results.
  - "Do not use URLs" stays for raw URLs in text. Source names become links (R5).
- Length limits stay in Pydantic and `writing.py`, because strict mode has no
  `minLength` or `maxLength` (research §1.4).
- The writing linter keeps its checks and follows the new `voice.md`.

### R3 — CVE research step

- A separate model call with `web_search` on the open web. The model plans its own
  searches, with `max_tool_calls: 10` (at most $0.10 of searches per record).
- Input: CVE ID, observed product and version, service type, severity, KEV and EPSS. No
  placeholders, IPs, hostnames, organisation data or other scan data.
- Output: strict fix records. Each record has an effort level (for example setting
  change, update, workaround, replace, ask vendor), who must act (owner, IT person,
  vendor), up to 3 short steps, whether it fixes the problem fully, and its sources.
- Each source URL must be in the `web_search_call.action.sources` of that response.
  A record without a valid source is not saved.
- Feed values (KEV, EPSS, NVD fixed version) win over web text when they conflict.
- Cache key: CVE + normalized product + normalized version + research inputs version. The
  cache is shared across organisations.
- Invalidate a record when the CVE's KEV entry changes or the CVE record's `dateUpdated`
  changes (research §4.1). TTL (decided 2026-10-23, configuration): **14 days** for a
  record with a fixed version or vendor fix; **2 days** for a record with no fix yet
  (workaround or "ask the vendor").
- Scan analysis and synthesis receive fix records, never web page text. The easiest
  valid fix feeds "What to do first".

### R4 — Chat with live web search

- Chat has the `web_search` tool on the open web. The model decides when to search.
- Set `user_location` from the organisation country and timezone. Without it, the default
  is the United States (research §2.1).
- Limit cost: `max_tool_calls: 10`, so searches cost at most $0.10 per answer.
  `search_context_size: "medium"`. A search costs $0.01, the same as about 100,000 Luna
  input tokens, so searches drive the chat cost (research §2.2).
- Log `action.queries` and `action.sources` for each answer.
- Chat also reads the cached fix records for the findings in its context.
- Chat keeps placeholder-only context, as today. It never sees real IPs or hostnames.
- One request, one answer. No streaming.
- Guardrails (decided 2026-10-23):
  1. **Topic scope:** only this organisation's network, its scans and security fixes.
     Other topics get a short, polite refusal.
  2. **No offensive help:** no exploit code, no attack steps, no help to get into a
     machine the user does not own. Explain the risk and the fix only.
  3. **Warn before risky steps:** steps that can cut access or lose data (factory reset,
     firmware flash, closing a port a business service uses) start with one warning line
     and "ask your IT person if unsure".
  4. **No invented facts:** versions, menu paths and vendor claims come from scan data or
     a cited source; else the answer says Dmitri could not confirm it. The backend checks
     the cited-source rule (R5).
  5. **No secrets in or out:** the backend removes passwords, API keys, tokens and IP or
     MAC addresses from the user's question before the provider call; the answer never
     repeats them.
  6. **Limits:** `max_tool_calls: 10` per answer; **30 questions per user per day**
     (configuration); a maximum question length.
  Rules 1–4 live in `chat.md` and `voice.md`; rules 5–6 are code checks before the call.

### R5 — Sources in answers

- The answer text names its source ("Cisco advisory"), and the name is a clickable link.
- Links come only from `url_citation` annotations whose URL is also in
  `action.sources`. Never from model text (research §2.4).
- No citation means no source name in the text. The linter flags source names outside
  an annotated span.
- Text is still rendered as plain text. Only the citation links are clickable.
- **Output format per surface** (decided from the 2026-10-23 API tests, open items 1 and 4):
  - Luna returns `url_citation` annotations in both modes, but always also writes its own
    Markdown link next to the cited text, e.g. `([hikvision.com](https://…?utm_source=openai))`.
    With strict JSON the annotation offsets point into the JSON string, not into a field.
  - **Chat:** plain text with the allowed Markdown subset (lists, bold) plus annotations.
    The backend replaces each annotated span (the model's own link) with a source link
    built from the annotation, and drops any Markdown link or raw URL left outside an
    annotated span. `uncertainties` moves into the text.
  - **Research step and scan analysis:** strict JSON. Each fix record has `source_name`
    and `source_url` fields; the backend keeps a record only when `source_url` is in that
    response's `action.sources`. The backend strips Markdown links and raw URLs from all
    other text fields. Annotations are not used here.
  - Strip the `utm_source=openai` query parameter from every stored or shown URL.

### R6 — Waiting state and plain-language entry point

- While the AI works, the UI shows a polished loader, a stage label and the elapsed time.
  Inspiration: the Loading State component on [Beautiful UI](https://www.beautifului.dev).
  It is built with Dmitri's tokens (`docs/ui/FOUNDATIONS.md`, `frontend/src/index.css`).
- Scan analysis shows real progress ("group N of M"). Chat shows only the stage and the
  elapsed time, because it gets nothing before the answer (research §5).
- A Cancel button. `role="status"` announces state changes only, not each timer tick. A
  reduced-motion version of the loader.
- No "what the AI did" trace under answers.
- Separate issue, after R1–R5: the AI summary and "What to do first" appear at the top of
  scan and host views. Technical tables move behind "Show technical details".

## Delivery order

1. Test calls for open items 1–3 (one script, no product code).
2. R1 — model and provider. **Built 2026-10-23** (`services/ai/openai_responses.py`,
   migration `20261023_44` adds `ai_usage.cached_input_tokens` and `reasoning_tokens`).
3. R2 — instruction files and `voice.md`. **Built 2026-10-23** (`services/ai/instructions/`:
   `voice.md`, `scan.md`, `chunk.md`, `synthesis.md`, `repair.md`, `chat.md`;
   `AI_PROMPT_VERSION` 8, `WRITING_SKILL_VERSION` 2). The CVE research file comes with R3,
   which adds its caller and schema. Chat stays plain text until R5 renders lists.
4. R3 — CVE research step and cache. **Built 2026-10-23** (`services/ai/research.py`,
   `instructions/research.md`, table `ai_fix_records` in migration `20261023_45`,
   `AI_PROMPT_VERSION` 9, `AI_CONTEXT_VERSION` 6). Research runs inside the analysis job,
   up to 5 calls in parallel. The AI job stale window is now `AI_TIMEOUT_SECONDS × 10`.
5. R4 + R5 + waiting state — chat search, source links, loader. **R4 and R5 built
   2026-10-23**. **Loader built 2026-10-23** (`components/WaitingState.tsx`, DESIGN.md §9):
   used in chat (with Cancel, which aborts the request; the server still finishes and
   counts it) and in the scan overview. The analysis job now saves its stage
   (`fixes`, `groups`, `summary`) and group count in `ai_scan_analyses.progress_*`
   (migration `20261023_46`), returned as `progress` on pending and processing responses.
   Elapsed time counts from the job's `created_at`. Scan polling now stops after 20
   minutes, not 5, to match the job's stale window. The grid gap is 4px in both sizes,
   because the spacing scale has no 2px or 3px step.
   - Chat is plain text with `web_search` (`AI_CHAT_MAX_TOOL_CALLS`). The backend keeps a
     citation only when its URL is in `action.sources`, writes it as a `[host](url)` link,
     and removes every other link, raw URL, HTML, heading and code mark. Display values are
     stripped of `[`, `]` and `*` before they go into the text.
   - `user_location` comes from `AI_SEARCH_COUNTRY` / `AI_SEARCH_TIMEZONE`, not from the
     organisation: organisations have no country or timezone field. Unset sends
     `{"type": "approximate"}`, which avoids the United States default.
   - Guardrail 5 scrubs credentials and IP, MAC and IPv6 addresses from the question
     before the call and in the saved history; answers are scrubbed of credentials only,
     so vendor steps such as "open 192.168.1.1" survive.
   - Guardrail 6: `AI_CHAT_DAILY_LIMIT` (30) questions per user in a rolling 24 hours,
     counted from `ai_usage` chat rows; over the limit returns 429 `ai_daily_limit`.
   - The chat linter cleans instead of rejecting: a repair call would double a search
     answer's wait.
   - Product, version and service come from the port CPE only, for analysis, research and
     chat. Raw banners are no longer sent, because a banner can hold a hostname.
   - `uncertainties` stays in the API for old messages; new answers return `[]`.
6. R6 entry point — separate issue.

## Success check

Manual. On the same saved scans, compare old and new output:

- Each top vulnerability has a concrete fix with a source link, not a restatement.
- Chat answers "how do I fix this" with steps for the specific product and version.
- The voice rules hold: calm, short, no banned words, no claims that a network is safe.

## Risks

- **Latency.** High reasoning plus web search makes chat slower. Measure it. If the wait
  is too long, lower the chat effort in configuration or add streaming in a new issue.
- **Output cut off.** At `high`, low token caps stop the model during reasoning, and the
  call returns no text. R1 raises the caps.
- **Cost.** Searches, not tokens, are the main chat cost. `max_tool_calls: 10` limits each
  answer to $0.10 of searches, and each user to 30 questions per day.
- **Source quality.** On the open web the model can cite a forum or blog. The
  instructions tell it to prefer vendor advisories and official docs.
- **Prompt injection.** Chat combines scan data, open-web pages and a way out (search
  queries and links). Chat sees no real IPs or hostnames, has no other tools, and output
  is plain text, so the impact is low. Shared fix records have no domain allow-list, so
  their safety depends on the source and schema checks in code.
- **No proof that `high` helps.** There is no eval suite, so the manual check is the only
  comparison.

## Open items

API tests run on 2026-10-23 against `gpt-6-luna`, `reasoning.effort=high`, `store:false`
(script kept outside the repo; about 5 calls):

1. ~~Citations with web_search + strict JSON~~ — **yes**, HTTP 200, 1 `url_citation`
   annotation, 39 sources. Offsets point into the JSON string. See R5 for the format
   decision.
2. ~~`text.verbosity`~~ — **accepted** (`low` → 200, short answer). Usable per task.
3. ~~`maxLength` in strict mode~~ — **accepted and enforced**: the model stopped the field
   at exactly 40 characters, mid-sentence. Do not use `maxLength` for prose (it cuts
   sentences); keep length limits in the prompt and in Pydantic / `writing.py`.
4. ~~Markdown links next to citations~~ — **yes, always**, in both modes, as
   `([domain](url))`, plus `**bold**` in plain text. URLs carry `utm_source=openai`. R5
   handles both.
5. **Measure (first numbers, small prompts):** with `web_search` (`max_tool_calls: 3`):
   16–17 s, about 15–18k input tokens (search content), about 850 reasoning tokens. Without
   search: 2–3 s, 26–60 reasoning tokens. Still to measure on real scan contexts and chat
   bundles before setting `AI_TIMEOUT_SECONDS`. Note: the model repeated the same query
   twice in one call; `max_tool_calls` counts calls, so duplicates waste budget.
6. ~~Decide: fix-record TTL values~~ — 14 days / 2 days (R3).
7. ~~Decide: a per-organisation daily cap~~ — none for now (2026-10-23): only two
   organisations exist (the real one and the local test one). The per-user limit is
   enough; spend is read by hand from `ai_usage`. Add an organisation question cap if
   usage grows.
8. **Unverified:** whether `open_page` and `find_in_page` are billed as separate searches.
9. ~~Decide: Home review and "Explain this scan" content~~ — decided (information plan;
   DESIGN.md §18).
10. ~~Decide: chat guardrails~~ — decided in R4.
10a. ~~Design~~ — done: [`DESIGN.md`](DESIGN.md), from the
    [scan visual cues canvas](https://claude.ai/artifact/UVnbjzroi7jkG1Xz6BsWFf).
11. ~~Decide: how lists render~~ — decided in "Voice rules".
12. ~~Linear issues~~ — none (owner decision, 2026-10-23). This PRD supersedes DMI-163
    and DMI-169; work is tracked in these specs only.
