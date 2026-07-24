# Backend — decisions

> **Purpose:** work through backend decisions here. The code in `backend/` is a **starting point**,
> not the source of truth — reuse what fits, replace what doesn't.
>
> **ADRs** ([`docs/adr/`](../adr/)) record **completed, locked** architecture only. Open choices
> stay in this file until you ship and are ready to formalize.
>
> **Also see:** [`AUTH.md`](AUTH.md) (phased identity) · [`docs/cloud/`](../cloud/README.md) · [`docs/epics/EPICS.md`](../epics/EPICS.md)
>
> **Neighbours:** [`PI.md`](PI.md), [`FRONTEND.md`](FRONTEND.md), [`SECURITY.md`](SECURITY.md), [`AI.md`](AI.md).

---

## Decision log

| ID | Topic | Status | Notes |
|----|-------|--------|-------|
| B1 | User model (organizational) | ✅ | Multi-user, single org; `org_id` — [B1](#b1--user-model-organizational-) |
| B2 | Agent auth | ✅ | HMAC September — [`AUTH.md`](AUTH.md) Phase 1 |
| B3 | Frontend auth | ✅ | [`AUTH.md`](AUTH.md) Phase 1 |
| B4 | Database hosting | ✅ | Supabase → AWS RDS; [B4/B5](#b4--b5--hosted-stack-) |
| B5 | App hosting | ✅ | Railway → AWS; single `nspi` env for September |
| B6 | Pi command channel | ✅ | [B6](#b6--pi-command-channel-) — [`ADR-011`](../adr/ADR-011-pi-command-channel.md) |
| B7 | OpenAPI vs reality | ✅ | September slice — [`ADR-011`](../adr/ADR-011-pi-command-channel.md), `contracts/openapi/` |
| B8 | Reuse `backend/` code | ✅ | Keep the enrichment/scoring engine; discard the app shell — [Reuse](#reuse-from-backend-code-) |
| B9 | Hosted vs enterprise | ✅ | Hosted v1; enterprise deal-driven — [B9](#b9--hosted-vs-enterprise-) |
| B10 | September MVP scope | ✅ | **Scenario B — Control** — [B10](#b10--september-mvp-) |
| B11 | Frontend contract asks | 🔓 | 14 contract gaps + 1 self-contradiction — [B11](#b11--frontend-contract-asks-) |
| B12 | Transactional email | 🔓 | Decided (invites + password reset); **provider and sending domain TBD** — [B11-C17](#b11--frontend-contract-asks-) |

✅ = decided here · 🔓 = open (auth details → [`AUTH.md`](AUTH.md))

---

## B1 — User model (organizational) ✅

**Decision:** multi-user, **single org** for NSPi. Operators in that org share the same scans,
devices, and Pis.

| Decided | Not decided (see [`AUTH.md`](AUTH.md)) |
|---------|----------------------------------------|
| Multi-user, single org for NSPi pilot | — |
| `org_id` on tenant-owned data from first identity migration | — |
| Invite-only signup; roles `admin` / `viewer` | — |
| Pi HMAC; passwords; sessions (7-day fixed refresh) | Device secret rotation (Phase 2) |
| Device secrets: B2B installer provisioning | Self-service Pi pairing (if needed later) |
| Design toward many orgs + enterprise later | — |

---

## B2 + B3 — Authentication ✅

**Decided** — **[`AUTH.md`](AUTH.md) Phase 1.** Implement in code; update ADR-005 when shipped.

| Area | Status |
|------|--------|
| Pi HMAC (ingest + WSS) | ✅ |
| Login, invites, roles | ✅ |
| Passwords (policy, breach screening, reset — no forced rotation, [`ADR-015`](../adr/ADR-015-password-policy.md)) | ✅ |
| Sessions (15 min access, 7-day refresh, server logout) | ✅ |
| Device secrets (installer provisioning) | ✅ provision model; Pi secret rotation Phase 2 |

Cross-cutting: [`SECURITY.md`](SECURITY.md).

---

## B4 + B5 — Hosted stack ✅

**NSPi (September):** **Supabase** (Postgres) + **Railway** (API, worker, frontend). **AWS staging**
in parallel; prod cutover only after smoke parity.

### Hosting details ✅

| Topic | Decision |
|-------|----------|
| **Frontend (NSPi)** | **Railway static** — same Railway project as API/worker |
| **Environments** | **Single `nspi` env** for September |
| **Region** | Same broad region for Supabase + Railway; closest to operators/Pi — document in [`docs/cloud/`](../cloud/README.md) |
| **Supabase runtime** | Pooler **6543** (transaction mode) for API + worker |
| **Supabase migrations** | Direct **5432** for Alembic only |
| **Supabase plan** | **Pro** (or keep active) before September — free tier pauses when idle |
| **Railway** | Two services: `api`, `worker` |

### Code portability (Supabase/Railway → AWS)

Same application code; env URLs and deploy config change only. AWS config in `infra/aws/`.

### AWS parallel track — schedule + weekly review

See prior week-by-week plan in git history or expand in [`docs/cloud/`](../cloud/README.md). Weekly 30 min: app requirements → infra progress → blockers → one deliverable.

---

## B6 — Pi command channel ✅

**In September** ([B10](#b10--september-mvp-) = Control). Roadmap decisions below; frame/DDL detail → **ADR-011** + OpenAPI ([B7](#b7--openapi-contract-)).

**Transport ✅:** **Option C — outbound WebSocket** ([`PI.md`](PI.md)). Pi daemon dials backend and keeps connection open; commands pushed when Pi is online.

**Command contract ✅** (September v1):

### Lifecycle (3a — full)

`queued` → `delivered` → `running` → `uploading` → `done` · `failed` · `expired`

| State | Meaning |
|-------|---------|
| `queued` | Row created; delivery not yet confirmed on WS |
| `delivered` | Command message sent on open WebSocket |
| `running` | Pi acknowledged; scan pipeline active |
| `uploading` | Scan finished locally; `POST /scans` in flight |
| `done` | Ingest succeeded |
| `failed` | Command **reached the Pi** and then broke: error reported by Pi, ingest failure, WS drop mid-scan, or stale `running` past the timeout |
| `expired` | Command **never reached the Pi**: delivery gave up after the 2 retries (set at the same moment the trigger returns `503 device_offline`) |

**The dividing line is `delivered_at` (C12, decided 2026-07-13).** Not the timeout duration — *whether the
Pi ever took the job*. Never delivered → `expired`; delivered then broke → `failed`. This is why
`expired` needs **no timeout sweeper**: it is set synchronously at enqueue when delivery fails.

### Payload (3b)

Backend generates **`command_id`** and **`scan_id`** at enqueue. Pi must use the given `scan_id` in the ingest payload.

| Field | Source |
|-------|--------|
| `command_id` | Backend (UUID) |
| `scan_id` | Backend (UUID) — assigned at enqueue |
| `agent_id` | Backend (target Pi — `agents` table) |
| `scan_mode` | ~~Operator~~ → **product picks `quick`**; the other four are not surfaced in the UI ([`FRONTEND.md`](FRONTEND.md), [`ui/FLOWS.md` B4](../ui/FLOWS.md#b4--scan-now-command-flow)) |
| `subnet` | ~~Operator — CIDR~~ → **`agent.target_subnet`**, chosen once on AGENTS. See [B11-C2](#b11--frontend-contract-asks-) |

> ⚠️ **Revised 2026-07-13.** This table assumed the operator supplies `scan_mode` and `subnet` at
> trigger time. **They cannot supply `subnet`:** the user is a non-technical org admin who does not
> know their CIDR, and the Pi is deliberately **dual-homed** ([NSPi field
> test](../tests/nspi-september/plan.md)) — ethernet on the target subnet with no default gateway,
> wifi for internet — so it sees two networks and cannot guess either. The choice is made **once**,
> by a human, and stored on the agent. See [B11-C2](#b11--frontend-contract-asks-).

### Delivery when operator clicks "Scan now" (3c)

- **Pi online** (open WS): deliver immediately → `delivered` → `running`.
- **Pi offline:** backend **retries delivery up to 2 times**; then reject — **`503`** + `code: device_offline` — frontend toast: *"Pi seems to be offline."* No queue-for-later in v1.

### Concurrency (3d)

**One scan at a time** per Pi. If a command is `running` (or `uploading`), reject new trigger — **`409`** + `code: device_busy` — frontend toast or inline error (copy TBD).

### Failure & timeout (3e)

- **No resume** — scans are not resumable.
- **`running` without progress / dead Pi:** mark **`failed`** after timeout — the Pi *took* the command, so this is a broken scan, not an undelivered one. **How long** is tunable at implementation (ADR-011 / config) — not a product decision here.
- **WS drop mid-scan:** same timeout → `failed`; operator triggers again.
- **Undelivered after the 2 retries:** **`expired`**, set synchronously with the `503 device_offline` — never reached the Pi. This is the *only* path to `expired`; there is no second timeout for it.

### Idempotency (3f)

Pi treats **`command_id`** as idempotent: duplicate WS delivery → ack, do not re-run scan.

### API surface ✅

**Namespace (5a):** **`/agents/`** = scanner Pis (JWT reads + HMAC WSS). **`/hosts/`** = discovered network machines (JWT). **`/commands/`** = command lifecycle (JWT). OpenAPI today calls hosts **`/devices`** — rename in [B7](#b7--openapi-contract-).

**Transport:** production uses **HTTPS** and **WSS** only (TLS everywhere; local dev HTTP exception per ADR-005).

| Method | Path | Caller | Auth | Purpose |
|--------|------|--------|------|---------|
| **WSS** | `/api/v1/agents/{agent_id}/commands` | Pi daemon | HMAC on upgrade | Persistent connection; receive commands; send status |
| **POST** | `/api/v1/agents/{agent_id}/commands` | Web | JWT | **Scan now** — body: `scan_mode`, `subnet` (frontend sends `quick` + the agent's `target_subnet`) |
| **GET** | `/api/v1/agents` | Web | JWT | **List agents** — array of one in the MVP. 🔓 **missing** ([B11-C1](#b11--frontend-contract-asks-)); without it the frontend cannot discover `agent_id` |
| **GET** | `/api/v1/agents/{agent_id}` | Web | JWT | Agent detail — **`online`** (from WS registry), `last_seen_at`, `active_command_id`. 🔓 must also carry `available_subnets` + `target_subnet` ([B11-C2](#b11--frontend-contract-asks-)) |
| **GET** | `/api/v1/commands/{command_id}` | Web | JWT | Command lifecycle |
| **GET** | `/api/v1/hosts/…` | Web | JWT | Host inventory *(OpenAPI `/devices` → `/hosts` in B7)* |
| **POST** | `/api/v1/scans` | Pi | HMAC | Upload scan results *(exists in OpenAPI)* |
| **GET** | `/api/v1/scans/{scan_id}` | Web | JWT | Scan results when ready *(exists)* |

**Trigger errors** (distinct HTTP status + `code` for logs/metrics):

| Condition | HTTP | `code` | UI |
|-----------|------|--------|-----|
| Pi not reachable after 2 delivery retries | **503** | `device_offline` | Toast: *Pi seems to be offline.* |
| Scan already `running` / `uploading` | **409** | `device_busy` | Toast: scan in progress (copy TBD) |

**WebSocket messages (4e):** backend → Pi `command` payload; Pi → backend `status` updates. Large result payload stays on **`POST /scans`**, not WS.

### Data model ✅

**Two concepts (5a):** **`agents`** = Pis running `dmitri agent` (`agent_id` = HMAC `X-Device-Id`). **`hosts`** = machines discovered by scans (today's backend `devices` table / OpenAPI `DeviceSummary` — rename to `hosts` in B7).

```
org
 └── agents          ← Pi appliances, secrets, online/last_seen
      └── commands   ← "Scan now"
           └── scans  ← pre-created at enqueue (5c); filled on ingest
                └── hosts  ← discovered machines (ports, findings, …)
```

**`agents`** (5b): `agent_id` (PK, **UUID** — decided 2026-07-13; it must equal `X-Device-Id`, and every other id in the system is a UUID. Backend mints it at provisioning; `display_name` is what humans read), `org_id`, `display_name`, `secret_hash`, `revoked_at`, `last_seen_at`, `created_at`, **`target_subnet`** (🔓 [B11-C2](#b11--frontend-contract-asks-) — the network the operator chose to scan; nullable until chosen). **`online`** derived from open WS in API registry (5e) — not a persisted boolean. **`available_subnets`** is *reported*, not stored: the Pi sends its interfaces over the WS channel.

**`commands`** (5c): `command_id`, `org_id`, `agent_id` (FK), `scan_id` (FK), `scan_mode`, `subnet`, `status`, `requested_by` (audit, optional Phase 1), `error_code`, timestamps (`created_at`, `delivered_at`, `started_at`, `completed_at`).

**Enqueue (5c-A):** `POST …/agents/{id}/commands` inserts **`commands`** + stub **`scans`** row (same `scan_id`) before WS delivery.

**`org_id` (5d):** on `agents`, `commands`, `scans`; hosts scoped via `scan.org_id`.

**ADR-011 ✅:** [`ADR-011`](../adr/ADR-011-pi-command-channel.md) — WS typed envelope, HMAC upgrade, stub scan `pending`, `/hosts` rename, timeouts config-only, single API replica NSPi.

Auth → [`AUTH.md`](AUTH.md). Pi runtime → [`PI.md`](PI.md). Trigger UX → [`FRONTEND.md`](FRONTEND.md).

---

## B9 — Hosted vs enterprise ✅

**B9a — Hosted:** Supabase + Railway for NSPi; AWS staging parallel.

**B9b — Enterprise:** deal-driven — customer cloud + SSO; no build until signed need.

---

## B10 — September MVP ✅

**Target:** September. **Stack:** B4/B5.

**Decision:** **Scenario B — Control** — hosted pipeline + **scan-from-web** (B6) + read UI. Defers LLM only.

| Scenario | Product | Defers |
|----------|---------|--------|
| **A — Observability** | Hosted pipeline; Pi push; read-only web | Command channel (B6); LLM |
| **B — Control** ✅ | A + scan-from-web (B6) | LLM |

**Auth for September:** [`AUTH.md`](AUTH.md) Phase 1 ✅ — implement in code.

Minimum technical path:

- [ ] **Pi hardware acquired and base-configured** — see [`PI.md`](PI.md) (blocker: no Pi in possession today)  
- [ ] Supabase + Railway `nspi` live  
- [ ] Alembic + identity schema per [`AUTH.md`](AUTH.md) Phase 1  
- [ ] Pi daemon + Pi → backend ingest (HMAC per AUTH Phase 1)  
- [ ] Command queue + "Scan now" E2E (web → backend → Pi → results → web)  

---

## B11 — Frontend contract asks 🔓

**Raised 2026-07-13 (DMI-54)** by breadboarding the UI against
[`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml). Each gap blocks a flow in
[`ui/FLOWS.md`](../ui/FLOWS.md#contract-asks); none are frontend-solvable. The UI is designed and
waiting.

**The big one: there is no `/users` path in the contract at all.** Not a missing field — a missing
resource. `POST /invites` and `POST /invites/{token}/accept` are the *only* identity-adjacent write
routes, and `LoginResponse` returns a bare token with no user object. This leaves **USERS & INVITES
mostly unbuildable** as breadboarded (B1 promised "multi-user, single org… invite-only signup, roles
`admin`/`viewer`" — the UI to operate that does not have endpoints), and leaves a logged-in user
unable to see or change their own profile.

**And it goes one level deeper than "no profile page" (C16):** with no user object anywhere, the
frontend has **no documented way to learn the logged-in user's role** — so it cannot decide whether
to render `[Scan now]`, the `Users` nav item, or the invite form. The entire `admin`/`viewer` split
promised in [B1](#b1--user-model-organizational-) and [`AUTH.md`](AUTH.md) rests on a JWT claim that
the contract never specifies. That is the cheapest fix on this list and the one that unblocks the
most screens.

| # | Ask | Blocks | Notes |
|---|-----|--------|-------|
| **C1** | `GET /api/v1/agents` — list agents | AGENTS, "Scan now" | Array of one in the MVP. `agent_id` is the provisioning `X-Device-Id`, so the frontend has **no way to discover it**. Cheap, and correct under [B1](#b1--user-model-organizational-)'s "design toward many orgs". |
| **C2** ◐ | `AgentDetail.available_subnets` + `target_subnet`, and a way to set it | AGENTS, "Scan now", first-run | **WS half LOCKED 2026-07-13:** the Pi sends a **`hello` frame on connect** with `available_subnets` (`interface` + `cidr`) — in the contract and in [`ADR-011` §3](../adr/ADR-011-pi-command-channel.md). Decided *now*, while the envelope was being defined, rather than reopening it later. **HTTP half still open:** surfacing them on `AgentDetail` + the endpoint an admin uses to pick one, once. `agents` table gains `target_subnet`; `POST /commands` is unchanged. |
| **C3** | `GET /users/me` (+ update) | SETTINGS → profile | No `/users` resource exists. Unknown whether the user model even has a `display_name`. |
| **C4** | Users & invites: list users, list pending invites, change role, revoke invite | USERS & INVITES | Only `POST /invites` exists. The whole admin surface in [`ui/FLOWS.md` B2](../ui/FLOWS.md#b2--admin-day-one-invite--first-scan) has no endpoints behind it. |
| ~~**C5**~~ | ~~Forced password change: 403 on expired-password login carries no token, but `POST /auth/change-password` requires Bearer~~ | — | **✅ MOOT 2026-07-23 — [`ADR-015`](../adr/ADR-015-password-policy.md) drops forced password rotation.** With no password expiry, this deadlock cannot occur: login is `200`/`401` only. No change needed. |
| **C6** | `HostSummary.first_seen_at` | HOME "new device" item | Item is **cut from v1** until this exists. **Cheap:** the field is already on `HostDetailResponse` — this is projecting an existing column into the list. |
| ~~**C7**~~ | ~~Does `POST /invites/{token}/accept` issue a session?~~ | — | **✅ RESOLVED 2026-07-13 — yes.** It returns `201` with a full `LoginResponse`, so ACCEPT INVITE auto-logs-in to HOME. (Expiry is **`410`**, not `400`.) `ui/FLOWS.md` B2 assumed the opposite and was corrected. No change needed. |
| ~~**C8**~~ | ~~`FindingRecord.cve_id`~~ | — | **✅ RESOLVED 2026-07-13** — `cve_id`, `cvss_score` and `references` all exist. No change needed. |
| **C9** | `host_id` on `DevicePayload` | SCAN DETAIL | The `devices` array on `ScanDetailResponse` has no id — only `ip`/`mac`/`hostname`/`vendor`. A host row on a scan therefore **cannot link to that host's page**. (Findings do carry `device_id`, so the id exists server-side.) |
| **C10** | A failed scan carries **no reason** | SCAN DETAIL, HOME | `ScanDetailResponse` has no error field. The UI must go `scan.command_id` → `GET /commands/{id}.error_code` — and `error_code` is a machine code, so it needs a **plain-language mapping** owned by the backend or the copy deck. A failed scan with a null `command_id` has no reason at all. B6 promised *"scan failed → readable failure reason"*; today that is unreachable. |
| ~~**C11**~~ | ~~Does `GET /findings?device_id=…` accept a `host_id`?~~ | — | **✅ RESOLVED 2026-07-13 — the filter becomes `?host_id=`.** The question only existed because the [B7](#b7--openapi-contract-) rename stopped at the paths; finishing it into the read-model field names dissolves it. Same identifier, one name. HOST DETAIL can show findings. |
| ~~**C12**~~ | ~~Dead Pi → `failed` or `expired`?~~ | — | **✅ RESOLVED 2026-07-13 — split on `delivered_at`.** Never delivered → **`expired`** (set with the `503`, no sweeper). Delivered then broke — Pi error, ingest failure, WS drop, stale `running` — → **`failed`**. Both statements in B6 were half-right; the [lifecycle table](#lifecycle-3a--full) and [Failure & timeout](#failure--timeout-3e) now say the same thing. **Not a contract gap** — `CommandStatus` already carries all seven states. |
| **C13** | Bad `current_password` → **400, not 401** | SETTINGS | `POST /auth/change-password` documents both. It must be **400**: a `401` trips the SPA's refresh interceptor ([`ADR-008`](../adr/ADR-008-frontend-stack.md) §Auth Client) and bounces the user to login for a mistyped field. Confirm or change. |
| **C14** | `GET /api/v1/invites/{token}` — read an invite before accepting | ACCEPT INVITE | The screen currently knows **nothing**: not the org, not the role, not the invited email. So (a) it cannot tell a stranger the link is legitimate, and (b) the invitee must **type their own email from memory** to match `AcceptInviteRequest.email` — a typo then fails identically to a dead link. Public route, single-use token, returns `{ email, role, org_name }`. |
| **C15** | Distinct `error.code`s on `POST /auth/reset-password`'s `400` | RESET PASSWORD | A **dead/used link** and a **weak password** share one status, and `ErrorBody.code` is an unconstrained `string`. The two need *opposite* instructions ("request a new link" vs "pick a better password"), and a stale link is this screen's most likely failure. Same treatment would help ACCEPT INVITE's `400`. |
| **C16** | **The user's role is nowhere in the contract** | **all role-gated UI** | `LoginResponse` is a bare token; no user object exists anywhere. [`ADR-008`](../adr/ADR-008-frontend-stack.md) §Papéis says the role rides in **JWT claims** — but the contract documents **no claims**, so the SPA would decode an unspecified payload to decide what to render. Every *absent, not disabled* decision depends on it: the `Users` nav item, `[Scan now]`, the network chooser, the invite form. **Either document the claims or return the role** (cheapest: fold into **C3**'s `/users/me`). |
| ~~**C17**~~ | ~~No email delivery exists anywhere~~ | — | **✅ DECIDED 2026-07-13 — transactional email is in scope. Provider TBD.** The backend sends **invite links** and **password-reset links**. <br>**Cost is small:** `httpx` is already a backend dependency, so no new library — a `services/mailer.py` plus two call sites (`POST /invites`, `POST /auth/forgot-password`), both already the points where a token is minted, and two plain-text templates. <br>**The real work is deliverability, not code:** a sending domain with **SPF + DKIM + DMARC**. A security product's one-time login link is structurally indistinguishable from phishing and will be filtered without them. <br>**Reset is what made this mandatory** — an admin can hand-carry an invite link, but a locked-out user has nobody in the loop. <br>**Invites keep the copyable link in the UI anyway** (email is the convenience, the link is the guarantee). <br>**Open:** pick the provider (Resend / Postmark / SES) and own the sending domain. |
| **C18** | `POST /invites` documents **only a `201`** | USERS & INVITES | No error responses at all. Inviting an address that **already has an account**, or that **already has a live invite**, is undefined behavior — and re-inviting is the likeliest repeat action on that screen. Needs a defined status + `error.code`. |

**Not asked for, deliberately:** a `GET /findings/{id}`. `GET /findings?scan_id=…` already returns
the full `FindingRecord` (description, recommendation, evidence), so finding detail renders from data
the screen already holds — [`REFERENCE.md` §12](../ui/REFERENCE.md), don't solve a problem you don't
have.

---

## B7 — OpenAPI contract ✅

**Decision:** **September slice** — update [`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml) to match B6 + AUTH Phase 1 **before** frontend type-gen. No `/devices` alias (breaking rename to `/hosts`; no consumers today).

Locked with [`ADR-011`](../adr/ADR-011-pi-command-channel.md): stub scan `200` + `status: pending`, typed WS envelope, HMAC upgrade same as ADR-005, auth + invite routes, trigger error `code`s.

**Baseline, not a freeze (decided 2026-07-13).** B7 originally said *freeze*. It was written before
[B11](#b11--frontend-contract-asks-) existed, and B11's asks each amend this same file **after** B7
lands — so "frozen" would be false the week it was declared. B7 delivers a **baseline**: correct
against every decision that exists the day it lands, and the thing the backend routes and the
frontend type-gen build from. Version stays `1.0.0`; B11's amendments follow it.

**`openapi.yaml` is the only contract artifact (decided 2026-07-13).** `contracts/schemas/*.json`
(`scan_result`, `device`, `finding`) were a **second, legacy definition of the ingest payload** — and a
duplicate is a drift generator: the contract's own ingest example had gone stale (`scan_mode: full`, a
mode that no longer exists) while the Pi's copy was correct. The schema files are **deleted**; the
enum-parity guard in `hardware-agent/tests/test_contract_models.py` now checks the Pi's Pydantic
`Literal` against **`openapi.yaml`**. The **typed WS frames live here too** (`AgentCommandFrame`,
`AgentStatusFrame`, `AgentHelloFrame`) — one file, one truth.

**The rename goes all the way into the field names.** `/devices` → `/hosts` is not just the paths:
the read model becomes `hosts[]`, `host_count`, `host_id` / `host_ip`, `?host_id=`. **The ingest
payload is the boundary and does not move** — `POST /scans` keeps `devices[]` / `DevicePayload` /
`devices_received` per [`ADR-011` §5](../adr/ADR-011-pi-command-channel.md), because the Pi already
emits them. *The Pi reports devices; the backend serves hosts* ([`CONTEXT.md`](../../CONTEXT.md)).
This closes [C11](#b11--frontend-contract-asks-).

---

## Reuse from `backend/` code ✅

**Context:** the current `backend/` was written by a prior contributor **before** the auth, frontend,
Pi-command-channel, and `contracts/` decisions existed. It is a standalone scan-result **scorer** —
it ingests a payload, enriches CVEs against KEV/EPSS/NVD, and assigns a risk score. **It is not wired
to the TUI and nothing calls it today.** Full rewrite is acceptable; this decision only records *what
domain code is worth carrying forward* vs. what should be discarded and rebuilt under the new
architecture.

**The line:** keep `services/` (the enrichment + scoring **engine**); discard the app **shell**
(`main.py`, the `db/session.py` stack, `config.py`, routers placeholder). The engine is portable
because it is mostly functions over a `Session` + records. The shell encodes a world with no auth, no
`org_id`, no Pi, and SQLite — none of which match where we are going (see [B6](#b6--pi-command-channel-),
[B7](#b7--openapi-contract-), [`AUTH.md`](AUTH.md)).

### Keep — real domain logic, reusable largely as-is

| Component | File | Why |
|-----------|------|-----|
| Risk scoring formula | `services/risk.py` | Self-contained; finding + KEV/EPSS → score + rationale. "Formula ownership" is editorial, not a code problem. |
| Enrichment job processing | `services/enrichment.py` | CPE→CVE and CVE→KEV/EPSS correlation — the hard part already solved. |
| External API clients | `services/nvd.py`, `kev.py`, `epss.py` | NVD/KEV/EPSS HTTP clients with TTL caching. Only the cache *storage* changes with the DB stack. |
| NVD parsing | `parse_nvd_matches`, `_severity_from_cvss` | Pure functions, zero infra coupling. |
| Finding dedupe/merge | `upsert_finding`, `finding_dedupe_key`, `_max_severity`, `_max_confidence` | Domain rules; survive any rewrite. |

### Keep with changes — right shape, stale wiring

| Component | Survives / changes |
|-----------|--------------------|
| `persist_scan()` (`services/persistence.py`) | Ingest+normalize logic is good and contract-aligned. Changes: add `org_id`; link to `agents`/`commands`; revisit mid-function `commit()`s. |
| Data model (`models/persistence.py`) | scan→device→port→service→cpe→finding→risk tree is sound. Changes: `devices`→`hosts` rename ([B6](#b6--pi-command-channel-)), add `org_id`, drop `create_all` (Alembic-managed). |
| Worker loop (`worker.py`, `worker_main.py`) | Poll loop + `FOR UPDATE SKIP LOCKED` is a keeper. Run against the real DB stack; respect org scoping. |
| Pydantic scan schemas (`schemas/scan.py`) | Aligned with `contracts/schemas/`. Reconcile *from* the contract — the contract is source of truth ([B7](#b7--openapi-contract-)), not these. |

### Discard — predates current decisions, rebuilt anyway

| Component | Why |
|-----------|-----|
| `main.py` (as written) | Monolith; all routes + serializers in one file, empty `routers/`, open CORS, no auth. Routes get rewritten under auth middleware. Salvage the `_serialize_*` helpers as reference only. |
| `db/session.py` stack assumptions | SQLite default + `create_all()` in lifespan. Replaced by Postgres + Alembic. |
| `config.py` (as the settings model) | No auth/JWT/HMAC/org settings; SQLite-centric. Only the KEV/EPSS/NVD URL+TTL fields carry over. |
| Read/query endpoints (`list_scans`, `list_findings`, `get_scan_risk_summary`, …) | Auth-less, org-less; the [B7](#b7--openapi-contract-) contract already redefines this surface. Risk-summary *aggregation* is worth reading as reference. |
| `smoke_test.py` | Dev scaffolding from the old standalone setup. |

**Caveat (revalidate at build time):** the engine assumes SQLModel record types and a **synchronous**
`Session`. If the rebuilt backend goes async SQLAlchemy or a different ORM, "keep as-is" becomes "keep
the algorithm, re-port the I/O." Confirm the DB-access style is settled before treating these as a
clean lift.

---

## Build sequence

1. **Pi hardware** — acquire + base image per [`PI.md`](PI.md) (parallel with cloud work)  
2. **[`AUTH.md`](AUTH.md) Phase 1** — implement (roadmap ✅)  
3. Foundation — Supabase, Alembic, `org_id` in schema  
4. Railway — API + worker (+ frontend when ready)  
5. Phase 1 auth + Pi HTTP client (ingest + WebSocket)  
6. Command queue + **WebSocket command delivery** + `dmitri agent` daemon on Pi  
7. Frontend MVP — read UI + **"Scan now"** (B10 Control)  
8. NSPi cutover (Epic 7)  
9. AWS staging (parallel)  
10. **[`AUTH.md`](AUTH.md) Phase 2** — product-ready by end of year  
11. Multi-tenant hosted · AWS prod cutover · LLM  
12. **AUTH Phase 3** + B9b — enterprise, deal-driven  

---

## References

| Doc | Use |
|-----|-----|
| [`AUTH.md`](AUTH.md) | Phased authentication — primary auth roadmap |
| [`ADR-005`](../adr/ADR-005-security-model.md) | Proposal only until AUTH phases locked |
| [`docs/epics/EPICS.md`](../epics/EPICS.md) | Cloud epics |
| [`docs/cloud/README.md`](../cloud/README.md) | Ops (in progress) |
