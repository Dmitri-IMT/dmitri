# Project Peirce — Personal AI Workspace

**Plan & Roadmap (v0.1)**
Engine: Pi (coding-agent harness, MIT) · Owner: you · Form factors: CLI first → messaging → webview

---

## 0. How to read this

This is a build plan treated like real software: it goes from inception → requirements → architecture → iterative delivery → hardening → deployment → maintenance. It is deliberately phased so you ship a *working spine* early and bolt domains on one at a time. Do **not** try to build the whole feature list at once — the architecture below is designed so each domain is a near-identical increment.

A blunt reality check up front (see §11): the full vision is a multi-year solo project. The point of this doc is to make it *incremental and safe*, so that even if you stop at Milestone 4 you have something genuinely useful.

---

## 1. Vision & non-goals

**North star.** A single, self-hosted, privacy-first personal agent — "Peirce" — that you own end to end. It is your coding agent *and* your life assistant. You reach it three ways: terminal (now), a messaging bridge (Telegram/WhatsApp), and later a web workspace. It remembers you, validates before it changes anything, and never silently mutates your data or your money.

**Explicitly out of scope (non-goals):**
- Peirce never executes financial transactions (no trades, transfers, purchases of securities). It *tracks* what you tell it. (See finance module.)
- Peirce never gets raw write access to your database (see §4.5).
- No telemetry leaves your machine without an explicit, audited decision.
- Not a product for other users (yet). Single-tenant. This removes a huge amount of auth/multi-user complexity — keep it that way as long as possible.

---

## 2. Guiding principles (these constrain every later decision)

1. **CLI-first, extend deeply, webview last.** Prove every capability in the terminal before adding a UI. The webview is a *view* over the same engine, not a second implementation.
2. **Pi is a pinned dependency, not a fork.** You customize through extensions/skills/prompts, never by editing Pi's core. (Rationale established earlier; reinforced by the Earendil acquisition — see §4.1.)
3. **The agent talks to data through a typed access layer, never raw SQL.** This is the single most important architectural decision (§4.5).
4. **Mutation = confirmation.** Any write to memory or the database is proposed, shown to you, and committed only on approval. Deletes are soft by default; hard deletes need a second confirmation.
5. **Everything is recoverable.** Append-only audit log + automated backups + version-controlled exports. Assume the agent will one day try to delete everything.
6. **One pattern, many domains.** Library, fitness, finance, notes, trips… are all the same shape: a skill set + a few tables + a confirmation gate + (later) a web surface. Build the pattern once.

---

## 3. SDLC framing

| SDLC phase | What it maps to here |
|---|---|
| Inception / feasibility | §1–§2, plus the Cursor & messaging spikes in §5 |
| Requirements | §6 (functional) + §8 (non-functional) |
| Architecture & design | §4–§5 |
| Iterative implementation | §7 milestones (each = design → build → test for one increment) |
| Verification | §8.3 testing strategy, run continuously |
| Deployment | self-host milestone (M4 messaging, M9 server) |
| Maintenance | §8 backups/observability + ongoing Pi-version audits |

---

## 4. Phase 0 — Foundations (do this before any feature)

### 4.1 Pin and audit Pi
Pi was acquired by Earendil (a venture-backed public-benefit company; Mario Zechner joined them). Pi stays MIT today, but the owners have signaled some future Pi-adjacent parts may be Fair Source or proprietary. Practical consequences:
- **Pin** a specific known-good MIT version in your repo. Don't auto-update blindly.
- **Audit** the pinned version for any telemetry/network calls before you trust it with personal data. Document what you find.
- **Keep an exit hatch:** because it's MIT, you can fork your pinned version if the project's direction changes. You don't need to act on this now — just keep the pin clean so a fork is always possible.

### 4.2 Repo & layout (single workspace repo)
```
peirce/
  .pi/                  # project-local Pi config: extensions, skills, prompt templates
  SYSTEM.md             # rebrand + core behavior (see 4.3)
  AGENTS.md             # project context Peirce loads at startup
  packages/
    dal/                # the Data Access Layer (typed query functions) — 4.5
    skills/             # domain skills, namespaced (library/, finance/, notes/…)
    gateway/            # messaging bridge (later)
    server/             # web server + RPC bridge to Pi (later)
    web/                # webview frontend (later)
  data/
    peirce.db           # SQLite (start here)
    backups/            # automated snapshots
  scripts/              # backup, restore, audit, migrations
```
Pi-the-engine stays in `node_modules` (pinned). Your self-modifications land in `.pi/` and `packages/skills/` and get committed — so "the agent improving itself" is captured in version control.

