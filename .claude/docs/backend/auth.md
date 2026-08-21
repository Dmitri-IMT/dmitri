---
type: Module
title: Backend auth — sessions, tokens, passwords, routes
description: The wired user auth/session/password system, activity stamping, invite creation/lookup/list/revoke, role gates, and request-id/CORS middleware.
resource: backend/src/api/services/auth.py
tags: [backend, auth, jwt, sessions, passwords, invites, roles, middleware, cors]
timestamp: 2026-08-18T00:00:00Z
---

# Backend auth — sessions, tokens, passwords, routes

## Purpose

The auth subsystem (spec 016 / DMI-60) is the second route group wired over HTTP after the
[read path](/backend/routers.md). It authenticates users against the dormant-no-longer
[`users` identity table](/backend/models.md), issues short-lived **JWT access tokens** plus a
rotating **refresh-token family** stored in [`refresh_tokens`](/backend/models.md), and handles the
password lifecycle (change, forgot, reset) with an argon2 hash + policy screen. It spans a
router, four services, one FastAPI dependency, and the app-wide middleware. The auth, invite,
member-admin, ingest, and command-channel routes all run in `main.py`.

Spec 017 / DMI-61 completed the gate: `require_admin` adds role enforcement on top of
`require_user`, the **invite flow** (`POST /api/v1/invites`, `POST /api/v1/invites/accept`)
lets an admin onboard a teammate, and `require_user` is now actually *mounted* on the four business
read routes with per-org scoping — see [routers](/backend/routers.md). Device (as opposed to user)
authentication is a separate gate; see [device auth](/backend/device-auth.md).

Spec 023 / DMI-77 closed the error-code edges (contract asks C13/C15/C18): every auth and invite
failure now carries a **pinned `error.code`** instead of collapsing into `bad_request`, a dead
reset link answers **410** rather than 400, re-inviting a live address answers **409**, and the
invite token moved **out of the URL path into the request body**.

Spec 027 / DMI-86 (contract ask C14) added a **public, non-consuming invite lookup**
(`POST /api/v1/invites/lookup`) so the accept page can name the org and role before asking for a
password, and — as its direct consequence — **acceptance stopped asking for the address**.
`POST /api/v1/invites/accept` now takes `{token, password}` only; the address, role and org are
read from the invite record, which is what they were always sourced from.

