# Roadmap — Authentication & authorization

> **Status:** **Phase 1 ✅ decided** and its software controls are implemented: identity schema,
> sessions/passwords, browser and device auth gates, invite onboarding, account removal, the
> command/ingest transports, and — since spec 030 / DMI-76 — member/pending-invite administration
> plus user activity stamping. Remaining gaps are operational (physical Pi provisioning, service
> packaging, keys/clock) and the later product surfaces described below, not missing auth routes.
> **Neighbours:** [`BACKEND.md`](BACKEND.md), [`SECURITY.md`](SECURITY.md),
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
| **1 — NSPi / September** | ~September | Login + invite onboarding + coarse roles + Ed25519 device signatures on Pi paths |
| **2 — Product-ready** | End of year | Hardening, rotation, multi-org, audit, prod secrets |
| **3 — Enterprise & beyond** | Deal-driven | Customer cloud, SSO, stricter identity — per [`BACKEND.md`](BACKEND.md) B9b |

---

## Phase 1 — NSPi / September ✅

**Goal:** support the September demo on Supabase + Railway — real users, least privilege, Pi Ed25519 signatures.

### Decided ✅

| Area | Decision |
|------|----------|
| **Browser** | **Login required.** JWT Bearer on all web API routes per [`BACKEND.md`](BACKEND.md) B6. No shared team account, no URL-only gate. |
| **Signup** | **Invite-only (org invite links).** Bootstrap: create one **admin** per company (`org`). Admin generates **invite links**; invitee opens link and **creates their own account** inside that org. No open/self-serve signup. |
| **Roles** | **`admin`** and **`viewer`** in September. Enforce on API (mutate vs read). Permission matrix for each role — refine with device/agent actions below. |
| **Pi → API** | **Ed25519 device signature required** for September (ADR-005, amended 2026-07-24) — `POST /api/v1/scans` and WSS upgrade on `/api/v1/agents/{agent_id}/commands` per B6. |
| **Device keys** | **B2B installer provisioning** — device keypair generated on the Pi, public key registered with the backend; see below. **Rotation deferred** to Phase 2 (E1). |

**Signup pattern name:** commonly **invite-only registration** or **admin-initiated org invites** (admin issues link → user self-completes account creation scoped to one `org_id`).

### Device secrets — B2B two-audience model ✅

Dmitri is **B2B**: Pi setup is **not** self-service for the company admin. Consumer-style patterns
(QR pairing, `dmitri.local` codes, end-user install scripts) **do not apply** to September.

| Audience | Who | September responsibility |
|----------|-----|---------------------------|
| **Installer** | Technical person on-site (vendor, integrator, or customer IT) | Physically deploy Pi; generate the device **keypair on the Pi**, register its **public key** with the backend (`/etc/dmitri/agent.env`, systemd, network). May use SSH and vendor playbook — acceptable for this role. |
| **Org admin** | Non-technical operator in the web app | **Easy day-to-day use only:** login, invite users, view agents (online/offline), trigger scans, read results. No Pi setup in the web app. The admin's **credentials** authorize registration when the installer runs `provision-pi.sh` (DMI-147). |

> **Auth model updated 2026-07-24 (ADR-005 amended):** the Pi authenticates with **Ed25519
> asymmetric signing**, not a symmetric HMAC secret. The device holds a **private key**; the
> backend stores only the device's **public key**. There is no shared secret and nothing to
> encrypt at rest — [`ADR-015`](../adr/ADR-015-agent-secret-storage-at-rest.md) is retired. This
> shrinks the provisioning blast radius: no secret is ever transmitted (see flow below).

**September provisioning flow:**

1. **Installer** generates an Ed25519 **keypair on the Pi**; the private key never leaves the device.
2. **Installer** registers the device's **public key** with the backend, creating the `agents` row scoped to `org_id`. Since 2026-09-24 (DMI-147), `hardware-agent/scripts/provision-pi.sh` does this over HTTPS: it logs in with an org **admin** account and calls `POST /api/v1/agents`, so the Pi joins that admin's org. The vendor CLI `backend-provision-agent` stays for cases with no admin login; both call the same `register_agent()`. The public key is **not a secret** — the channel needs integrity (bind the right public key to the right `agent_id`/`org_id`), not confidentiality.
3. **Installer** writes Pi config (`DEVICE_ID`, `DEVICE_PRIVATE_KEY`, `BACKEND_URL`), enables `dmitri-agent.service`, verifies WSS + ingest.
4. **Org admin** sees agent online in admin UI; uses product without touching device credentials.

**Binding (C1):** Pi authenticates with `agent_id` + **Ed25519 signature** only. `org_id` is set on the `agents` row at provisioning time; backend resolves tenant from DB lookup — Pi does not carry `org_id`.