### 4.3 Rebrand to "Peirce" (without forking)
Do it through `SYSTEM.md` (Pi supports replacing/appending the system prompt per project) and the agent's name/identity in config + theme. Never patch Pi's source to rename it.

### 4.4 Secrets management
You'll accumulate keys: LLM providers, email OAuth tokens, market-data API, messaging bot tokens. Decide now:
- Use a single `.env` that is **git-ignored**, loaded by the DAL/skills, never passed into prompts.
- Never let the agent read the raw secret store; give it *capabilities* (e.g., "send email") not credentials.

### 4.5 The database access decision (RESOLVED RECOMMENDATION)
You flagged this as an open decision. Recommendation: **the agent never touches the database directly.** Instead:

- A **Data Access Layer (DAL)**: a set of typed functions exposed to the agent as skills/tools — `library.addBook`, `finance.logExpense`, `notes.search`, etc. Each internally runs **parameterized** queries.
- The agent calls these functions with structured arguments. It cannot write free-form SQL.

**Why:** prevents SQL injection from a hallucinated query, makes destructive operations *impossible to express by accident*, gives you one choke point for the confirmation gate and the audit log, and — critically — the **webview reuses the exact same DAL**, so you never write data logic twice.

**Tradeoff:** more upfront work defining the function surface; less ad-hoc querying. **Mitigation:** add one *read-only*, sandboxed query skill for exploratory reads if you miss it — but never a raw write path.

### 4.6 Guardrails & backups (build the framework before the features)
- **Confirmation middleware** in the DAL: every mutating call returns a "proposed change" the agent must surface to you; commit only on explicit yes.
- **Soft deletes** everywhere (`deleted_at` column); hard delete is a separate, double-confirmed path.
- **Append-only audit log** table: who/what/when for every mutation.
- **Backups:** scheduled SQLite snapshots to `data/backups/`, plus periodic human-readable exports (Markdown/JSON) committed or pushed off-box. A `scripts/restore` you've actually tested.

---

## 5. Architecture

### 5.1 Components
```
            ┌─────────────────────────────────────────────┐
            │                  Peirce                      │
            │            (Pi engine, pinned)               │
            │  SYSTEM.md · skills · prompt templates       │
            └───────────────┬─────────────────────────────┘
                            │ calls (structured args only)
                ┌───────────▼───────────┐
                │   Data Access Layer    │  ← confirmation gate
                │  typed query functions │  ← audit log
                └───────────┬───────────┘
                            │ parameterized SQL
                        ┌───▼────┐
                        │ SQLite │  (domain-namespaced tables)
                        └────────┘
   Interfaces (all drive the SAME engine + DAL):
   • CLI (now)        • Messaging gateway (Telegram→WhatsApp)
   • Web server + webview (later, via Pi RPC/SDK)
```

### 5.2 Engine bridges you'll rely on
Pi already ships the seams you need, so you don't hand-roll a runtime:
- **Programmatic SDK** (`createAgentSession`, `SessionManager`, `ModelRegistry`, `AuthStorage`) — for embedding the agent in the gateway and server.
- **RPC mode over stdin/stdout** (LF-delimited JSONL) — clean bridge for non-Node interfaces and for the webview backend.
- **`pi-ai` cross-provider context handoff** — lets a conversation move between Claude/GPT/Gemini mid-thread; useful for model routing and the Council module.

### 5.3 Two modes: Agent vs Assistant
Implement as two **profiles**, not two apps:
- **Agent (coding) mode:** your dev workflow — full file/bash tools, coding skills, your IDE terminal.
- **Assistant (life) mode:** the personal-assistant skills (library/fitness/finance/…), file/bash tools *restricted or off*, the brain/memory active by default.