Spec 030 / DMI-76 completed the identity administration API: admins can list members and pending
invites, change another member's role, and revoke a pending invite. Login and invite acceptance
stamp both `users.last_login_at` and `users.last_seen_at`; refresh advances only `last_seen_at`.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `_stamp_activity()` | Bulk-updates only the activity columns: every fresh session sets `last_seen_at`, and password login or invite acceptance also sets `last_login_at`. It deliberately does not write the full `User` row. | `backend/src/api/services/auth.py:39` |
| `issue_session()` | The single place a **fresh** session is minted from a `User` — stamps both activity times, creates the access token + new refresh family, and returns `expires_in`. Used by `login` and `accept_invite`. | `backend/src/api/services/auth.py:47` |
| `login()` | Verifies email + argon2 password, then delegates to `issue_session`; bad credentials raise `InvalidCredentialsError` and mint nothing. | `backend/src/api/services/auth.py:57` |
| `refresh_session()` | Rotates within the presented refresh family, advances `last_seen_at` without changing `last_login_at`, commits both writes, and mints a fresh access token. | `backend/src/api/services/auth.py:66` |
| `logout()` | Revokes the current refresh family; silently idempotent on an unknown/stale cookie. | `backend/src/api/services/auth.py:84` |
| `change_password()` | `WrongCurrentPasswordError` on bad current pw, `PasswordPolicyError` on weak new pw (both → 400, never 401); on success updates `password_hash`/`password_changed_at` without touching sessions. | `backend/src/api/services/auth.py:88` |
| `forgot_password()` | Sends a reset link **only** for a real account (via the `Mailer`) but never raises — no account enumeration. | `backend/src/api/services/auth.py:104` |
| `reset_password()` | Consumes the single-use token once (`InvalidResetTokenError` on missing/consumed/expired), validates policy, updates the password, and `revoke_all_refresh_tokens` to log out everywhere. The token is checked **before** the policy. | `backend/src/api/services/auth.py:123` |
| `create_access_token()` / `decode_access_token()` | PyJWT HS256; claims `sub`/`org_id`/`role`/`iat`/`exp`, exp from `ACCESS_TOKEN_TTL_MINUTES` (15), signed with `JWT_SIGNING_SECRET`. | `backend/src/api/services/tokens.py:20` |
| `issue_refresh_token()` | Raw = `secrets.token_urlsafe(32)`, stored as `sha256` hex; new `family_id`, `family_expires_at` = now + `REFRESH_TOKEN_TTL_DAYS` (7d). | `backend/src/api/services/tokens.py:42` |
| `rotate_refresh_token()` | Sets `rotated_at` on the old row and mints a new row in the same family with the **copied** `family_expires_at`; reuse of a rotated/revoked hash calls `_revoke_family` and raises `RefreshTokenError`; refresh past `family_expires_at` rejected. | `backend/src/api/services/tokens.py:73` |
| `revoke_refresh_token()` / `revoke_all_refresh_tokens()` | Revoke the current family / every one of a user's refresh rows (one UPDATE). | `backend/src/api/services/tokens.py:104` |
| `hash_password()` / `verify_password()` | argon2-cffi hash + verify. | `backend/src/api/services/passwords.py:36` |
| `validate_policy()` | Enforces the AUTH.md rules — min length 12, common/breached, repeated-char / keyboard-suffix / repeated-number, email/name/org substrings — raising a violation-listing `PasswordPolicyError`; includes the HIBP k-anonymity screen. | `backend/src/api/services/passwords.py:76` |
| `_check_hibp()` | SHA-1 range-API screen (first 5 chars sent, 35-char suffix matched locally), gated by `HIBP_ENABLED`; skipped (not failed) on timeout/HTTP error. | `backend/src/api/services/passwords.py:57` |
| `Mailer` | Protocol `send_reset_link(email, token)` + `send_invite_link(email, token)`. Both take a **raw token, never a URL**; the mailer builds the URL itself from `APP_BASE_URL`. | `backend/src/api/services/mailer.py:40` |
| `invite_link()` / `reset_link()` | The two link shapes the emails point at — `{APP_BASE_URL}/invite?token={token}` and `{APP_BASE_URL}/reset-password?token={token}`. The single place a token becomes a URL; both use the query form since DMI-77. | `backend/src/api/services/mailer.py:45`, `:50` |
| `ResendMailer` | Posts a **plain-text** message to the Resend API (`RESEND_API_BASE_URL`, `Bearer RESEND_API_KEY`, `MAIL_FROM`, optional `MAIL_REPLY_TO`, `MAIL_TIMEOUT_SECONDS`). Snapshots every setting it needs in `__init__`. Swallows transport errors and ≥400 responses into a `logger.error` that never contains the token. | `backend/src/api/services/mailer.py:68` |
| `NullMailer` | Used when `RESEND_API_KEY` is unset: logs a warning that the mail was **not** sent (never the token), so invites and resets still work off the returned link. | `backend/src/api/services/mailer.py:55` |
| `BackgroundMailer` | Wraps a `Mailer` and defers each send onto FastAPI `BackgroundTasks`, so the provider call happens after the response — see the note below. | `backend/src/api/services/mailer.py:132` |
| `get_mailer(tasks)` | The seam both routes call: `NullMailer` when the key is missing or blank, otherwise `BackgroundMailer(tasks, ResendMailer())`. | `backend/src/api/services/mailer.py:153` |
| `create_invite()` | Admin-side, in order: takes a transaction-scoped `pg_advisory_xact_lock(INVITE_LOCK_NAMESPACE, hashtext(org_id‖lower(email)))`, refuses an email already a user in **this** org, refuses an address with an unconsumed unexpired invite, then stores only `sha256(raw)` and returns the raw token once. | `backend/src/api/services/invites.py:40` |
| `INVITE_LOCK_NAMESPACE` | `8817` — separates the per-org/email invite lock from the org-admin lock namespace in [`org_lock.py`](/backend/services.md). | `backend/src/api/services/invites.py:37` |
| `accept_invite()` | Consumes a live invite and creates the user in one commit, then delegates to `issue_session`, which stamps both user activity times. The address, role, and org all come from the invite row. | `backend/src/api/services/invites.py:95` |
| `read_invite()` | Public lookup half: resolves a live token to `(email, role, org_name)` without consuming it or issuing a session. Unknown, expired, and consumed all raise the same `InviteTokenError`. | `backend/src/api/services/invites.py:136` |
| `list_pending_invites()` | Returns only the caller org's unconsumed, unexpired invites, ordered by `expires_at` then `id`; token material is never projected. | `backend/src/api/services/invites.py:154` |
| `revoke_invite()` | Org-scoped, pending-only hard delete. Unknown, expired, consumed, and foreign-org identifiers all return `False`, which the router maps to 404. | `backend/src/api/services/invites.py:165` |
| `require_user()` / `CallerIdentity` | FastAPI dependency validating the `Authorization: Bearer` JWT → caller identity (sub/org_id/role); missing/invalid/expired → 401. | `backend/src/api/dependencies/auth.py:25` |
| `require_user_row()` | Depends on `require_user`, then loads the caller's `User` row; a signed token whose subject no longer exists → **401**. Used by `GET /users/me`, `DELETE /users/me`, and change-password — the routes that need the row itself. | `backend/src/api/dependencies/auth.py:42` |
| `require_admin()` / `ROLE_ADMIN` / `ROLE_VIEWER` | Depends on `require_user` (never re-decodes the token) and raises 403 unless the role is exactly `admin` — an allowlist, so an unknown role is denied rather than waved through. | `backend/src/api/dependencies/auth.py:54` |
| auth routes | 6 POST routes (`login`/`refresh`/`logout`/`change-password`/`forgot-password`/`reset-password`) + OPTIONS preflights; set/clear the `dmitri_refresh` cookie. | `backend/src/api/routers/auth.py:62` |
| invite routes | Admin create/list/revoke (`POST`/`GET /api/v1/invites`, `DELETE /api/v1/invites/{invite_id}`), public accept/lookup (`POST /accept`, `POST /lookup`). Listing returns no token; revocation is pending-only and answers 204. | `backend/src/api/routers/invites.py:39` |
| `lookup_invite_route()` | Public, non-consuming `POST /api/v1/invites/lookup`; possession of the body token is the only authorisation. Returns `{email, role, org_name}` or 410 `invalid_invite_token`. | `backend/src/api/routers/invites.py:82` |
| invite preflight loop | Registers bare 204 `OPTIONS` routes for each invite `POST`; `GET` and `DELETE` preflights are handled by the CORS middleware. | `backend/src/api/routers/invites.py:129` |
| `set_refresh_cookie()` / `clear_refresh_cookie()` | `dmitri_refresh` cookie: `HttpOnly`, `Path=/api/v1/auth`, `SameSite=None`, `Max-Age`=7d, `Secure` per `REFRESH_COOKIE_SECURE`. The only place a cookie is set. `None` since 2026-08-18 (`f2836ba`): `up.railway.app` is a public suffix, so `nspi.` and `api-nspi.` are separate registrable domains and a `Lax` cookie was never attached to the cross-site refresh call. See the Notes below — it contradicts [ADR-005](../../../docs/adr/ADR-005-security-model.md) §cookie flags. | `backend/src/api/session_response.py:17` |
| `login_response()` | Builds the `LoginResponse` **and** sets the refresh cookie; used by `login_route`, `refresh_route`, and `accept_invite_route` so no route hand-rolls either. | `backend/src/api/routers/auth.py:52` |
| `RequestIdMiddleware` | Reads inbound `X-Request-Id` or generates a uuid4, sets it on **every** response. | `backend/src/api/middleware.py:15` |
| `NoContentCorsMiddleware` | Subclasses Starlette `CORSMiddleware`, overriding `preflight_response` to return **204** (contract requires it) instead of the default 200. It **rebuilds** the response rather than reassigning `status_code`, dropping `content-length` and `content-type`: the parent returns `PlainTextResponse("OK", 200)`, so a bare status reassignment left a 204 declaring a 2-byte body — malformed per RFC 9110 §15.3.5, and WebKit answers it by dropping the real request. | `backend/src/api/middleware.py:38` |
| `build_cors_middleware_kwargs()` | Builds credentialed CORS kwargs from `CORS_ALLOWED_ORIGINS`; allowed methods are GET/POST/PATCH/DELETE/OPTIONS, covering role change and removal/revocation. | `backend/src/api/middleware.py:53` |