**Agent admin (D1):** both roles may view agent state; only org **`admin`** may trigger scans or
revoke/restore a device. Only an org **`admin`** token can register a public key
(`POST /api/v1/agents`). The installer runs that from the Pi; there is no web UI for it. The viewer UI omits these
actions rather than disabling them.

**Rotation (E1):** revoke/restore UX ships with **DMI-155** (spec 048): admin-only
`POST /api/v1/agents/{id}/revoke` and `/restore`, with Revoked shown on the device list and detail.
A restored Pi reconnects on its next hourly attempt (ADR-011 amendment 2026-09-16). Rotation still
has no UX: rotation = a new keypair on the Pi + replace the stored public key (no confidential secret to invalidate). Rotation + re-pair UX → Phase 2.

**Phase 2+:** optional self-service pairing if customers deploy Pis without vendor on-site; installer playbook remains the secure default.

**Role matrix ✅**

| Role | Read (scans, hosts, agents) | Trigger scan | Invite users | Remove a member | Pi provisioning |
|------|------------------------------|--------------|--------------|-----------------|-----------------|
| `viewer` | Yes | No | No | Own account only | No |
| `admin` | Yes | Yes | Yes | Yes, and own account | Register a Pi via `provision-pi.sh` (no web UI) |

Roles stay **`admin`** and **`viewer`**. "Viewer" is deliberately not renamed to "user": every
member is a user, so the word cannot distinguish a role, and the screen that lists them is itself
called *Users*.

### Account removal ✅

Decided 2026-08-08 — [`ADR-017`](../adr/ADR-017-account-removal.md), which supersedes the previous
"no user deletion/deactivation" position. Summary; the ADR holds the reasoning:

| Area | Decision |
|------|----------|
| **Kind** | **Hard delete**, cascading `refresh_tokens` and `password_reset_tokens`. No deactivated state. Frees the email for re-invite, which the global unique `lower(email)` index would otherwise block. |
| **Routes** | `DELETE /users/me` (**any role**, always self) and `DELETE /users/{user_id}` (**admin only**, never self). Foreign org → **404**, per the org-scoping rule below. |
| **Self-service** | Available to **both roles**, from Settings. A viewer never sees the Users screen, so this is their only way out of the org. |
| **Last-admin invariant** | **An org always has at least one admin.** `/users/{user_id}` and the role-change route refuse to target the caller, so the caller always survives and neither can reach zero. `DELETE /users/me` is the only route that can, and it answers **`409 last_admin`**. |
| **Self-demotion** | **Refused outright.** An admin may leave the org but may not downgrade themselves; a colleague can demote them. This is what makes the invariant hold for role changes. |
| **Confirmation** | The operator types the **target's email address** before removal proceeds — on both surfaces (Settings and Users). |
| **Session teardown** | The cascade kills the refresh token. The delete routes do **not** clear the refresh cookie: it is `/api/v1/auth`-scoped and the SPA's business client sends no credentials, so the residual cookie is already inert. |

### Member activity ✅

Decided 2026-08-08 and implemented by spec 030 / DMI-76 on 2026-08-11. Research:
[`user-last-seen-tracking.md`](../research/user-last-seen-tracking.md). This partially pulls forward
the Phase 2 "Audit — who logged in" row below, which no longer wholly owns this.

Two nullable columns on `users`, because login and activity are genuinely different facts — the
split every mainstream implementation makes (Django `last_login`; Devise `current_sign_in_at`;
Supabase GoTrue `users.last_sign_in_at` alongside `sessions.refreshed_at`):

| Column | Stamped in | Records |
|--------|-----------|---------|
| `last_login_at` | `issue_session()` only | Real authentication — login, invite acceptance, post-reset sign-in |
| `last_seen_at` | `issue_session()` **and** `refresh_session()` | Activity, including silent refresh |

Stamping happens on the **auth paths, not middleware** — no framework surveyed writes activity to
the user row per request. `GET /users` serves **`last_seen_at` only**; `last_login_at` is recorded
now because login history cannot be backfilled, and is read when the Phase 2 audit surface lands.

Settings now carries the disclosure for both roles: admins can see when a member last used Dmitri
and when they last signed in, while no viewed/action detail is recorded. It is an expandable notice,
not an opt-out setting.

**Two implementation constraints, both load-bearing:**

- **Neither column is indexed.** PostgreSQL's heap-only-tuple optimisation requires the update not
  touch indexed columns, so indexing the column written every ~15 minutes defeats it and adds index
  bloat. Sort with `ORDER BY last_seen_at DESC NULLS LAST`; at org scale the planner seq-scans anyway.
- **The UPDATE must name only the stamped columns.** A whole-object write sends `email` back and
  hits `ix_users_email`, which defeats HOT for the same reason.