Each profile = its own `SYSTEM.md` + a scoped skill set + (optionally) a different default model. This also solves your skill-clutter worry (next).

### 5.4 Skill organization (your "/" clutter problem — solved)
Pi loads skills **on-demand with progressive disclosure**, so you don't have to show everything at once. Strategy:
- **Namespace** skills by domain (`library:add`, `finance:log`, `notes:search`).
- **Scope by mode/context** — assistant mode surfaces only assistant skills; coding mode only coding skills.
- Use **prompt templates** (`/name`) for the handful of flows you trigger constantly.
- Result: the palette stays short and relevant. Don't flatten everything into one global list.

### 5.5 Cursor integration — refined
You guessed this would be hard. Good news: a community Pi extension already does most of it. `@netandreus/pi-cursor-provider` is a Pi custom provider that **routes model requests through the Cursor Agent CLI**, letting you use your Cursor-subscription models (Claude, GPT, Gemini, Grok, Composer) inside Pi with **no separate API keys** — auth is your normal Cursor login via the CLI.

How it works and what to weigh:
- Each Pi turn spawns a Cursor Agent CLI subprocess; it serializes your conversation into a prompt and reads the CLI's streamed JSON back. So: **subprocess-per-turn latency**, and **context is passed as a serialized transcript** rather than native message objects — fine for many tasks, weaker for very long contexts.
- **Alternative:** the official **Cursor SDK** (`@cursor/sdk`, `Agent.create({ model: { id: "composer-2" }})`). But it authenticates via a **Cursor API key**, and SDK/CLI usage draws on Cursor's token pool — so it may bill differently from "just using my subscription." Verify how your plan is metered before relying on it.
- **Risk to check:** driving a subscription programmatically can brush against Cursor's terms of service. Confirm before you build a workflow that depends on it.
- **Recommendation:** spike the existing extension first (an afternoon), decide if the transcript-serialization tradeoff is acceptable for your coding workflow, and only build something custom if it isn't.

### 5.6 OpenClaw / Hermes
OpenClaw is built *on* Pi (same engine), so its patterns transfer directly — study it as a reference for productizing Pi, not as a dependency. Hermes (Nous Research) is Python and a different runtime; per the earlier analysis, treat it as a **reference design for the self-evolving learning loop** (skill distillation, cross-session recall, a curator that prunes skills) which you reimplement as Peirce skills — or run Hermes as a service behind its OpenAI-compatible endpoint if you want its loop wholesale. This feeds the "brain" and "self-evolving memory" modules (M1, M7).

---

## 6. Functional requirements — domain modules

Each row is one increment of the same pattern. "Confirm?" = needs the mutation gate. "Web later" = gets a webview surface in M10.

| Module | Core capability | Tables (namespaced) | Mutations need confirm? | External dep |
|---|---|---|---|---|
| Brain / Memory | Remembers you; validates before saving; self-evolving (proposes saves, you approve) | `memory_*` | Yes (always) | — |
| Notes / Ideas / Tasks | CRUD notes/ideas/tasks; recall by query; reminders | `notes`, `ideas`, `tasks` | Write yes / read no | (calendar later) |
| Library | Goodreads-style shelves; reading sessions + per-session ideas; query what you read | `books`, `shelves`, `reading_sessions` | Write yes | (book metadata API optional) |
| Finance | Log income/expenses; track holdings you *report*; net-worth view; price fetch only | `accounts`, `transactions`, `holdings` | Write yes | market-data API (read-only) |
| Fitness | Goals, exercises, meals; daily check-in messages | `workouts`, `meals`, `goals` | Write yes | messaging gateway |
| Email | Read, triage/tag urgency, summarize, draft replies; multi-account client | `email_meta` (not bodies) | **Send = explicit yes** | IMAP/Gmail OAuth |
| Council | Personas (philosophers, founders…) chat with you about your life | uses memory + `personas` | Save insights = yes | (multi-model optional) |
| Study | Topic-separated learning using proven techniques (spaced repetition, etc.) | `topics`, `cards`, `reviews` | Write yes | — |
| Trips | Places-to-visit planner; auto-creates a city when you mention one | `cities`, `places` | Write yes | maps/geocoding API |
| Deep Research | Multi-step research → produces an HTML report you can open in the webview; steerable | `research_runs` | — (output is a file) | web search |
| Docs/Slides/Photo | Markdown-first editing; export to formats; "beautify" button | files + `documents` | Save yes | format/export libs |
| Web automation | Order food, buy things, etc. via a controlled browser instance | `actions_log` | **Always yes, high-bar** | headless browser |
| Kanban | Board view over `tasks`, agent-native | reuses `tasks` | Write yes | — |