## How it connects

- **Upstream** — the router and both middleware are registered in [`main.py`](/backend/api.md);
  `main.py` also answers `OPTIONS /api/v1/health` with 204 through the CORS middleware.
- **Config** — every knob (`JWT_SIGNING_SECRET`, the TTLs, `REFRESH_COOKIE_SECURE`,
  `CORS_ALLOWED_ORIGINS`, `RESET_TOKEN_TTL_MINUTES`, `HIBP_*`, and the mail block
  `RESEND_API_KEY`/`RESEND_API_BASE_URL`/`MAIL_FROM`/`MAIL_REPLY_TO`/`MAIL_TIMEOUT_SECONDS`/
  `APP_BASE_URL`) is a `Settings` field — see [config](/backend/api.md).
- **Data** — refresh/reset rows live in [`models/session.py`](/backend/models.md); identity and
  activity columns live in `identity.py`. [Migration `20260810_16`](/backend/migrations.md) adds the
  two user timestamps and grants runtime DELETE on `invites`.
- `routers/auth.py` maps the service exception types to HTTP status: `InvalidCredentialsError` →
  401; `WrongCurrentPasswordError` → `ApiError(400, code="wrong_current_password")`;
  `PasswordPolicyError` on change-password **and** on reset-password →
  `ApiError(400, code="password_policy_violation")` (contract C13 — both stay 400, never 401);
  `InvalidResetTokenError` → `ApiError(410, code="invalid_reset_token")` (C15). Login/refresh/logout
  still raise bare `HTTPException` and get the [default envelope codes](/backend/errors.md).
