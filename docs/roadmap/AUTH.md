# Roadmap — Authentication & authorization

> **Status:** **Phase 1 ✅ decided** (roadmap). Nothing shipped in code yet — implement per sections
> below; then update ADR-005 to match. **Neighbours:** [`BACKEND.md`](BACKEND.md), [`SECURITY.md`](SECURITY.md),
> [`FRONTEND.md`](FRONTEND.md), [`PI.md`](PI.md).

---

## What is decided (organizational)

From [`BACKEND.md`](BACKEND.md) B1:

- **Multi-user, single org** for NSPi pilot
- **`org_id`** on tenant data from first identity migration
- Auth must be **pluggable** toward enterprise IdP later — no hard-coded one-off shortcuts that block SSO

---

## Phased roadmap

| Phase | When | Goal |
|-------|------|------|
| **1 — NSPi / September** | ~September | Login + invite onboarding + coarse roles + HMAC on Pi paths |
| **2 — Product-ready** | End of year | Hardening, rotation, multi-org, audit, prod secrets |
| **3 — Enterprise & beyond** | Deal-driven | Customer cloud, SSO, stricter identity — per [`BACKEND.md`](BACKEND.md) B9b |

---

## Phase 1 — NSPi / September ✅

**Goal:** support the September demo on Supabase + Railway — real users, least privilege, Pi HMAC.

### Decided ✅

| Area | Decision |
|------|----------|
| **Browser** | **Login required.** JWT Bearer on all web API routes per [`BACKEND.md`](BACKEND.md) B6. No shared team account, no URL-only gate. |
| **Signup** | **Invite-only (org invite links).** Bootstrap: create one **admin** per company (`org`). Admin generates **invite links**; invitee opens link and **creates their own account** inside that org. No open/self-serve signup. |
| **Roles** | **`admin`** and **`viewer`** in September. Enforce on API (mutate vs read). Permission matrix for each role — refine with device/agent actions below. |
| **Pi → API** | **HMAC required** for September — `POST /api/v1/scans` and WSS upgrade on `/api/v1/agents/{agent_id}/commands` per B6. |
| **Device secrets** | **B2B installer provisioning** — see below. **Rotation deferred** to Phase 2 (E1). |

**Signup pattern name:** commonly **invite-only registration** or **admin-initiated org invites** (admin issues link → user self-completes account creation scoped to one `org_id`).

### Device secrets — B2B two-audience model ✅

Dmitri is **B2B**: Pi setup is **not** self-service for the company admin. Consumer-style patterns
(QR pairing, `dmitri.local` codes, end-user install scripts) **do not apply** to September.

| Audience | Who | September responsibility |
|----------|-----|---------------------------|
| **Installer** | Technical person on-site (vendor, integrator, or customer IT) | Physically deploy Pi; apply **most secure practical** provisioning (HMAC secret on device, `/etc/dmitri/agent.env`, systemd, network). May use SSH and vendor playbook — acceptable for this role. |
| **Org admin** | Non-technical operator in the web app | **Easy day-to-day use only:** login, invite users, view agents (online/offline), trigger scans, read results. **Does not** provision Pi secrets or run pairing wizards. |

**September provisioning flow:**

1. **Backend** generates `agent_id` + secret; stores `secret_hash` on `agents` row scoped to `org_id`.
2. **Installer** receives plaintext secret **once** via vendor channel (install playbook, secure handoff — not exposed in routine admin UI).
3. **Installer** writes Pi config (`DEVICE_ID`, `DEVICE_SECRET`, `BACKEND_URL`), enables `dmitri-agent.service`, verifies WSS + ingest.
4. **Org admin** sees agent online in admin UI; uses product without touching device credentials.

**Binding (C1):** Pi authenticates with `agent_id` + HMAC only. `org_id` is set on the `agents` row at provisioning time; backend resolves tenant from DB lookup — Pi does not carry `org_id`.

**Agent admin (D1):** both roles may view agent state; only org **`admin`** may trigger scans.
Creating/revoking agent rows and secret handoff to installer is **vendor/installer ops** in
September (not a self-serve admin UI flow). The viewer UI omits the trigger rather than disabling it.

**Rotation (E1):** no rotate/revoke UX in September; `revoked_at` column may exist. Rotation + revoke + re-pair → Phase 2.

**Phase 2+:** optional self-service pairing if customers deploy Pis without vendor on-site; installer playbook remains the secure default.

**Role matrix ✅**

| Role | Read (scans, hosts, agents) | Trigger scan | Invite users | Pi provisioning |
|------|------------------------------|--------------|--------------|-----------------|
| `viewer` | Yes | No | No | No |
| `admin` | Yes | Yes | Yes | No (installer/vendor) |

### Passwords ✅

