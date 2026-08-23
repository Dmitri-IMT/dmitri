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
| B2 | Agent auth | ✅ | Ed25519 device signature September (ADR-005 amended 2026-07-24) — [`AUTH.md`](AUTH.md) Phase 1 |
| B3 | Frontend auth | ✅ | [`AUTH.md`](AUTH.md) Phase 1 |
| B4 | Database hosting | ✅ | Supabase → AWS RDS; [B4/B5](#b4--b5--hosted-stack-) |
| B5 | App hosting | ✅ | Railway → AWS; single `nspi` env for September |
| B6 | Pi command channel | ✅ | [B6](#b6--pi-command-channel-) — [`ADR-011`](../adr/ADR-011-pi-command-channel.md) |
| B7 | OpenAPI vs reality | ✅ | September slice — [`ADR-011`](../adr/ADR-011-pi-command-channel.md), `contracts/openapi/` |
| B8 | Reuse `backend/` code | ✅ | Keep the enrichment/scoring engine; discard the app shell — [Reuse](#reuse-from-backend-code-) |
| B9 | Hosted vs enterprise | ✅ | Hosted v1; enterprise deal-driven — [B9](#b9--hosted-vs-enterprise-) |
| B10 | September MVP scope | ✅ | **Scenario B — Control** — [B10](#b10--september-mvp-) |
| B11 | Frontend contract asks | 🔓 | **1 of 18 still open** (C3 partial); C10 closed by DMI-75/spec 032 — [B11](#b11--frontend-contract-asks-) |
| B12 | Transactional email | 🔓 | Built in DMI-71 on **Resend** (invites + password reset); **sending domain still TBD** — [B11-C17](#b11--frontend-contract-asks-) |

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
| Pi Ed25519 signatures; passwords; sessions (7-day fixed refresh) | Device key rotation (Phase 2) |
| Device keys: B2B installer provisioning (register device public key) | Self-service Pi pairing (if needed later) |
| Design toward many orgs + enterprise later | — |

---

## B2 + B3 — Authentication ✅

**Decided** — **[`AUTH.md`](AUTH.md) Phase 1.** Implement in code; update ADR-005 when shipped.

| Area | Status |
|------|--------|
| Pi Ed25519 signature (ingest + WSS) | ✅ |
| Login, invites, roles | ✅ |
| Passwords (policy, breach screening, reset — no forced rotation, [`ADR-016`](../adr/ADR-016-password-policy.md)) | ✅ |
| Sessions (15 min access, 7-day refresh, server logout) | ✅ |
| Device keys (installer provisioning) | ✅ provision model (register public key); Pi key rotation Phase 2 |

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
| `expired` | Command **never reached the Pi**: no open socket, or the one send attempt threw (set at the same moment the trigger returns `503 device_offline`) — or the stale sweep found it still `queued` |

**The dividing line is `delivered_at` (C12, decided 2026-07-13).** Not the timeout duration — *whether the
Pi ever took the job*. Never delivered → `expired`; delivered then broke → `failed`. This is why
`expired` needs **no timeout sweeper**: it is set synchronously at enqueue when delivery fails.

### Payload (3b)

Backend generates **`command_id`** at enqueue. **`scan_id`** is minted for the WS delivery
payload and **persisted** (with the stub `scans` row) only on successful delivery — an
`expired` command has `scan_id: null` (ADR-011 §4 / D1). Pi must use the given `scan_id` in
the ingest payload.

| Field | Source |
|-------|--------|
| `command_id` | Backend (UUID) — assigned at enqueue |
| `scan_id` | Backend (UUID) — generated for delivery; persisted only on successful delivery |
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
- **Pi offline:** **one delivery attempt, no retries** — reject immediately — **`503`** + `code: device_offline` — frontend toast: *"Pi seems to be offline."* No queue-for-later in v1. **Retrying is the operator clicking "Scan now" again.**

> **Amended 2026-08-13 — the "2 delivery retries" are withdrawn.** They were never built, and they
> cannot work as written: `deliver()` holds **one** socket object, and `send_text` throws only when
> that connection is already closed, so a second and third call are guaranteed to fail too. For a
> retry to find a live socket the Pi must *reconnect* — seconds, not microseconds — which means
> sleeping inside the operator's request. That is queue-for-later, which [`ADR-011`](../adr/ADR-011-pi-command-channel.md)
> rejects for v1. Retries also miss the failure that actually bites: a half-open socket where the
> send *succeeds* into a black hole. Nothing is retried there — the presence projection and the
> stale sweep catch it and mark the command `failed` / `agent_disconnected`. One try, fail fast,
> click again.

### Concurrency (3d)

**One scan at a time** per Pi. If a command is `running` (or `uploading`), reject new trigger — **`409`** + `code: device_busy` — frontend toast or inline error (copy TBD).

### Failure & timeout (3e)

- **No resume** — scans are not resumable.
- **`running` without progress / dead Pi:** mark **`failed`** after timeout — the Pi *took* the command, so this is a broken scan, not an undelivered one. **How long** is tunable at implementation (ADR-011 / config) — not a product decision here.
- **WS drop mid-scan:** same timeout → `failed`; operator triggers again.
- **Undelivered on the single attempt:** **`expired`**, set synchronously with the `503 device_offline` — never reached the Pi. There is no timeout for it: the verdict is immediate. The stale sweep reaches the same verdict for a command left `queued` (the enqueue succeeded but delivery never ran), so `expired` has two writers, both meaning *the Pi never took the job* and both recording `device_offline`.

### Idempotency (3f)

Pi treats **`command_id`** as idempotent: duplicate WS delivery → ack, do not re-run scan.

### API surface ✅

**Namespace (5a):** **`/agents/`** = scanner Pis (JWT reads + Ed25519-signed WSS). **`/hosts/`** = discovered network machines (JWT). **`/commands/`** = command lifecycle (JWT). The **`/devices`** → **`/hosts`** rename shipped with [B7](#b7--openapi-contract-); the contract has no `/devices` path.

**Transport:** production uses **HTTPS** and **WSS** only (TLS everywhere; local dev HTTP exception per ADR-005).

| Method | Path | Caller | Auth | Purpose |
|--------|------|--------|------|---------|
| **WSS** | `/api/v1/agents/{agent_id}/commands` | Pi daemon | Ed25519 signature on upgrade | Persistent connection; receive commands; send status |
| **POST** | `/api/v1/agents/{agent_id}/commands` | Web | JWT | **Scan now** — body: `scan_mode`, `subnet` (frontend sends `quick` + the agent's `target_subnet`) |
| **GET** | `/api/v1/agents` | Web | JWT | **List agents** — array of one in the MVP. ✅ shipped DMI-78 as `listAgents`; org-scoped, viewers included ([B11-C1](#b11--frontend-contract-asks-)) |
| **GET** | `/api/v1/agents/{agent_id}` | Web | JWT | Agent detail — **`online`** (from WS registry), `last_seen_at`, `active_command_id`, `available_subnets`, `target_subnet`. ✅ implemented DMI-78 ([B11-C2](#b11--frontend-contract-asks-)) |
| **PATCH** | `/api/v1/agents/{agent_id}` | Web | JWT (admin) | **Choose the network to scan** — body `target_subnet`; refuses a CIDR the Pi is not reporting (`422 subnet_not_reported`) or a Pi reporting none (`409 device_offline`). ✅ shipped DMI-78 |
| **GET** | `/api/v1/commands/{command_id}` | Web | JWT | Command lifecycle |
| **GET** | `/api/v1/hosts/…` | Web | JWT | Host inventory *(renamed from `/devices` in B7; `GET /hosts` honours `page`/`per_page`)* |
| **POST** | `/api/v1/scans` | Pi | Ed25519 signature | Upload scan results *(exists in OpenAPI)* |
| **GET** | `/api/v1/scans/{scan_id}` | Web | JWT | Scan results when ready *(exists)* |

**Trigger errors** (distinct HTTP status + `code` for logs/metrics):

| Condition | HTTP | `code` | UI |
|-----------|------|--------|-----|
| Pi not reachable on the one delivery attempt | **503** | `device_offline` | Toast: *Pi seems to be offline.* |
| Scan already `running` / `uploading` | **409** | `device_busy` | Toast: scan in progress (copy TBD) |

**WebSocket messages (4e):** backend → Pi `command` payload; Pi → backend `status` updates. Large result payload stays on **`POST /scans`**, not WS.

### Data model ✅

**Two concepts (5a):** **`agents`** = Pis running `dmitri agent` (`agent_id` = the signed `X-Device-Id`). **`hosts`** = machines discovered by scans (the `hosts` table / `HostSummary`, renamed from `devices` / `DeviceSummary` in B7).

```
org
 └── agents          ← Pi appliances, secrets, online/last_seen
      └── commands   ← "Scan now"
           └── scans  ← stub on successful delivery (5c); filled on ingest
                └── hosts  ← discovered machines (ports, findings, …)
```

**`agents`** (5b): `agent_id` (PK, **UUID** — decided 2026-07-13; it must equal `X-Device-Id`, and every other id in the system is a UUID. Backend mints it at provisioning; `display_name` is what humans read), `org_id`, `display_name`, `public_key` (32-byte Ed25519 public key, plaintext — ADR-005 amended 2026-07-24; **not** a stored secret, ADR-015 retired), `revoked_at`, `last_seen_at`, `created_at`, **`target_subnet`** (✅ shipped DMI-78, migration `20260811_17` — the network the operator chose to scan; nullable until chosen, unindexed). **`online`** derived from open WS in API registry (5e) — not a persisted boolean. **`available_subnets`** is *reported*, not stored: the Pi sends its interfaces over the WS channel and the API reads them from its in-process registry per request.

**`commands`** (5c): `command_id`, `org_id`, `agent_id` (FK), `scan_id` (FK), `scan_mode`, `subnet`, `status`, `requested_by` (audit, optional Phase 1 — **must be nullable / `ON DELETE SET NULL`**: members can now be hard-deleted, [`ADR-017`](../adr/ADR-017-account-removal.md), and a removed requester renders as "deleted user"), `error_code`, timestamps (`created_at`, `delivered_at`, `started_at`, `completed_at`).

**Enqueue (5c-A):** `POST …/agents/{id}/commands` inserts a **`commands`** row (`queued`,
`scan_id` null). The stub **`scans`** row is created only after WS delivery succeeds (same
`scan_id` persisted on the command).

**`org_id` (5d):** on `agents`, `commands`, `scans`; hosts scoped via `scan.org_id`.

**ADR-011 ✅:** [`ADR-011`](../adr/ADR-011-pi-command-channel.md) — WS typed envelope, Ed25519-signed upgrade, stub scan `pending`, `/hosts` rename, timeouts config-only, single API replica NSPi.

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

- [ ] **Pi hardware acquired and base-configured** — see [`PI.md`](PI.md) (blocker: no Pi in possession today; procurement is DMI-55, cycle 6)
- [x] Supabase + Railway `nspi` live — DMI-52 (2026-07-28); frontend static deploy still open (DMI-91)
- [x] Alembic + identity schema per [`AUTH.md`](AUTH.md) Phase 1 — DMI-60, DMI-61, DMI-77
- [ ] Pi daemon + Pi → backend ingest (Ed25519 signature per AUTH Phase 1) — DMI-66, DMI-65, DMI-63
- [ ] Command queue + "Scan now" E2E (web → backend → Pi → results → web) — enqueue/delivery landed (DMI-64); E2E is DMI-67

---

## B11 — Frontend contract asks 🔓

**Raised 2026-07-13 (DMI-54)** by breadboarding the UI against
[`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml). Each gap blocks a flow in
[`ui/FLOWS.md`](../ui/FLOWS.md#contract-asks); none are frontend-solvable. The UI is designed and
waiting.

**The identity administration contract is now complete.** Spec 030 / DMI-76 publishes and
implements separate admin-only, org-scoped resources for members and pending invites:
`GET /users`, `PATCH /users/{user_id}`, `GET /invites`, and
`DELETE /invites/{invite_id}`. Spec 029 / DMI-102 already supplied both account-removal routes.
The Users & Invites frontend screen consumed these in spec 034 / DMI-90 (2026-08-21); C4 is closed end to end.

**The role half of this is now closed.** `GET /users/me` returns the user object, so the frontend
has a documented way to learn the logged-in user's role and does not have to read a JWT claim the
contract never specified — spec 020's session layer does exactly that, and nothing in the SPA
decodes a token. What that unblocks is the `admin`/`viewer` split for `[Scan now]`, the `Users` nav
item and the invite form, once those screens exist.

| # | Ask | Blocks | Notes |
|---|-----|--------|-------|
| ~~**C1**~~ | ~~`GET /api/v1/agents` — list agents~~ | — | **✅ RESOLVED 2026-08-12 (DMI-78/spec 031).** Published and implemented as `listAgents`: an org-scoped array (one row in the MVP) any authenticated caller may read, so the frontend can discover `agent_id` instead of needing the provisioning `X-Device-Id`. `frontend/src/api/agents.ts` — shipped by spec 020 called by nothing — now has a route to call; wiring it, and HOME's Pi-status footer line, is DMI-89. |
| ~~**C2**~~ | ~~`AgentDetail.available_subnets` + `target_subnet`, and a way to set it~~ | — | **✅ RESOLVED 2026-08-12 (DMI-78/spec 031).** The WS half was locked 2026-07-13 (the Pi's `hello` frame carries `available_subnets`, per [`ADR-011` §3](../adr/ADR-011-pi-command-channel.md)). The HTTP half now exists: `AgentDetail` carries both fields, and `PATCH /api/v1/agents/{agent_id}` is the admin's one-time choice — refusing a CIDR the Pi is not reporting (`422`) and a Pi reporting none (`409`). `agents.target_subnet` is the only new column; `available_subnets` and `online` stay unstored. `POST /commands` is unchanged except that it now refuses a `subnet` the Pi is not reporting. |
| **C3** ◐ | ~~`GET /users/me`~~ (+ update) | SETTINGS → profile | **Read half ✅ shipped** (DMI-72 / spec 019): `GET /api/v1/users/me` is in the contract and implemented; spec 020's session layer reads identity **and role** from it, and nothing decodes a JWT. **Still open:** the update half (profile edit) for SETTINGS. |
| ~~**C4**~~ | ~~Users & invites: list users, list pending invites, change role, revoke invite, remove a member, member activity~~ | — | **✅ RESOLVED 2026-08-11 (DMI-76/spec 030, plus DMI-102/spec 029 removal).** Published and implemented as separate admin resources: `GET /users` returns `OrgMember` rows with `last_seen_at`; `PATCH /users/{user_id}` changes role while refusing self-target and final-admin demotion; `GET /invites` lists live pending rows without tokens; `DELETE /invites/{invite_id}` revokes pending invites. `DELETE /users/me` and `DELETE /users/{user_id}` remove accounts. All are org-scoped; foreign ids are 404. |
| ~~**C5**~~ | ~~Forced password change: 403 on expired-password login carries no token, but `POST /auth/change-password` requires Bearer~~ | — | **✅ MOOT 2026-07-23 — [`ADR-016`](../adr/ADR-016-password-policy.md) drops forced password rotation.** With no password expiry, this deadlock cannot occur: login is `200`/`401` only. No change needed. |
| ~~**C6**~~ | ~~`HostSummary.first_seen_at`~~ | — | **✅ RESOLVED** — `first_seen_at` is now a required property on `HostSummary` in the contract. The HOME "new device" item is unblocked (it is still not built; HOME ships critical/high findings, failed scans and stale coverage only). |
| ~~**C7**~~ | ~~Does accept-invite issue a session?~~ | — | **✅ RESOLVED 2026-07-13 — yes.** It returns `201` with a full `LoginResponse`, so ACCEPT INVITE auto-logs-in to HOME. (Expiry is **`410`**, not `400`.) `ui/FLOWS.md` B2 assumed the opposite and was corrected. No change needed. |
| ~~**C8**~~ | ~~`FindingRecord.cve_id`~~ | — | **✅ RESOLVED 2026-07-13** — `cve_id`, `cvss_score` and `references` all exist. No change needed. |
| ~~**C9**~~ | ~~`host_id` on `DevicePayload`~~ | — | **✅ RESOLVED 2026-08-02 (DMI-85)** — the array on `ScanDetailResponse` is `hosts: ScanHostView[]`, and `host_id` is a required property on it, so a host row on a scan links to that host's page. `FindingRead.host_id` carries the same identifier for findings. |
| ~~**C10**~~ | ~~A failed scan carries **no reason**~~ | — | **✅ RESOLVED 2026-08-13 (DMI-75/spec 032).** `ScanDetailResponse` carries optional `error_code` (`ScanErrorCode \| null`) from a read-time join to the command row — one request, no second round trip. A failed scan with no command, a NULL stored code, or an off-contract string reads `"unknown"`. A non-failed scan is always `null`. The eight published codes are in the contract; the operator sentence is client copy at `frontend/src/lib/scanFailureReasons.ts`. The Scan Detail screen that renders it is DMI-88. |
| ~~**C11**~~ | ~~Does `GET /findings?device_id=…` accept a `host_id`?~~ | — | **✅ RESOLVED 2026-07-13 — the filter becomes `?host_id=`.** The question only existed because the [B7](#b7--openapi-contract-) rename stopped at the paths; finishing it into the read-model field names dissolves it. Same identifier, one name. HOST DETAIL can show findings. |
| ~~**C12**~~ | ~~Dead Pi → `failed` or `expired`?~~ | — | **✅ RESOLVED 2026-07-13 — split on `delivered_at`.** Never delivered → **`expired`** (set with the `503`, no sweeper). Delivered then broke — Pi error, ingest failure, WS drop, stale `running` — → **`failed`**. Both statements in B6 were half-right; the [lifecycle table](#lifecycle-3a--full) and [Failure & timeout](#failure--timeout-3e) now say the same thing. **Not a contract gap** — `CommandStatus` already carries all seven states. |
| ~~**C13**~~ | ~~Bad `current_password` → **400, not 401**~~ | — | **✅ RESOLVED — `400`, and the `401` now means only what it says.** Spec 019 (DMI-72) pinned `wrong_current_password` / `password_policy_violation` at `400` via `PasswordChangeRejected`. DMI-77 closed the remainder: the route's `401` was retitled to pin it to a missing/malformed/expired `Authorization` header. Deleting the `401` would have made the contract lie — the route is bearer-authed, so `401` is genuinely reachable; RFC 9110 §11.6.2 just confirms a body field is not a credential. |
| ~~**C14**~~ | ~~`POST /api/v1/invites/lookup` — read an invite before accepting~~ | ACCEPT INVITE | ~~The screen knows **nothing**: not the org, not the role, not the invited email — so it cannot tell a stranger the link is legitimate, and the invitee must **type their own email from memory**.~~ **✅ RESOLVED 2026-08-06 (DMI-86, spec 027).** Public route (`security: []`), token in the **body**, returns `{ email, role, org_name }`; expired, accepted and unknown tokens are indistinguishable — all `410 invalid_invite_token`, reusing the accept route's own response component so the two cannot drift. Reading does **not** consume the invite. **A body `POST`, not the `GET` this ask originally named**: DMI-77 moved this token out of the accept path because uvicorn's default access logger writes the request target; a query string fixes the *path* but not the log, so the `GET` would reintroduce exactly what DMI-77 removed, and cacheability is worthless for a single-use credential (`specs/027-invite-lookup/decisions/DR-0001-invite-lookup-transport.md`). **Its consequence shipped with it:** acceptance now takes `{token, password}` only (DR-0002). **The endpoint is unconsumed** — the ACCEPT INVITE screen that greets the invitee is DMI-87. |
| ~~**C15**~~ | ~~Distinct `error.code`s on `POST /auth/reset-password`'s `400`~~ | — | **✅ RESOLVED 2026-08-03 (DMI-77) — split by status, not just code.** A dead/used link is **`410 invalid_reset_token`**; a weak password is **`400 password_policy_violation`**. Pinning a code alone would have papered over the shared status; splitting it resolves the complaint and makes RESET PASSWORD and ACCEPT INVITE one pattern (RFC 9110 does not settle `400` vs `410` here — parity decided it). The "same treatment for ACCEPT INVITE" note was taken up: its `400` causes were pinned as `invite_email_mismatch` / `email_already_registered` / `password_policy_violation`, and its `410` is `invalid_invite_token`. **Superseded in part by spec 027 (2026-08-06):** the invite lookup landed and acceptance no longer takes an address, so `invite_email_mismatch` is **removed** — only `email_already_registered` and `password_policy_violation` remain on the `400`. All enums are pinned in the contract and gated by `test_contract_fidelity.py`. |
| ~~**C16**~~ | ~~**The user's role is nowhere in the contract**~~ | — | **✅ RESOLVED — the cheapest option was taken:** the role is returned by **C3**'s `GET /users/me`, not read from an undocumented JWT claim. Spec 020's session layer is the only reader, and nothing in the SPA decodes a token — a token payload claiming a different role does not change what renders. ⚠️ **REVALIDATE:** [`ADR-008`](../adr/ADR-008-frontend-stack.md) §Papéis still says the role rides in JWT claims and now contradicts the shipped code; it needs an amendment. |
| ~~**C17**~~ | ~~No email delivery exists anywhere~~ | — | **✅ DECIDED 2026-07-13 — transactional email is in scope. Provider TBD.** The backend sends **invite links** and **password-reset links**. <br>**Cost is small:** `httpx` is already a backend dependency, so no new library — a `services/mailer.py` plus two call sites (`POST /invites`, `POST /auth/forgot-password`), both already the points where a token is minted, and two templates. <br>**The real work is deliverability, not code:** a sending domain with **SPF + DKIM + DMARC**. A security product's one-time login link is structurally indistinguishable from phishing and will be filtered without them. <br>**Reset is what made this mandatory** — an admin can hand-carry an invite link, but a locked-out user has nobody in the loop. <br>**Invites keep the copyable link in the UI anyway** (email is the convenience, the link is the guarantee). <br>**Provider picked 2026-08-02 — Resend**, on price at low volume, a one-call plain-text API and domain-verification-only onboarding (no SES-style sandbox review): see [the research](../research/transactional-email-provider-and-sending-domain.md). Shipped in DMI-71 exactly as costed above — `services/mailer.py` + the same two call sites. <br>**Deliverability closed 2026-08-22 — `mail.peirce.dev` is verified:** SPF, DKIM and DMARC all pass and `peirce.dev` sits at `p=reject`; Resend reports `last_event: delivered`. <br>**DMI-108 (2026-08-23) then fixed placement, not delivery.** Delivered mail was still filed as spam, on two structural causes: the templates were text-only, and links pointed at `nspi.up.railway.app` while mail came from `mail.peirce.dev`. Both are gone — mail is now `multipart/alternative` (bare semantic HTML beside the unchanged text part) and both services moved onto `peirce.dev` (`dmitri.peirce.dev` + `api.peirce.dev`). That domain move also returned the refresh cookie to `SameSite=Lax`, closing the [ADR-005](../adr/ADR-005-security-model.md) deviation. <br>**What remains is reputation, not engineering:** inbox placement is earned by volume of mail people open, and the domain has sent single-digit messages. No PR closes that. The copyable link stays the guarantee meanwhile. |
| ~~**C18**~~ | ~~`POST /invites` documents **only a `201`**~~ | — | **✅ RESOLVED 2026-08-03 (DMI-77).** Already-a-member is **`400 email_already_member`**; already-has-a-live-invite is **`409 invite_already_pending`** (RFC 9110's Conflict, including its "resolve and resubmit" clause; matches the existing `DeviceBusyError` 409). The member check runs first, so an address that is both yields `email_already_member` — the two lead to different admin actions ("nothing to do" vs "wait or reissue"). **The premise was partly stale:** the already-a-member case existed and was tested; what was genuinely missing is that `create_invite` never looked for a live invite, so re-inviting silently minted a *second valid token*. It now takes a `pg_advisory_xact_lock` before the checks, because `Invite.role` is per-row and two racing invites with different roles would let the invitee pick their own privilege. A different org's address is still unreported and returns `201`, per the anti-probing design. |

**Not asked for, deliberately:** a `GET /findings/{id}`. `GET /findings?scan_id=…` already returns
the full `FindingRecord` (description, recommendation, evidence), so finding detail renders from data
the screen already holds — [`REFERENCE.md` §12](../ui/REFERENCE.md), don't solve a problem you don't
have.

---

## B7 — OpenAPI contract ✅

**Decision:** **September slice** — update [`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml) to match B6 + AUTH Phase 1 **before** frontend type-gen. No `/devices` alias (breaking rename to `/hosts`; no consumers today).

Locked with [`ADR-011`](../adr/ADR-011-pi-command-channel.md): stub scan `200` + `status: pending`, typed WS envelope, Ed25519-signed upgrade same as ADR-005, auth + invite routes, trigger error `code`s.

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