- `routers/invites.py` no longer raises `HTTPException` at all. `AlreadyMemberError` →
  `ApiError(400, code="email_already_member")`; `PendingInviteError` →
  `ApiError(409, code="invite_already_pending")`; on accept, `InviteTokenError` →
  `ApiError(410, code="invalid_invite_token")` and `DuplicateUserError` / `PasswordPolicyError` →
  400 `email_already_registered` / `password_policy_violation`. The lookup route maps the one
  exception it catches, `InviteTokenError`, to the same 410 `invalid_invite_token`. A non-admin
  caller still falls through `require_admin` as **403**.
  `InviteEmailMismatchError` and its `invite_email_mismatch` code **no longer exist** — DMI-86
  deleted them along with the address field that could mismatch.
- **The router literals are gated against the contract.** `test_contract_fidelity.py` AST-walks each
  route function for its `ApiError(status, …, code="…")` literals and asserts exact set equality
  against the pinned `enum` in the matching `components/responses` entry, per status. A typo in
  either direction fails the suite — see [contracts](/contracts.md).
- **Bootstrap** — the *first* org and its admin invite cannot come from an authenticated route;
  they come from [`backend-bootstrap-org`](/backend/management.md).

## Notes / gotchas

- **The refresh cookie is `SameSite=None`, and that contradicts ADR-005.** Railway serves the SPA
  at `nspi.up.railway.app` and the API at `api-nspi.up.railway.app`. `up.railway.app` is on the
  Public Suffix List, so those are **separate registrable domains** — every `/auth/*` call is a
  cross-site subresource request and a `Lax` cookie is never attached, which is why refresh
  returned 401 forever in production. `f2836ba` (2026-08-18) switched both set and clear to
  `SameSite=None`, which requires `Secure` (supplied by `REFRESH_COOKIE_SECURE`; localhost is
  exempt from the HTTPS rule, so local dev is unaffected).
  [ADR-005](../../../docs/adr/ADR-005-security-model.md) §"Flags previstas" still specifies
  `SameSite=Lax` *ou mais restritivo*, and `None` is strictly **less** restrictive — the ADR and
  the code disagree, and the same ADR requires CSRF to be "tratado explicitamente" once a
  cookie-authenticated mutation exists, which `POST /auth/refresh` now is. Unresolved; a custom
  domain (`app.` + `api.` under one registrable domain) would make the pair same-site again and
  allow `Lax` back. See [research](../../../docs/research/http-cookies-samesite.md).