| Area | Decision |
|------|----------|
| **Invite completion** | **Email + password (A1).** Invitee opens one-time invite link and **chooses their password** to activate the account. No shared/temporary passwords. |
| **First org admin** | **Same invite flow (E2).** Vendor creates org and sends the first **admin** an invite link — not a separately seeded password. |
| **Invite link TTL** | **Short (D1).** Links expire after a brief window (target **24–72 h** at implementation). **Single-use** — consumed on successful signup. |
| **Password policy** | **Strong**, enforced at invite completion, login password change, and reset: minimum length; reject common/breached passwords; reject obvious patterns — repeated characters (e.g. `111`), keyboard/simple suffixes (e.g. `1!`), **repeated number sequences**, **birth dates**, **names** (user name, org name — implementation defines matching). |
| **Password rotation** | **Every 3 months.** User must set a new password when expired; block normal API use until changed (login may succeed only to reach change-password flow). |
| **Forgot password** | **Self-serve email reset (C2).** “Forgot password?” → email with one-time reset link → set new password (same policy + rotation clock). |
| **Transactional email** ✅ | **In scope — the backend sends invite links and reset links.** Decided 2026-07-13; **provider TBD** (Resend / Postmark / SES). Previously *nothing in the roadmap sent mail*, which left self-serve reset unbuildable — an admin can hand-carry an invite link, but a locked-out user has nobody in the loop. Code is small (`httpx` already a dependency); **the real work is a sending domain with SPF + DKIM + DMARC** — a one-time login link from a security product looks exactly like phishing and gets filtered without them. **Invites also keep a copyable link in the admin UI** as a fallback ([`ui/SCREENS.md` → Users & invites](../ui/SCREENS.md#users--invites)). |

**Frontend surfaces:** invite acceptance page, login, forgot password, reset password, **forced change-password** when rotation due. Client mechanics (token storage, silent-refresh interceptor, route guards): [`ADR-008`](../adr/ADR-008-frontend-stack.md).

### Sessions ✅

Per ADR-005 pattern (Bearer on business APIs; refresh on `/auth/*` only).

| Area | Decision |
|------|----------|
| **Access token** | Short-lived JWT (**~15 min**, A1). `Authorization: Bearer` on all business endpoints. Stored in **SPA memory only** (E1) — full page reload triggers silent refresh. |
| **Refresh** | **httpOnly cookie** on `/auth/*` (B1). `POST /auth/refresh` with `credentials: include`; not used on scan/command routes. |
| **Refresh lifetime** | **Fixed 7 days from login** (C2) — no sliding extension. After 7 days user must **log in with password** again (helps password recall; intentional tradeoff). |
| **Refresh rotation** | **Rotate on each refresh** (D1); detect reuse / invalidate token family. |
| **Logout** | **Server revoke** (F2) — `POST /auth/logout` invalidates refresh server-side and clears cookie; not client-only. |
| **Extra session cap** | **None** (H deferred) — 7-day refresh + 3-month password rotation is sufficient for September. |
| **Auth endpoints** | `POST /auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/change-password` (G). |

**Password rotation interaction:** if password expired, login/refresh may only allow change-password until updated.

**SPA:** Axios Bearer on API client; `withCredentials` on `/auth/*` only. On **401**, try refresh once then redirect to login.

**Depends on:** [`BACKEND.md`](BACKEND.md) B10 Control ✅ — HMAC on **ingest** + **WebSocket handshake** (confirmed).

---

## Phase 2 — Product-ready (end of year) 🔓

**Goal:** auth fit for **hosted SaaS** customers (not enterprise BYOC yet).

**Builds on Phase 1** (invite model and coarse roles already in September):

| Area | Product-ready likely adds |
|------|---------------------------|
| **Users** | Second org on same stack; `org_id` isolation tested |
| **Sessions** | Logout everywhere (all devices), optional idle timeout |
| **Authorization** | Finer permissions matrix; document role semantics |
| **Agent** | Secret **rotation + revoke** story; optional self-service pairing if no on-site installer |
| **Ops** | JWT signing key + device secrets in managed secrets (not plain Railway env for prod) |
| **Audit** | Who logged in, who triggered scans (minimum trail) |

**Open questions for Phase 2 planning:**

- MFA — in or out for year-end?
- API keys for automation (out of scope until requested?)
- Self-serve org creation vs sales-led only

---

## Phase 3 — Enterprise & beyond 🔓

**Trigger:** signed deal(s) requiring customer-controlled identity and data ([`BACKEND.md`](BACKEND.md) B9b).

| Area | Enterprise |
|------|------------|
| **Identity** | OIDC / SAML (Entra ID, Okta, Google Workspace, etc.) |
| **Deploy** | `AUTH_MODE=oidc`; customer IdP; optional no local password store |
| **Data** | Customer `DATABASE_URL`; same app binary |
| **Hardening** | Stricter session policy, audit export, possibly mTLS — **per deal** |

SSO and BYOC packaging are **one epic**, not background work.

---

## Two audiences

| Caller | Mechanism | Phase 1 |
|--------|-----------|---------|
| **Pi agent** | HMAC-SHA256 per device ([`ADR-005`](../adr/ADR-005-security-model.md)) | ✅ Required |
| **Web browser** | JWT Bearer + httpOnly refresh on `/auth/*` ([`ADR-005`](../adr/ADR-005-security-model.md)) | ✅ |

**Next:** implement Phase 1 in code; reconcile and update ADR-005 when shipped.

---

## Built today

| Control | State |
|---------|--------|
| Everything | **Not built** — ingestion and reads are open in code |

---

## Sequencing

1. **Implement** Phase 1 (identity tables, invite flow, sessions, roles middleware, HMAC verify)  
2. Plan Phase 2 before December (multi-org, device secret rotation, audit, prod secrets)  
3. Phase 3 when a deal names requirements  

---

## Ripple

Phase changes affect [`FRONTEND.md`](FRONTEND.md) (login + invite UX), [`PI.md`](PI.md) (device secrets, HMAC client), [`SECURITY.md`](SECURITY.md), [`BACKEND.md`](BACKEND.md) (tables, middleware, `requested_by` on commands).