Write amplification needs no mitigation at this scale (~20 updates/hour per org, against a
crossover around 10k active users). Redis buffering, a separate activity table and `fillfactor`
tuning are all explicitly **out** — see the research doc for the trigger that would justify each.

**Privacy:** surfacing a member's activity to their org admin needs a documented lawful basis
(legitimate interests — consent is not freely given in an employment relationship) and transparency
toward the people being monitored. ICO guidance treats logon-time monitoring as comparatively
low-intrusion and a DPIA is not mandatory here, but the decision not to run one is recorded. Store
precise, render coarse — the UI shows relative time, matching the house style for hosts and agents.

### Passwords ✅

| Area | Decision |
|------|----------|
| **Invite completion** | **Email + password (A1).** Invitee opens one-time invite link and **chooses their password** to activate the account. No shared/temporary passwords. |
| **First org admin** | **Same invite flow (E2).** Vendor creates org and sends the first **admin** an invite link — not a separately seeded password. |
| **Invite link TTL** | **Short (D1).** Links expire after a brief window (target **24–72 h** at implementation). **Single-use** — consumed on successful signup. |
| **Password policy** | **Strong**, enforced at invite completion, login password change, and reset: minimum length; reject common/breached passwords; reject obvious patterns — repeated characters (e.g. `111`), keyboard/simple suffixes (e.g. `1!`), **repeated number sequences**, **birth dates**, **names** (user name, org name — implementation defines matching). |
| **Password rotation** | **No forced periodic rotation** ([`ADR-016`](../adr/ADR-016-password-policy.md), NIST SP 800-63B §5.1.1.2) — supersedes the prior "every 3 months" decision. Passwords change only voluntarily or via reset; instead, every password set is screened against known-breached passwords (HIBP Pwned-Passwords range API). |
| **Forgot password** | **Self-serve email reset (C2).** “Forgot password?” → email with one-time reset link → set new password (same policy). |
| **Transactional email** ✅ | **In scope — the backend sends invite links and reset links.** Decided 2026-07-13; **provider chosen 2026-08-02 — Resend** ([research](../research/transactional-email-provider-and-sending-domain.md)), integrated in DMI-71. Previously *nothing in the roadmap sent mail*, which left self-serve reset unbuildable — an admin can hand-carry an invite link, but a locked-out user has nobody in the loop. Code is small (`httpx` already a dependency); **the real work was a sending domain with SPF + DKIM + DMARC** — a one-time login link from a security product looks exactly like phishing and gets filtered without them. `mail.peirce.dev` was verified on 2026-08-22 (all three pass, `p=reject`), and DMI-108 then fixed spam *placement* — `multipart/alternative` plus links and mail under one domain. **Invites also keep a copyable link in the admin UI** as a fallback ([`ui/SCREENS.md` → Users & invites](../ui/SCREENS.md#users--invites)). |

**Frontend surfaces:** invite acceptance page, login, forgot password, reset password. Client mechanics (token storage, silent-refresh interceptor, route guards): [`ADR-008`](../adr/ADR-008-frontend-stack.md).

### Sessions ✅

Per ADR-005 pattern (Bearer on business APIs; refresh on `/auth/*` only).

| Area | Decision |
|------|----------|
| **Access token** | Short-lived JWT (**~15 min**, A1). `Authorization: Bearer` on all business endpoints. Stored in **SPA memory only** (E1) — full page reload triggers silent refresh. |
| **Refresh** | **httpOnly cookie** on `/auth/*` (B1). `POST /auth/refresh` with `credentials: include`; not used on scan/command routes. |
| **Refresh lifetime** | **Fixed 7 days from login** (C2) — no sliding extension. After 7 days user must **log in with password** again (helps password recall; intentional tradeoff). |
| **Refresh rotation** | **Rotate on each refresh** (D1); detect reuse / invalidate token family. |
| **Logout** | **Server revoke** (F2) — `POST /auth/logout` invalidates refresh server-side and clears cookie; not client-only. |
| **Extra session cap** | **None** (H deferred) — 7-day refresh is sufficient for September. |
| **Auth endpoints** | `POST /auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/change-password` (G). |

**SPA:** Axios Bearer on API client; `withCredentials` on `/auth/*` only. On **401**, try refresh once then redirect to login. **Single-flight the refresh** — all concurrent 401s must await one shared in-flight refresh promise, never fire one refresh per request. The backend rotates refresh tokens with strict reuse detection (no grace window, DMI-60): presenting an already-rotated token kills the whole family, so two parallel refreshes of the same cookie would look like theft and log the user out. Interceptor mechanics: [`ADR-008`](../adr/ADR-008-frontend-stack.md).

**Depends on:** [`BACKEND.md`](BACKEND.md) B10 Control ✅ — Ed25519 device signature on **ingest** + **WebSocket handshake** (confirmed; ADR-005 amended 2026-07-24).

---

## Phase 2 — Product-ready (end of year) 🔓

**Goal:** auth fit for **hosted SaaS** customers (not enterprise BYOC yet).

**Builds on Phase 1** (invite model and coarse roles already in September):

| Area | Product-ready likely adds |
|------|---------------------------|
| **Users** | Second org on same stack; `org_id` isolation tested |
| **Sessions** | Logout everywhere (all devices), optional idle timeout |
| **Authorization** | Finer permissions matrix; document role semantics |
| **Agent** | Key **rotation** and re-pair story (revoke/restore shipped in DMI-155); optional self-service pairing if no on-site installer |
| **Ops** | JWT signing key in managed secrets (not plain Railway env for prod). Device auth no longer needs a stored secret — backend holds only public keys (ADR-005 Ed25519). |
| **Audit** | Who triggered scans (minimum trail), and who removed whom. **"Who logged in" partly ships in September** — `last_login_at` / `last_seen_at` land with Account removal above; what remains here is the *trail* (an append-only record), which a mutable column on `users` cannot provide. Removal leaves no trace of itself by design ([`ADR-017`](../adr/ADR-017-account-removal.md)), so this needs its own table. `requested_by` on commands **must** be nullable / `ON DELETE SET NULL` to survive member removal. |

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
| **Pi agent** | Ed25519 per-device signature ([`ADR-005`](../adr/ADR-005-security-model.md), amended 2026-07-24; backend stores only the public key) | ✅ Required |
| **Web browser** | JWT Bearer + httpOnly refresh on `/auth/*` ([`ADR-005`](../adr/ADR-005-security-model.md)) | ✅ |

Both mechanisms are implemented and mounted. `require_agent_ws` gates the command WebSocket and
`require_agent` gates scan ingest; the browser gate protects business reads and admin mutations.
The remaining end-to-end gap is physical/operational provisioning, not an absent auth path.

---

## Built today

| Control | State |
|---------|--------|
| Identity schema (`orgs`/`users`/`invites`, `org_id` on tenant data) | ✅ Built (DMI-58) |
| Sessions + auth routes (login/refresh/logout, password change/reset) | ✅ Built (DMI-60) |
| JWT gate + role matrix (`require_user`, `require_admin`) | ✅ Built (DMI-61) |
| Org scoping on business reads (`/hosts`, `/hosts/{id}`, `/scans/{id}`, `/findings`) | ✅ Built (DMI-61) — enforced in SQL; a foreign row is 404, never 403 |
| Invite flow (admin creates, invitee accepts → session) | ✅ Built (DMI-61) |
| Account removal (`DELETE /users/me`, `DELETE /users/{user_id}`, last-admin invariant) | ✅ Built (DMI-102 / spec 029) |
| Member/pending-invite administration (`GET /users`, `PATCH /users/{id}`, `GET /invites`, `DELETE /invites/{id}`) | ✅ Built (DMI-76 / spec 030); admin-only and org-scoped |
| Member activity (`last_login_at`, `last_seen_at`) | ✅ Built (DMI-76 / spec 030); only last-seen is published, and Settings discloses both recorded facts |
| Ed25519 device-signature verify + nonce replay protection | ✅ Built and mounted on WebSocket + ingest |
| Agent→backend command channel (WebSocket) | ✅ Built on backend and Pi software; real hardware/operations remain |
| Scan ingest (`POST /api/v1/scans`) | ✅ Built on backend and Pi software; real hardware/operations remain |
| Transactional email for invites / password reset | ✅ Code built (DMI-71) — Resend chosen, `ResendMailer` sends both links; `LogMailer` is gone, nothing logs a raw token. **Delivering since 2026-08-22** — `mail.peirce.dev` verified (SPF/DKIM/DMARC, `p=reject`); DMI-108 added the HTML part and aligned the link domain so mail lands in the inbox rather than spam. Inbox placement now rests on sender reputation, not code. With `RESEND_API_KEY` unset the backend still falls back to `NullMailer` and both flows work off the returned link |

---

## Sequencing

1. **Phase 1 software controls:** identity tables ✅, sessions ✅, roles middleware ✅, invite flow ✅,
   account/member administration ✅, activity stamps/disclosure ✅, and signed command/ingest
   transports ✅. Remaining work is physical and operational deployment.
2. Plan Phase 2 before December (multi-org, device key rotation, audit, prod secrets)  
3. Phase 3 when a deal names requirements  

---

## Ripple

Phase changes affect [`FRONTEND.md`](FRONTEND.md) (login + invite UX), [`PI.md`](PI.md) (device keypair, Ed25519 signing client), [`SECURITY.md`](SECURITY.md), [`BACKEND.md`](BACKEND.md) (tables, middleware, `requested_by` on commands).