- **A preflight must not carry a body.** `NoContentCorsMiddleware` rebuilds the parent's
  `PlainTextResponse("OK", 200)` as a bare 204 instead of reassigning `status_code`. The old
  version shipped `204` with `Content-Length: 2`; Chrome and curl tolerate it, WebKit rejects the
  preflight and never sends the real request, which surfaced as "Can't reach the server" on iOS.
  Two regression tests pin the empty body and the absent `content-length` / `content-type`.

- **Refresh-token reuse revokes the whole family.** Presenting a rotated or revoked hash is treated
  as theft and kills every row sharing that `family_id`; `family_expires_at` is fixed at login and
  copied verbatim on each rotation, so the 7-day window never slides.
- **Both password errors are 400, not 401.** A wrong *current* password and a policy-violating
  *new* password are caller errors (contract C13); only a missing/invalid/expired Bearer is 401.
  Change-password now raises [`ApiError`](/backend/errors.md) with distinct `error.code` values so
  the SPA can branch without decoding JWT claims.
- **`refresh_session` cannot reuse `issue_session`.** `issue_session` calls `issue_refresh_token`,
  which mints a token in a **new** `family_id`; refresh must call `rotate_refresh_token` to stay in
  the **same** family. Routing refresh through `issue_session` orphans a token row in an unlinked
  family and leaves the presented token's `rotated_at`/`revoked_at` NULL, so reuse detection never
  fires. The ~3 duplicated lines of access-token construction are the deliberate price.
- **Activity stamps have different meanings.** `issue_session` is reached by password login and
  invite acceptance, so both timestamps advance. `refresh_session` advances only `last_seen_at`.
  The member list exposes `last_seen_at`; `last_login_at` is stored for the later audit surface.
- **Invites use two different duplicate scopes, and they are not symmetrical.** `create_invite`
  checks **own-org only**, so inviting an address that already has an account in *another* org
  succeeds and returns a response indistinguishable from a fresh address — no cross-tenant
  existence oracle. `accept_invite` checks **globally**, because `users` email uniqueness became
  global in migration `20260724_10`; a genuine collision fails at acceptance, not at invitation.
- **An invite's `consumed_at` is written in the same commit as the `User` insert.** Every failure
  path — unknown, expired, already-consumed, duplicate user, weak or breached password — leaves
  `consumed_at` NULL and no `User` row. **Reading an invite is not a failure path and not a write
  path**: `read_invite` never touches `consumed_at` either, so a lookup leaves the invite fully
  acceptable.
- **Dropping accept's email was a re-sourcing, not a deletion.** The address was read in three
  places; only the mismatch check went away. The duplicate-user lookup and `validate_policy` both
  still receive it, now from `invite.email`. Deleting rather than re-sourcing the policy argument
  would silently stop the password screen from considering the invited address — a quiet
  weakening no other test would catch, which is why
  `test_accept_invite_password_policy_still_receives_the_invited_address` exists specifically to
  fail if that argument is ever dropped.
- **The lookup is advisory display data, never authority.** Nothing a caller sends can influence
  what an accepted account receives: org, role and address are read from the invite row at
  acceptance. Both invite request models are `extra="forbid"`, so a caller who appends `role` or
  `email` gets a **422** rather than having it silently ignored — the loud-failure property is the
  point.
