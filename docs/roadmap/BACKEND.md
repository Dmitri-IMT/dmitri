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
| Passwords (policy, 3-month rotation, reset) | ✅ |
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
| `failed` | Error reported by Pi, ingest failure, or timeout |
| `expired` | Stale `running` / undelivered past policy (timeout — implementation detail, ADR-011) |

### Payload (3b)

Backend generates **`command_id`** and **`scan_id`** at enqueue. Pi must use the given `scan_id` in the ingest payload.

| Field | Source |
|-------|--------|
| `command_id` | Backend (UUID) |
| `scan_id` | Backend (UUID) — assigned at enqueue |
| `agent_id` | Backend (target Pi — `agents` table) |
| `scan_mode` | Operator — `quick` \| `standard` \| `extensive` \| `nspi` \| `max` |
| `subnet` | Operator — CIDR |

### Delivery when operator clicks "Scan now" (3c)

- **Pi online** (open WS): deliver immediately → `delivered` → `running`.
- **Pi offline:** backend **retries delivery up to 2 times**; then reject — **`503`** + `code: device_offline` — frontend toast: *"Pi seems to be offline."* No queue-for-later in v1.

### Concurrency (3d)

**One scan at a time** per Pi. If a command is `running` (or `uploading`), reject new trigger — **`409`** + `code: device_busy` — frontend toast or inline error (copy TBD).

### Failure & timeout (3e)

- **No resume** — scans are not resumable.
- **`running` without progress / dead Pi:** mark `failed` after timeout. **How long** is tunable at implementation (ADR-011 / config) — not a product decision here.
- **WS drop mid-scan:** same timeout → `failed`; operator triggers again.

### Idempotency (3f)

Pi treats **`command_id`** as idempotent: duplicate WS delivery → ack, do not re-run scan.

### API surface ✅

**Namespace (5a):** **`/agents/`** = scanner Pis (JWT reads + HMAC WSS). **`/hosts/`** = discovered network machines (JWT). **`/commands/`** = command lifecycle (JWT). OpenAPI today calls hosts **`/devices`** — rename in [B7](#b7--openapi-contract-).

**Transport:** production uses **HTTPS** and **WSS** only (TLS everywhere; local dev HTTP exception per ADR-005).

| Method | Path | Caller | Auth | Purpose |
|--------|------|--------|------|---------|
| **WSS** | `/api/v1/agents/{agent_id}/commands` | Pi daemon | HMAC on upgrade | Persistent connection; receive commands; send status |
| **POST** | `/api/v1/agents/{agent_id}/commands` | Web | JWT | **Scan now** — body: `scan_mode`, `subnet` |
| **GET** | `/api/v1/agents/{agent_id}` | Web | JWT | Agent detail — **`online`** (from WS registry), `last_seen_at`, active command |
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

**`agents`** (5b): `agent_id` (PK string), `org_id`, `display_name`, `secret_hash`, `revoked_at`, `last_seen_at`, `created_at`. **`online`** derived from open WS in API registry (5e) — not a persisted boolean.

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

## B7 — OpenAPI contract ✅

**Decision:** **September slice** — update [`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml) to match B6 + AUTH Phase 1 **before** frontend type-gen. No `/devices` alias (breaking rename to `/hosts`; no consumers today).

Locked with [`ADR-011`](../adr/ADR-011-pi-command-channel.md): stub scan `200` + `status: pending`, typed WS envelope, HMAC upgrade same as ADR-005, auth + invite routes, trigger error `code`s.

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