---

## 7. Roadmap — milestones

Each milestone has a **goal**, **deliverables**, and an **exit criterion** (how you know it's done). Ship in order; resist jumping ahead.

### M0 — Foundations
**Goal:** safe ground to build on.
**Deliverables:** §4 in full — pinned+audited Pi, repo layout, `SYSTEM.md` rebrand, secrets, the DAL skeleton with confirmation gate + audit log, working backup/restore scripts.
**Exit:** you can run `peirce` in the terminal as a renamed agent; a dummy `notes.add` write is proposed, confirmed, logged, and recoverable from a backup.

### M1 — The spine: assistant profile + brain
**Goal:** a real personal assistant with memory and guardrails, even with zero domains.
**Deliverables:** Agent/Assistant profiles (§5.3); the Brain module — durable facts about you, with the *propose-then-confirm* save loop (the seed of self-evolution); skill scoping (§5.4).
**Exit:** Peirce recalls validated facts across sessions and asks permission before remembering anything new.

### M2 — Notes / Ideas / Tasks
**Goal:** prove the domain pattern end to end on the simplest CRUD.
**Deliverables:** three tables, DAL functions, skills, recall-by-query, simple reminders.
**Exit:** "log this idea", "what tasks do I have", "remind me about X" all work via the DAL with confirmation on writes.

### M3 — Library + Finance
**Goal:** a content-rich domain (library) and an external-API domain (finance, read-only).
**Deliverables:** shelves + reading sessions + session-ideas recall; income/expense logging; report-only holdings + price fetch + net-worth summary. **Hard rule:** no transaction execution.
**Exit:** "I read chapter 3 of X and thought Y" is retrievable later; "I earned salary, spent 25 on lunch, I hold N shares of Z" produces a correct net-worth view.

### M4 — Messaging gateway (remote access)
**Goal:** reach Peirce without your PC. **Start with Telegram** (Bot API is trivial); add WhatsApp later (Business API / harder).
**Deliverables:** gateway package embedding the Pi SDK; route messages → agent → DAL; daily fitness check-in messages (activates the Fitness module's outbound side).
**Exit:** you text Peirce "spent 30 on dinner" from your phone and it lands in the DB (after confirm).

### M5 — Email handler
**Goal:** the first genuinely complex integration.
**Deliverables:** read/triage/urgency-tagging, summaries, draft replies, multi-account. **Sending requires explicit per-message confirmation.** Store metadata, not full bodies, in the DB.
**Exit:** Peirce flags urgent mail and drafts a reply you approve before it sends.

### M6 — Fitness (full) + Study + Trips
**Goal:** breadth — three more domains on the proven pattern.
**Exit:** workout/meal logging + motivation messages; spaced-repetition study per topic; trip planner that auto-creates a city from "saw a video about Lisbon, add it."

### M7 — Council + self-evolving memory
**Goal:** the "interesting" layer.
**Deliverables:** persona definitions + multi-persona conversation; the learning loop (skill/insight distillation à la Hermes) that *proposes* saves and waits for your validation.
**Exit:** a persona chat surfaces an insight, Peirce asks to remember it, you approve, and it's recalled later.

### M8 — Deep Research
**Goal:** Odysseus-style research output.
**Deliverables:** multi-step research skill, steerable mid-run, that emits a standalone **HTML report**; conversational follow-up over the result.
**Exit:** a research run produces an HTML file you can open and then discuss.

### M9 — Webview foundation
**Goal:** the browser workspace begins — and reuses everything.
**Deliverables:** `server` package bridging the web app to Pi via **RPC/SDK**; the web app calls the **same DAL** as the CLI; auth for local/remote access; render M8's HTML reports.
**Exit:** a localhost chat that mimics the CLI, backed by the identical engine and data.

### M10 — Webview domain UIs
**Goal:** the visual surfaces.
**Deliverables:** dashboards/graphs (finance net-worth, reading stats), the **Kanban board**, the email client UI (Summarize / AI-reply buttons), Markdown-first **docs/slides/photo** editors with export + "beautify."
**Exit:** each domain has a view that reads/writes through the shared DAL.

### M11 — Web automation (gated, last)
**Goal:** real-world actions (order food, buy things).
**Deliverables:** a controlled headless-browser capability behind the **highest-bar confirmation** and a full action log. Treat as inherently risky; ship narrow and supervised.
**Exit:** a single, well-scoped action (e.g., one food order) completes only after explicit confirmation, fully logged.

---

## 8. Cross-cutting concerns (run through every milestone)

### 8.1 Security
- Single-tenant, local-first; nothing exposed publicly until M9, and then behind real auth.
- Agent holds capabilities, never raw secrets (§4.4).
- Email/web-automation are the high-risk surfaces — confirmation-gated, metadata-minimizing, logged.

### 8.2 Backups & recovery
- Scheduled SQLite snapshots + periodic Markdown/JSON exports pushed off-box.
- Tested `restore`. A backup you've never restored is a guess, not a backup.
- Soft-delete default; hard-delete double-confirmed.

### 8.3 Testing strategy
- **DAL:** unit-test every function, especially that destructive paths require confirmation and that queries are parameterized. This is your safety-critical layer — highest coverage here.
- **Skills:** golden-prompt tests — given an instruction, assert the agent calls the right DAL function with the right args (mock the DAL).
- **Guardrails:** explicit tests that "delete everything"-style instructions are refused/soft/confirmed.
- **Integration:** seed DB → run a scripted conversation → assert end state + audit log.

### 8.4 Observability
- The audit log doubles as your activity feed.
- Structured logs per turn (model, tokens, tools called, cost) — cost adds up across providers.

---

## 9. Open decisions you still need to make

| # | Decision | Recommendation |
|---|---|---|
| 1 | DB access pattern | DAL only, no raw agent SQL (§4.5) — recommended, resolved |
| 2 | Skill organization | Namespace + mode-scope + on-demand loading (§5.4) — recommended |
| 3 | Messaging first | Telegram first, WhatsApp later (M4) |
| 4 | Cursor path | Spike the existing extension before building custom (§5.5) |
| 5 | Cursor ToS / billing | Verify subscription-vs-API-key metering and terms before depending on it |
| 6 | DB engine | Start SQLite; migrate to Postgres only if/when the webview needs concurrency |
| 7 | Hosting (post-M9) | $5 VPS or a home box; decide based on whether you want 24/7 messaging |
| 8 | Self-evolution autonomy | Always propose-then-confirm; no silent writes — recommended |

---

## 10. Recommended stack

- **Engine:** Pi (pinned MIT) + `pi-ai` for model routing.
- **Language:** TypeScript/Node throughout (matches Pi; one language for engine, DAL, server, web).
- **DB:** SQLite (`better-sqlite3`) → Postgres later if needed.
- **Web (M9+):** Next.js (you already know it) for the webview; server bridges to Pi via RPC/SDK.
- **Messaging:** Telegram Bot API → WhatsApp Business API later.
- **Market data:** any read-only quotes API for the finance module.
- **Editors (M10):** Markdown core + export libs (docx/pptx/pdf) behind a "beautify/export" action.

---

## 11. Reality check & sequencing advice

- This is large enough that **the win is in stopping points**, not in finishing. M0–M3 alone (a renamed, memory-having assistant that tracks notes, books, and money safely) is already worth using daily.
- **Build the pattern once (M0–M2), then domains are cheap.** If a new domain takes more than "a few tables + a few DAL functions + a skill," your architecture has drifted — stop and refactor.
- **The webview is a multiplier, not a foundation.** Every hour spent making the CLI + DAL clean pays off twice when the web app reuses them. Resist starting the UI early.
- **Self-evolution stays on a leash.** The most exciting feature (an agent that rewrites itself and edits its own memory) is also the one most likely to corrupt your data. Propose-then-confirm, soft deletes, and tested backups are what make it safe to enjoy.