- **Expired, accepted and unknown are one answer, deliberately.** `read_invite` collapses all three
  into a single predicate and a single raise, and the route publishes the *same*
  `AcceptInviteTokenGone` response component acceptance already uses. Three error types would be
  three chances for status, code or body to diverge and turn the lookup into an enumeration oracle;
  a route test asserts the lookup's 410 body equals the accept route's byte for byte. Token entropy
  (256 bits), not throttling, is what protects the route — there is no rate limiting in the service
  on this or any route.
- **The invite token travels in the request body, not the URL.** `POST /api/v1/invites/accept` reads
  `body.token`. It was a path parameter until DMI-77; uvicorn's default access logger (this repo
  configures none) and any edge proxy write the path to a log line, which put a live single-use
  credential in the logs. Reset-password always took its token in the body and never had the
  problem. Both emailed links now use the query form, which is *not* a fix for the same issue — the
  research found the link shape has no security significance — just consistency.
- **The pending-invite check exists because `Invite.role` is per-row.** Without it, two concurrent
  `create_invite` calls both pass the member check under READ COMMITTED and both insert; if their
  roles differ, the invitee picks their own privilege by choosing which email to click. The
  `pg_advisory_xact_lock` closes that window and releases on commit or rollback — there is no unlock
  call and no cleanup path anywhere.
- **There is deliberately no partial index behind the pending check.** `WHERE expires_at > now()`
  will not compile (index predicates must be IMMUTABLE; `now()` is STABLE), and
  `WHERE consumed_at IS NULL` is semantically wrong because nothing sweeps expired invites — it
  would permanently block re-inviting anyone whose invite lapsed. Reissue after expiry or
  consumption is tested behavior.
- **`email_already_member` and `email_already_registered` are different scopes, not synonyms.** The
  first is org-scoped (create-invite); the second is global (accept-invite). The names carry the
  asymmetry described two bullets above on purpose.
- **No enumeration — including in timing.** `forgot_password` always yields 204 whether or not the
  email exists, and because `get_mailer` hands the route a `BackgroundMailer`, the provider call
  runs *after* the response. Response latency therefore does not reveal whether mail went out. The
  same deferral means a slow provider no longer holds the request's DB session: FastAPI exits
  `yield` dependencies before background tasks run, so the pooled connection is already back.
- **Email delivery is best-effort; the link is the guarantee.** `create_invite` commits and returns
  the raw token *before* the mailer is called, and `ResendMailer` swallows provider failures. A
  Resend outage therefore costs an email, never an invite — the admin still has a copyable link.
  With `RESEND_API_KEY` unset (`NullMailer`) nothing is emailed at all and both flows still work.
- **HIBP fails open.** A timeout or HTTP error on the pwnedpasswords range call skips the screen
  rather than blocking a password change; tests mock it and never hit the network.
- **DB-backed tests skip without local Postgres** — `test_auth_routes.py`, `test_auth_service.py`,
  `test_tokens.py`, `test_auth_migration.py` follow the project's Postgres-fixture skip pattern.

# Citations

[1] [specs/016-sessions-auth-routes](../../../specs/016-sessions-auth-routes/TRUTH.md)
[1a] [specs/017-auth-middleware-invite-flow](../../../specs/017-auth-middleware-invite-flow/TRUTH.md)
[1b] [specs/023-auth-invite-contract-edges](../../../specs/023-auth-invite-contract-edges/PLAN.md)
[1c] [specs/027-invite-lookup](../../../specs/027-invite-lookup/TRUTH.md)
[1d] [specs/030-users-invites-admin-api](../../../specs/030-users-invites-admin-api/TRUTH.md)
[2] [docs/adr/ADR-005-security-model.md](../../../docs/adr/ADR-005-security-model.md)
[3] [docs/adr/ADR-016-password-policy.md](../../../docs/adr/ADR-016-password-policy.md)
[4] [docs/roadmap/AUTH.md](../../../docs/roadmap/AUTH.md)
[5] [contracts/openapi/openapi.yaml](../../../contracts/openapi/openapi.yaml)
